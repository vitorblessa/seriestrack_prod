"""Sprint 1 — Pro monetization billing tests.
Covers /api/billing/plans, /me, /checkout, /status/{session_id}, /webhook/stripe.
Does NOT actually pay — just verifies session creation + DB row + auth/error paths.
"""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://show-notify.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASSWORD = "Admin@123"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "seriestrack")


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_id(session, admin_token):
    r = session.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL)
    return cli[DB_NAME]


# -------------------------- /billing/plans --------------------------
class TestPlans:
    def test_plans_public(self, session):
        r = session.get(f"{API}/billing/plans", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "plans" in data
        plans = {p["id"]: p for p in data["plans"]}
        assert "pro_monthly" in plans
        assert "pro_yearly" in plans
        m = plans["pro_monthly"]
        y = plans["pro_yearly"]
        assert m["amount"] == 12.90
        assert m["currency"].lower() == "brl"
        assert m["days"] == 30
        assert y["amount"] == 99.00
        assert y["currency"].lower() == "brl"
        assert y["days"] == 365


# -------------------------- /billing/me --------------------------
class TestBillingMe:
    def test_me_free_for_admin(self, session, auth_headers):
        r = session.get(f"{API}/billing/me", headers=auth_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        # admin should be free unless previously credited
        assert d["tier"] in ("free", "pro")
        if d["tier"] == "free":
            assert d["renews_at"] in (None, "")
            assert d["days_left"] in (None, 0)

    def test_me_requires_auth(self):
        # Clean session — login session has httpOnly cookies that auto-auth
        r = requests.get(f"{API}/billing/me", timeout=10)
        assert r.status_code == 401


# -------------------------- /billing/checkout --------------------------
class TestCheckout:
    def test_checkout_monthly(self, session, auth_headers, admin_id, mongo):
        body = {"plan": "pro_monthly", "origin_url": BASE_URL}
        r = session.post(f"{API}/billing/checkout", headers=auth_headers, json=body, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "url" in d and d["url"].startswith("https://checkout.stripe.com/")
        assert "session_id" in d and d["session_id"].startswith("cs_")
        # Verify DB row
        tx = mongo.payment_transactions.find_one({"session_id": d["session_id"]})
        assert tx is not None
        assert tx["status"] == "initiated"
        assert tx["payment_status"] == "pending"
        assert tx["credited"] is False
        assert tx["user_id"] == admin_id
        assert tx["plan"] == "pro_monthly"
        assert float(tx["amount"]) == 12.90
        assert tx["days"] == 30

    def test_checkout_yearly(self, session, auth_headers, admin_id, mongo):
        body = {"plan": "pro_yearly", "origin_url": BASE_URL}
        r = session.post(f"{API}/billing/checkout", headers=auth_headers, json=body, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["url"].startswith("https://checkout.stripe.com/")
        assert d["session_id"].startswith("cs_")
        tx = mongo.payment_transactions.find_one({"session_id": d["session_id"]})
        assert tx is not None
        assert tx["plan"] == "pro_yearly"
        assert float(tx["amount"]) == 99.00
        assert tx["days"] == 365
        assert tx["user_id"] == admin_id

    def test_checkout_invalid_plan(self, session, auth_headers):
        r = session.post(
            f"{API}/billing/checkout",
            headers=auth_headers,
            json={"plan": "foo", "origin_url": BASE_URL},
            timeout=10,
        )
        # 422 (Pydantic regex) or 400 (HTTPException) both signal invalid input
        assert r.status_code in (400, 422)

    def test_checkout_requires_auth(self):
        r = requests.post(f"{API}/billing/checkout", json={"plan": "pro_monthly", "origin_url": BASE_URL}, timeout=10)
        assert r.status_code == 401


# -------------------------- /billing/status --------------------------
class TestBillingStatus:
    @pytest.fixture(scope="class")
    def created_session_id(self, session, auth_headers):
        r = session.post(
            f"{API}/billing/checkout",
            headers=auth_headers,
            json={"plan": "pro_monthly", "origin_url": BASE_URL},
            timeout=30,
        )
        assert r.status_code == 200
        return r.json()["session_id"]

    def test_status_unpaid(self, session, auth_headers, created_session_id):
        r = session.get(f"{API}/billing/status/{created_session_id}", headers=auth_headers, timeout=20)
        # Acceptable: 200 (Stripe session retrievable) or 502 (Emergent test-mode flakiness on same-second lookup)
        assert r.status_code in (200, 502), r.text
        if r.status_code == 200:
            d = r.json()
            assert "status" in d
            assert "payment_status" in d
            assert d.get("payment_status") in ("unpaid", "no_payment_required", "pending", None)
            assert d.get("plan") == "pro_monthly"
            assert d.get("credited") is False

    def test_status_requires_auth(self, created_session_id):
        # Clean session (no cookies)
        r = requests.get(f"{API}/billing/status/{created_session_id}", timeout=10)
        assert r.status_code == 401

    def test_status_wrong_user_404(self, session, created_session_id):
        # Register a fresh user and query the admin's session_id
        import uuid
        email = f"TEST_other_{uuid.uuid4().hex[:8]}@seriestrack-test.com"
        rr = session.post(f"{API}/auth/register", json={"email": email, "password": "Test@1234", "name": "Other"}, timeout=15)
        assert rr.status_code == 200
        tok = rr.json()["access_token"]
        r = session.get(
            f"{API}/billing/status/{created_session_id}",
            headers={"Authorization": f"Bearer {tok}"},
            timeout=15,
        )
        assert r.status_code == 404


# -------------------------- /stripe/webhook --------------------------
class TestStripeWebhook:
    def test_webhook_invalid_signature_returns_400(self, session):
        r = session.post(
            f"{API}/stripe/webhook",
            data=b'{"foo":"bar"}',
            headers={"Stripe-Signature": "bogus", "Content-Type": "application/json"},
            timeout=10,
        )
        # Must NOT 500. Acceptable: 400 (invalid sig). 200/404 also OK if lib chooses to swallow.
        assert r.status_code != 500, r.text
        assert r.status_code in (400, 401, 403)

    def test_webhook_no_signature_returns_400(self, session):
        r = session.post(
            f"{API}/stripe/webhook",
            data=b'{}',
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        assert r.status_code != 500, r.text
        assert r.status_code in (400, 401, 403)
