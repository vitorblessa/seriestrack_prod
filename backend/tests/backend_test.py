"""SeriesTrack backend test suite (pytest).
Tests auth, public TMDB endpoints, library, calendar, notifications, and stats.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://show-notify.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASSWORD = "Admin@123"
BB_TMDB_ID = 1396  # Breaking Bad


# ---------------- Fixtures ----------------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(session):
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    assert data["user"]["email"] == ADMIN_EMAIL
    return data["access_token"]


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------- Health ----------------
def test_root(session):
    r = session.get(f"{API}/", timeout=10)
    assert r.status_code == 200
    assert r.json().get("app") == "SeriesTrack"


# ---------------- Auth ----------------
class TestAuth:
    def test_register_new_user(self, session):
        email = f"TEST_user_{uuid.uuid4().hex[:8]}@seriestrack-test.com"
        r = session.post(f"{API}/auth/register", json={"email": email, "password": "Test@1234", "name": "Test User"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "access_token" in data
        assert data["user"]["email"] == email.lower()
        assert data["user"]["name"] == "Test User"
        # token works
        me = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"}, timeout=10)
        assert me.status_code == 200
        assert me.json()["email"] == email.lower()

    def test_register_duplicate(self, session):
        r = session.post(f"{API}/auth/register", json={"email": ADMIN_EMAIL, "password": "Admin@123", "name": "Admin"}, timeout=10)
        assert r.status_code == 400

    def test_login_admin(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_login_invalid(self, session):
        r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_me_requires_auth(self):
        # Use clean session (no cookies) to ensure 401
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_me_with_bearer(self, session, auth_headers):
        r = session.get(f"{API}/auth/me", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_logout(self, session, auth_headers):
        r = session.post(f"{API}/auth/logout", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# ---------------- Public TMDB endpoints ----------------
class TestPublicSeries:
    @pytest.mark.parametrize("path", ["trending", "popular", "airing_today", "on_the_air", "top_rated"])
    def test_list_endpoints(self, session, path):
        r = session.get(f"{API}/series/{path}", timeout=20)
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0, f"{path} returned empty"
        # Validate first item schema
        item = data[0]
        for key in ("id", "name", "poster_url", "overview"):
            assert key in item, f"{path}: missing {key}"
        # Should be capped at 20
        assert len(data) <= 20

    def test_search(self, session):
        r = session.get(f"{API}/series/search", params={"q": "breaking"}, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0
        names = [x.get("name", "").lower() for x in data]
        assert any("breaking" in n for n in names)

    def test_series_detail(self, session):
        r = session.get(f"{API}/series/{BB_TMDB_ID}", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == BB_TMDB_ID
        assert "Breaking Bad" in d["name"] or d["name"]
        assert isinstance(d.get("seasons"), list) and len(d["seasons"]) > 0
        assert isinstance(d.get("cast"), list)
        assert isinstance(d.get("recommendations"), list)
        assert "providers" in d

    def test_season_detail(self, session):
        r = session.get(f"{API}/series/{BB_TMDB_ID}/season/1", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["season_number"] == 1
        assert isinstance(d.get("episodes"), list)
        assert len(d["episodes"]) > 0
        ep = d["episodes"][0]
        for k in ("episode_number", "name", "air_date"):
            assert k in ep


# ---------------- Library / Stats / Notifications / Calendar ----------------
class TestLibraryFlow:
    def test_full_flow(self, session, auth_headers):
        # Cleanup pre-existing
        session.delete(f"{API}/library/{BB_TMDB_ID}", headers=auth_headers, timeout=10)

        # Add to library
        r = session.post(f"{API}/library", headers=auth_headers, json={"tmdb_id": BB_TMDB_ID, "status": "watching"}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # contains -> true
        r = session.get(f"{API}/library/contains/{BB_TMDB_ID}", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        cdata = r.json()
        assert cdata["in_library"] is True
        assert cdata["item"]["status"] == "watching"
        assert cdata["item"]["tmdb_id"] == BB_TMDB_ID

        # GET library
        r = session.get(f"{API}/library", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        items = r.json()
        assert any(i["tmdb_id"] == BB_TMDB_ID for i in items)

        # Stats
        r = session.get(f"{API}/stats", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        st = r.json()
        for k in ("watching", "paused", "finished", "want", "total"):
            assert k in st
        assert st["watching"] >= 1
        assert st["total"] >= 1

        # Update status -> finished
        r = session.post(f"{API}/library", headers=auth_headers, json={"tmdb_id": BB_TMDB_ID, "status": "finished"}, timeout=15)
        assert r.status_code == 200
        r = session.get(f"{API}/library/contains/{BB_TMDB_ID}", headers=auth_headers, timeout=10)
        assert r.json()["item"]["status"] == "finished"

        # Notifications: should have at least one (created on add)
        r = session.get(f"{API}/notifications", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        notifs = r.json()
        assert isinstance(notifs, list)
        assert len(notifs) >= 1

        r = session.get(f"{API}/notifications/unread_count", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        assert "count" in r.json()

        r = session.post(f"{API}/notifications/read_all", headers=auth_headers, timeout=10)
        assert r.status_code == 200

        r = session.get(f"{API}/notifications/unread_count", headers=auth_headers, timeout=10)
        assert r.json()["count"] == 0

        # Calendar
        r = session.get(f"{API}/calendar/upcoming", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        cal = r.json()
        assert isinstance(cal, list)

        # Cleanup - delete
        r = session.delete(f"{API}/library/{BB_TMDB_ID}", headers=auth_headers, timeout=10)
        assert r.status_code == 200

        r = session.get(f"{API}/library/contains/{BB_TMDB_ID}", headers=auth_headers, timeout=10)
        assert r.json()["in_library"] is False

    def test_library_requires_auth(self, session):
        r = session.get(f"{API}/library", timeout=10)
        assert r.status_code == 401
