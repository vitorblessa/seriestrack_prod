"""Iteration 7: Tests for 3 NEW backend endpoints:
- GET  /api/ai/preview_rec         (Free upsell hook — TMDB-native rec, 1 item)
- POST /api/import/trakt           (multipart upload, JSON list / JSON {shows:[]} / CSV)
- GET  /api/calendar/ical          (text/calendar feed; supports Authorization header AND ?token=)

Conventions match other test files in this dir (BASE_URL from env, admin Pro creds + ephemeral
free user registered per-class for free-tier path).
"""
import io
import os
import json
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://show-notify.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "seriestrack")

ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASSWORD = "Admin@123"

FREE_CAP = 50


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def free_user(mongo_db):
    """Register an ephemeral free-tier user; full cleanup afterwards."""
    email = f"TEST_iter7_{uuid.uuid4().hex[:10]}@seriestrack-test.com"
    pwd = "FreeUser@123"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": pwd, "name": "Iter7 Free"}, timeout=20)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    user_id = r.json()["user"]["id"]
    yield {"email": email, "token": token, "user_id": user_id,
           "headers": {"Authorization": f"Bearer {token}"}}
    # teardown
    mongo_db.library.delete_many({"user_id": user_id})
    mongo_db.users.delete_one({"email": email})


# ============================================================
# 1. GET /api/ai/preview_rec
# ============================================================
class TestAIPreviewRec:
    """Free upsell hook — returns ONE TMDB recommendation based on user's library."""

    def test_unauthenticated_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/ai/preview_rec", timeout=15)
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"

    def test_empty_library_returns_rec_null(self, free_user):
        # Fresh user has 0 library items.
        r = requests.get(f"{BASE_URL}/api/ai/preview_rec",
                         headers=free_user["headers"], timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("rec") is None
        assert data.get("reason") == "empty_library"

    def test_with_library_free_user_returns_rec(self, free_user):
        # Add 1 item then expect a real rec
        add = requests.post(f"{BASE_URL}/api/library",
                            json={"tmdb_id": 1396, "status": "watching"},  # Breaking Bad
                            headers={**free_user["headers"], "Content-Type": "application/json"},
                            timeout=30)
        assert add.status_code in (200, 201), f"library add failed: {add.status_code} {add.text}"

        r = requests.get(f"{BASE_URL}/api/ai/preview_rec",
                         headers=free_user["headers"], timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Either we got a rec (most common — Breaking Bad has many recs) or no_match (rare)
        if data.get("rec") is None:
            assert data.get("reason") in ("no_match", "empty_library")
            return
        rec = data["rec"]
        # Required shape
        for k in ("tmdb_id", "name", "poster_url", "first_air_date", "vote_average", "overview", "seed_name"):
            assert k in rec, f"missing key {k}: {rec}"
        assert isinstance(rec["tmdb_id"], int)
        assert isinstance(rec["name"], str) and rec["name"]
        assert rec["poster_url"].startswith("http"), rec["poster_url"]
        assert rec["seed_name"]  # should reference Breaking Bad as seed

    def test_pro_user_also_works(self, admin_headers):
        """Spec: BOTH free and pro can hit this endpoint."""
        r = requests.get(f"{BASE_URL}/api/ai/preview_rec",
                         headers=admin_headers, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # Admin may or may not have library — both shapes valid
        assert "rec" in data


# ============================================================
# 2. POST /api/import/trakt
# ============================================================
TRAKT_LIST_JSON = [
    {"show": {"title": "Severance", "year": 2022, "ids": {"tmdb": 95396}, "status": "watching"}},
    {"show": {"title": "The Bear", "year": 2022}},  # no tmdb id — should match via search
    {"show": {"title": "NonexistentShow999XYZQ", "year": 2099}},  # should not be found
]

TRAKT_WRAPPED_JSON = {
    "shows": [
        {"show": {"title": "Ted Lasso", "year": 2020, "ids": {"tmdb": 97546}}},
        {"show": {"title": "The Boys", "year": 2019, "ids": {"tmdb": 76479}}},
    ]
}

TRAKT_CSV = "Title,Year,Tmdb\nSeverance,2022,95396\nThe Bear,2022,\n"


class TestImportTrakt:

    def test_unauthenticated_returns_401(self):
        files = {"file": ("a.json", json.dumps(TRAKT_LIST_JSON), "application/json")}
        r = requests.post(f"{BASE_URL}/api/import/trakt", files=files, timeout=30)
        assert r.status_code == 401

    def test_empty_file_returns_400(self, admin_headers):
        files = {"file": ("empty.json", "", "application/json")}
        r = requests.post(f"{BASE_URL}/api/import/trakt",
                          files=files, headers=admin_headers, timeout=30)
        assert r.status_code == 400, r.text

    def test_invalid_json_returns_400(self, admin_headers):
        files = {"file": ("bad.json", "{not valid", "application/json")}
        r = requests.post(f"{BASE_URL}/api/import/trakt",
                          files=files, headers=admin_headers, timeout=30)
        assert r.status_code == 400, r.text

    def test_json_list_admin_pro(self, admin_headers, mongo_db):
        """Trakt JSON list — admin is Pro (no cap)."""
        # Clean: remove tmdb_ids 95396 + The Bear so add count is reproducible
        admin = mongo_db.users.find_one({"email": ADMIN_EMAIL})
        admin_uid = str(admin["_id"])
        mongo_db.library.delete_many({"user_id": admin_uid, "tmdb_id": {"$in": [95396, 1903, 96677]}})

        files = {"file": ("trakt.json", json.dumps(TRAKT_LIST_JSON), "application/json")}
        r = requests.post(f"{BASE_URL}/api/import/trakt",
                          files=files, headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("total", "added", "duplicates", "not_found", "not_found_count", "skipped_cap", "tier", "cap"):
            assert k in data, f"missing key {k}: {data}"
        assert data["total"] == 3
        assert data["tier"] == "pro"
        assert data["cap"] is None
        assert data["skipped_cap"] == 0  # Pro has no cap
        # Severance + The Bear should resolve; bogus title shouldn't.
        assert data["added"] >= 1, data
        assert data["not_found_count"] >= 1, data
        assert "NonexistentShow999XYZQ" in data["not_found"]

        # Verify Severance landed in admin's library (persistence check)
        sev = mongo_db.library.find_one({"user_id": admin_uid, "tmdb_id": 95396})
        assert sev is not None, "Severance was reported added but not in DB"
        assert sev.get("imported_from") == "trakt"
        # Cleanup
        mongo_db.library.delete_many({"user_id": admin_uid, "imported_from": "trakt"})

    def test_json_wrapped_shows(self, admin_headers, mongo_db):
        admin = mongo_db.users.find_one({"email": ADMIN_EMAIL})
        admin_uid = str(admin["_id"])
        mongo_db.library.delete_many({"user_id": admin_uid, "tmdb_id": {"$in": [97546, 76479]}})

        files = {"file": ("trakt_wrapped.json", json.dumps(TRAKT_WRAPPED_JSON), "application/json")}
        r = requests.post(f"{BASE_URL}/api/import/trakt",
                          files=files, headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 2
        assert data["added"] >= 1, data  # at least one should resolve via TMDB

        # Cleanup imported items
        mongo_db.library.delete_many({"user_id": admin_uid, "imported_from": "trakt"})

    def test_csv_admin_pro(self, admin_headers, mongo_db):
        admin = mongo_db.users.find_one({"email": ADMIN_EMAIL})
        admin_uid = str(admin["_id"])
        mongo_db.library.delete_many({"user_id": admin_uid, "tmdb_id": {"$in": [95396]}})

        files = {"file": ("export.csv", TRAKT_CSV, "text/csv")}
        r = requests.post(f"{BASE_URL}/api/import/trakt",
                          files=files, headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total"] == 2
        assert data["tier"] == "pro"
        assert data["added"] >= 1, data
        # Cleanup
        mongo_db.library.delete_many({"user_id": admin_uid, "imported_from": "trakt"})

    def test_free_user_cap_enforced(self, free_user, mongo_db):
        """Free user: pre-fill library to FREE_CAP-1, then import 5 items. skipped_cap must >=1."""
        uid = free_user["user_id"]
        # Remove any existing items first
        mongo_db.library.delete_many({"user_id": uid})

        # Fast-forward: insert 49 dummy library docs directly (not 50, so 1 can succeed first)
        import datetime as _dt
        now = _dt.datetime.now(_dt.timezone.utc).isoformat()
        dummies = [{
            "user_id": uid,
            "tmdb_id": 900000 + i,
            "name": f"DUMMY {i}",
            "status": "want",
            "poster_url": None, "backdrop_url": None, "overview": "",
            "added_at": now, "updated_at": now,
        } for i in range(49)]
        mongo_db.library.insert_many(dummies)

        # Import 3 popular shows by tmdb_id — only the first should be added (50th slot), rest skipped
        import_payload = [
            {"show": {"title": "Severance", "year": 2022, "ids": {"tmdb": 95396}}},
            {"show": {"title": "Ted Lasso", "year": 2020, "ids": {"tmdb": 97546}}},
            {"show": {"title": "The Boys", "year": 2019, "ids": {"tmdb": 76479}}},
        ]
        files = {"file": ("trakt.json", json.dumps(import_payload), "application/json")}
        r = requests.post(f"{BASE_URL}/api/import/trakt",
                          files=files, headers=free_user["headers"], timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "free"
        assert data["cap"] == FREE_CAP
        assert data["added"] == 1, f"expected exactly 1 added (cap fill), got {data}"
        assert data["skipped_cap"] >= 2, f"expected skipped_cap>=2, got {data}"

        # Cleanup
        mongo_db.library.delete_many({"user_id": uid})

    def test_duplicates_detected(self, admin_headers, mongo_db):
        """Importing the same Trakt list twice should yield duplicates>0 on the 2nd run."""
        admin = mongo_db.users.find_one({"email": ADMIN_EMAIL})
        admin_uid = str(admin["_id"])
        mongo_db.library.delete_many({"user_id": admin_uid, "tmdb_id": 95396})

        payload = [{"show": {"title": "Severance", "year": 2022, "ids": {"tmdb": 95396}}}]
        files1 = {"file": ("t.json", json.dumps(payload), "application/json")}
        r1 = requests.post(f"{BASE_URL}/api/import/trakt", files=files1,
                           headers=admin_headers, timeout=30)
        assert r1.status_code == 200
        assert r1.json()["added"] == 1

        # Second time — same payload
        files2 = {"file": ("t.json", json.dumps(payload), "application/json")}
        r2 = requests.post(f"{BASE_URL}/api/import/trakt", files=files2,
                           headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["duplicates"] == 1, d2
        assert d2["added"] == 0

        # Cleanup
        mongo_db.library.delete_many({"user_id": admin_uid, "imported_from": "trakt"})


# ============================================================
# 3. GET /api/calendar/ical
# ============================================================
class TestCalendarICal:
    """text/calendar feed with auth via header OR ?token= query."""

    def test_unauthenticated_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/calendar/ical", timeout=15)
        assert r.status_code == 401

    def test_invalid_token_query_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/calendar/ical?token=clearlyNotAValidJwt", timeout=15)
        assert r.status_code == 401

    def test_admin_via_authorization_header(self, admin_headers, mongo_db):
        # Ensure admin has at least 1 library item so we get >=1 VEVENT
        admin = mongo_db.users.find_one({"email": ADMIN_EMAIL})
        admin_uid = str(admin["_id"])
        if mongo_db.library.count_documents({"user_id": admin_uid}) == 0:
            # Add Breaking Bad via API
            requests.post(f"{BASE_URL}/api/library",
                          json={"tmdb_id": 1396, "status": "watching"},
                          headers={**admin_headers, "Content-Type": "application/json"}, timeout=30)

        r = requests.get(f"{BASE_URL}/api/calendar/ical",
                         headers=admin_headers, timeout=45)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "").lower()
        assert "text/calendar" in ct, f"unexpected content-type: {ct}"
        cd = r.headers.get("content-disposition", "").lower()
        assert "attachment" in cd and "seriestrack.ics" in cd, cd

        body = r.text
        assert body.startswith("BEGIN:VCALENDAR"), body[:80]
        assert "END:VCALENDAR" in body
        # Should have at least one VEVENT (admin lib has Breaking Bad which has aired)
        # Note: BB finished, so only last_episode_to_air will yield one event.
        if "BEGIN:VEVENT" in body:
            assert "DTSTART;VALUE=DATE:" in body
            assert "END:VEVENT" in body

    def test_admin_via_token_query(self, admin_token):
        """Calendar apps subscribe via URL — must accept ?token=."""
        r = requests.get(f"{BASE_URL}/api/calendar/ical",
                         params={"token": admin_token}, timeout=45)
        assert r.status_code == 200, r.text
        assert "text/calendar" in r.headers.get("content-type", "").lower()
        assert r.text.startswith("BEGIN:VCALENDAR")
        assert "END:VCALENDAR" in r.text

    def test_free_user_with_library_works(self, free_user, mongo_db):
        uid = free_user["user_id"]
        # Ensure at least 1 lib item
        if mongo_db.library.count_documents({"user_id": uid}) == 0:
            requests.post(f"{BASE_URL}/api/library",
                          json={"tmdb_id": 1396, "status": "watching"},
                          headers={**free_user["headers"], "Content-Type": "application/json"}, timeout=30)
        r = requests.get(f"{BASE_URL}/api/calendar/ical",
                         headers=free_user["headers"], timeout=45)
        assert r.status_code == 200
        assert r.text.startswith("BEGIN:VCALENDAR")
