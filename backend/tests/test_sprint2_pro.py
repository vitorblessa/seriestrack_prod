"""Sprint 2 Pro monetization tests: /limits, library cap, /ai/recommendations, /stats/advanced.

Admin is currently Pro. For free-tier tests we register a fresh user. For library-cap test we
insert 50 library docs directly via motor to avoid burning TMDB/LLM quota.
"""
import os
import time
import uuid
import asyncio
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://show-notify.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "seriestrack")

ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASSWORD = "Admin@123"


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="module")
def mongo_db():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def free_user():
    """Register an ephemeral free-tier user; cleanup library + user afterwards."""
    email = f"TEST_sprint2_{uuid.uuid4().hex[:10]}@seriestrack-test.com"
    pwd = "FreeUser@123"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": pwd, "name": "Free User"}, timeout=20)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    user_id = r.json()["user"]["id"]
    yield {"email": email, "token": token, "user_id": user_id, "headers": {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}}
    # Cleanup
    try:
        cli = MongoClient(MONGO_URL)
        db = cli[DB_NAME]
        db.library.delete_many({"user_id": user_id})
        db.users.delete_one({"email": email})
        cli.close()
    except Exception:
        pass


# ------------------ /api/limits ------------------
class TestLimits:
    def test_limits_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/limits", timeout=15)
        assert r.status_code == 401

    def test_limits_admin_pro(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/limits", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "pro"
        assert "library" in data
        lib = data["library"]
        assert lib["cap"] is None  # Pro has no cap
        assert lib["remaining"] is None
        assert isinstance(lib["used"], int) and lib["used"] >= 0

    def test_limits_free_user(self, free_user):
        r = requests.get(f"{BASE_URL}/api/limits", headers=free_user["headers"], timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["tier"] == "free"
        assert data["library"]["cap"] == 50
        assert data["library"]["used"] == 0
        assert data["library"]["remaining"] == 50


# --------------- Library cap enforcement ----------------
class TestLibraryCap:
    def test_free_user_blocked_at_51st(self, free_user, mongo_db):
        """Fast-forward: insert 50 library docs via motor, then attempt 51st via API."""
        user_id = free_user["user_id"]
        # Clean slate
        mongo_db.library.delete_many({"user_id": user_id})
        # Insert 50 fake series
        docs = []
        for i in range(50):
            docs.append({
                "user_id": user_id,
                "tmdb_id": 900000 + i,  # fake TMDB IDs in private range to avoid collisions
                "status": "want",
                "name": f"TEST Cap Series {i}",
                "poster_url": None,
                "backdrop_url": None,
                "overview": "",
                "added_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            })
        mongo_db.library.insert_many(docs)

        # limits should now show used=50, remaining=0
        r_lim = requests.get(f"{BASE_URL}/api/limits", headers=free_user["headers"], timeout=15)
        assert r_lim.status_code == 200
        assert r_lim.json()["library"]["used"] == 50
        assert r_lim.json()["library"]["remaining"] == 0

        # 51st must fail with 402 + library_cap_reached
        r = requests.post(
            f"{BASE_URL}/api/library",
            headers=free_user["headers"],
            json={"tmdb_id": 950001, "status": "want", "name": "TEST 51st", "poster_url": None},
            timeout=20,
        )
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text}"
        body = r.json()
        detail = body.get("detail", body)
        assert detail.get("code") == "library_cap_reached", detail
        assert detail.get("cap") == 50

    def test_free_user_can_update_existing(self, free_user, mongo_db):
        """Existing item can change status without hitting cap."""
        user_id = free_user["user_id"]
        # Use first of the 50 docs (tmdb_id=900000)
        r = requests.post(
            f"{BASE_URL}/api/library",
            headers=free_user["headers"],
            json={"tmdb_id": 900000, "status": "watching", "name": "TEST Cap Series 0"},
            timeout=20,
        )
        assert r.status_code == 200, f"update existing should succeed: {r.status_code} {r.text}"
        # Verify status persisted
        doc = mongo_db.library.find_one({"user_id": user_id, "tmdb_id": 900000})
        assert doc is not None and doc["status"] == "watching"

    def test_pro_admin_has_no_cap(self, admin_headers):
        """Admin is pro — GET /limits must show cap=null; we don't actually add items."""
        r = requests.get(f"{BASE_URL}/api/limits", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["library"]["cap"] is None


# ---------------- /api/stats/advanced ----------------
class TestAdvancedStats:
    def test_free_gets_402(self, free_user):
        r = requests.get(f"{BASE_URL}/api/stats/advanced", headers=free_user["headers"], timeout=20)
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text}"
        body = r.json()
        msg = body.get("detail", body)
        if isinstance(msg, dict):
            msg = msg.get("message", "") or str(msg)
        assert "pro" in str(msg).lower() or "subscription" in str(msg).lower()

    def test_pro_admin_gets_200_with_all_keys(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/stats/advanced", headers=admin_headers, timeout=45)
        assert r.status_code == 200, r.text
        d = r.json()
        required = [
            "total_episodes_watched", "estimated_hours", "estimated_days",
            "top_series", "top_genres", "heatmap", "library_breakdown",
            "top_months", "library_size",
        ]
        missing = [k for k in required if k not in d]
        assert not missing, f"missing keys: {missing}"
        assert isinstance(d["total_episodes_watched"], int)
        assert isinstance(d["top_series"], list)
        assert isinstance(d["top_genres"], list)
        assert isinstance(d["heatmap"], list)
        assert isinstance(d["library_breakdown"], dict)

    def test_no_auth_401(self):
        r = requests.get(f"{BASE_URL}/api/stats/advanced", timeout=15)
        assert r.status_code == 401


# -------------- /api/ai/recommendations --------------
class TestAIRecommendations:
    def test_free_gets_402(self, free_user):
        r = requests.post(f"{BASE_URL}/api/ai/recommendations", headers=free_user["headers"], timeout=30)
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text}"

    def test_no_auth_401(self):
        r = requests.post(f"{BASE_URL}/api/ai/recommendations", timeout=15)
        assert r.status_code == 401

    def test_pro_admin_returns_recs(self, admin_headers):
        start = time.time()
        r = requests.post(f"{BASE_URL}/api/ai/recommendations", headers=admin_headers, timeout=75)
        elapsed = time.time() - start
        print(f"\n[AI recs] elapsed={elapsed:.1f}s status={r.status_code}")
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:500]}"
        data = r.json()
        # If admin has no history, backend returns {recommendations:[], reason:'no_history'} — still 200.
        if data.get("reason") == "no_history":
            pytest.skip("admin has no library/reviews — cannot validate rec shape")
        assert "recommendations" in data
        assert data.get("model")  # now the configured Gemini model, not a fixed string
        recs = data["recommendations"]
        assert isinstance(recs, list)
        assert 1 <= len(recs) <= 5, f"expected up to 5 recs, got {len(recs)}"
        # Each rec has required keys
        for rec in recs:
            assert "tmdb_id" in rec
            assert "name" in rec
            assert "ai_why" in rec
            assert "in_library" in rec
        # P1 if >60s
        assert elapsed < 60, f"AI response took {elapsed:.1f}s (>60s P1)"


# -------------- Regression smoke --------------
class TestRegression:
    def test_auth_me(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_library_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/library", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_billing_plans_public(self):
        r = requests.get(f"{BASE_URL}/api/billing/plans", timeout=15)
        assert r.status_code == 200
        plans = r.json().get("plans", [])
        ids = {p.get("id") for p in plans}
        assert "pro_monthly" in ids and "pro_yearly" in ids

    def test_billing_me(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/billing/me", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["tier"] == "pro"

    def test_notifications(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/notifications", headers=admin_headers, timeout=15)
        assert r.status_code == 200

    def test_calendar(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/calendar/upcoming", headers=admin_headers, timeout=30)
        assert r.status_code == 200
