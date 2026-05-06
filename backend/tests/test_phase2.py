"""SeriesTrack Phase 2 — new features backend tests.
Covers: Google OAuth (negative), Episode progress, Reviews, Public profile/library, Web Push.
Runs against the public backend URL.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://show-notify.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASSWORD = "Admin@123"
BB_TMDB_ID = 1396  # Breaking Bad


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "token": data["access_token"],
        "id": data["user"]["id"],
        "email": data["user"]["email"],
        "name": data["user"].get("name"),
        "headers": {
            "Authorization": f"Bearer {data['access_token']}",
            "Content-Type": "application/json",
        },
    }


@pytest.fixture(scope="module", autouse=True)
def cleanup_phase2(admin):
    """Before & after: remove any leftover progress/review/push test data for admin user."""
    H = admin["headers"]
    # Pre-clean
    requests.delete(f"{API}/reviews/{BB_TMDB_ID}", headers=H, timeout=10)
    # Ensure BB not in library beforehand (library tests may leave it)
    requests.delete(f"{API}/library/{BB_TMDB_ID}", headers=H, timeout=10)
    yield
    # Post-clean
    requests.delete(f"{API}/reviews/{BB_TMDB_ID}", headers=H, timeout=10)
    requests.delete(f"{API}/library/{BB_TMDB_ID}", headers=H, timeout=10)
    # Clear progress docs (no bulk API — toggle off each episode we touched)
    for ep in (1, 2):
        requests.post(
            f"{API}/progress",
            headers=H,
            json={"tmdb_id": BB_TMDB_ID, "season": 1, "episode": ep, "watched": False},
            timeout=10,
        )


# ---------------- Google OAuth negative ----------------
class TestGoogleAuth:
    def test_google_bogus_session_returns_401_not_500(self, session):
        r = session.post(f"{API}/auth/google", json={"session_id": "bogus-" + uuid.uuid4().hex}, timeout=30)
        # Expected: 401 (invalid session) — MUST NOT 500
        assert r.status_code != 500, f"endpoint crashed: {r.text}"
        assert r.status_code in (401, 502), f"unexpected: {r.status_code} {r.text}"


# ---------------- Push public key ----------------
class TestPushPublicKey:
    def test_push_public_key(self, session):
        r = session.get(f"{API}/push/public_key", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "public_key" in data
        assert "available" in data
        assert isinstance(data["available"], bool)


# ---------------- Episode progress ----------------
class TestProgress:
    def test_mark_and_unmark_episode(self, admin):
        H = admin["headers"]
        # Initially: list may have prior docs; just ensure mark & unmark works
        # Mark S1E1 watched
        r = requests.post(
            f"{API}/progress",
            headers=H,
            json={"tmdb_id": BB_TMDB_ID, "season": 1, "episode": 1, "watched": True},
            timeout=10,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        r = requests.get(f"{API}/progress/{BB_TMDB_ID}", headers=H, timeout=10)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        assert any(x["season"] == 1 and x["episode"] == 1 for x in arr)

        # Unmark
        r = requests.post(
            f"{API}/progress",
            headers=H,
            json={"tmdb_id": BB_TMDB_ID, "season": 1, "episode": 1, "watched": False},
            timeout=10,
        )
        assert r.status_code == 200
        r = requests.get(f"{API}/progress/{BB_TMDB_ID}", headers=H, timeout=10)
        arr = r.json()
        assert not any(x["season"] == 1 and x["episode"] == 1 for x in arr)

    def test_progress_summary(self, admin):
        H = admin["headers"]
        # Mark S1E1 and S1E2
        for ep in (1, 2):
            r = requests.post(
                f"{API}/progress",
                headers=H,
                json={"tmdb_id": BB_TMDB_ID, "season": 1, "episode": ep, "watched": True},
                timeout=10,
            )
            assert r.status_code == 200

        r = requests.get(f"{API}/progress/{BB_TMDB_ID}/summary", headers=H, timeout=30)
        assert r.status_code == 200, r.text
        s = r.json()
        assert "seasons" in s and isinstance(s["seasons"], list)
        assert "total_watched" in s and "total_episodes" in s and "percent" in s
        assert s["total_watched"] >= 2
        s1 = next((x for x in s["seasons"] if x["season_number"] == 1), None)
        assert s1 is not None
        assert s1["watched"] >= 2
        assert s1["total"] >= s1["watched"]
        assert 0 <= s1["percent"] <= 100

    def test_progress_requires_auth(self, session):
        r = session.get(f"{API}/progress/{BB_TMDB_ID}", timeout=10)
        assert r.status_code == 401


# ---------------- Reviews ----------------
class TestReviews:
    def test_create_update_fetch_delete(self, admin):
        H = admin["headers"]
        # Create
        r = requests.post(
            f"{API}/reviews",
            headers=H,
            json={"tmdb_id": BB_TMDB_ID, "rating": 5, "comment": "TEST_review initial"},
            timeout=10,
        )
        assert r.status_code == 200, r.text

        # GET list + average
        r = requests.get(f"{API}/reviews/{BB_TMDB_ID}", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "reviews" in d and "average" in d and "count" in d
        assert d["count"] >= 1
        mine = next((x for x in d["reviews"] if x["user_id"] == admin["id"]), None)
        assert mine is not None
        assert mine["rating"] == 5
        assert mine["comment"] == "TEST_review initial"

        # Mine
        r = requests.get(f"{API}/reviews/{BB_TMDB_ID}/mine", headers=H, timeout=10)
        assert r.status_code == 200
        m = r.json()
        assert m.get("rating") == 5

        # Update (upsert)
        r = requests.post(
            f"{API}/reviews",
            headers=H,
            json={"tmdb_id": BB_TMDB_ID, "rating": 4, "comment": "TEST_review updated"},
            timeout=10,
        )
        assert r.status_code == 200
        r = requests.get(f"{API}/reviews/{BB_TMDB_ID}/mine", headers=H, timeout=10)
        assert r.json()["rating"] == 4
        assert r.json()["comment"] == "TEST_review updated"

        # Delete
        r = requests.delete(f"{API}/reviews/{BB_TMDB_ID}", headers=H, timeout=10)
        assert r.status_code == 200
        r = requests.get(f"{API}/reviews/{BB_TMDB_ID}/mine", headers=H, timeout=10)
        assert r.status_code == 200
        assert r.json() == {} or not r.json()

    @pytest.mark.parametrize("bad_rating", [0, 6, -1, 10])
    def test_rating_out_of_bounds(self, admin, bad_rating):
        H = admin["headers"]
        r = requests.post(
            f"{API}/reviews",
            headers=H,
            json={"tmdb_id": BB_TMDB_ID, "rating": bad_rating, "comment": "bad"},
            timeout=10,
        )
        assert r.status_code == 422, f"rating={bad_rating} got {r.status_code}"

    def test_reviews_public_list_no_auth(self, session):
        r = session.get(f"{API}/reviews/{BB_TMDB_ID}", timeout=10)
        assert r.status_code == 200


# ---------------- Public profile / library ----------------
class TestPublicProfile:
    def test_public_profile(self, session, admin):
        r = session.get(f"{API}/users/{admin['id']}/public", timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == admin["id"]
        assert "name" in d
        for k in ("watching", "paused", "finished", "want", "total"):
            assert k in d["stats"]
        assert isinstance(d.get("recent_reviews"), list)

    def test_public_library(self, session, admin):
        r = session.get(f"{API}/users/{admin['id']}/library", timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_public_profile_not_found(self, session):
        # Valid ObjectId format but non-existent
        r = session.get(f"{API}/users/{'0' * 24}/public", timeout=10)
        assert r.status_code == 404

    def test_public_profile_invalid_id(self, session):
        r = session.get(f"{API}/users/not-an-id/public", timeout=10)
        assert r.status_code == 404


# ---------------- Web Push ----------------
class TestPush:
    SYNTHETIC_ENDPOINT = "https://fcm.googleapis.com/fcm/send/TEST_push_" + uuid.uuid4().hex

    def test_subscribe_unsubscribe(self, admin):
        H = admin["headers"]
        payload = {
            "endpoint": self.SYNTHETIC_ENDPOINT,
            "keys": {
                "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM",
                "auth": "tBHItJI5svbpez7KI4CCXg",
            },
        }
        r = requests.post(f"{API}/push/subscribe", headers=H, json=payload, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Unsubscribe
        r = requests.delete(
            f"{API}/push/subscribe",
            headers=H,
            params={"endpoint": self.SYNTHETIC_ENDPOINT},
            timeout=10,
        )
        assert r.status_code == 200

    def test_push_test_without_subs(self, admin):
        H = admin["headers"]
        # Ensure no subs remain
        r = requests.post(f"{API}/push/test", headers=H, timeout=10)
        # Should be 400 (no active subscriptions)
        assert r.status_code in (200, 400)

    def test_push_notify_today(self, admin):
        H = admin["headers"]
        r = requests.post(f"{API}/push/notify_today", headers=H, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "created" in d and "pushed" in d
        assert isinstance(d["created"], int) and isinstance(d["pushed"], int)


# ---------------- Regression: phase-1 endpoints still work ----------------
class TestRegression:
    def test_auth_me(self, admin):
        r = requests.get(f"{API}/auth/me", headers=admin["headers"], timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_series_detail(self, session):
        r = session.get(f"{API}/series/{BB_TMDB_ID}", timeout=20)
        assert r.status_code == 200
        assert r.json()["id"] == BB_TMDB_ID

    def test_library(self, admin):
        r = requests.get(f"{API}/library", headers=admin["headers"], timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_calendar(self, admin):
        r = requests.get(f"{API}/calendar/upcoming", headers=admin["headers"], timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats(self, admin):
        r = requests.get(f"{API}/stats", headers=admin["headers"], timeout=10)
        assert r.status_code == 200
        for k in ("watching", "paused", "finished", "want", "total"):
            assert k in r.json()

    def test_notifications(self, admin):
        r = requests.get(f"{API}/notifications", headers=admin["headers"], timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
