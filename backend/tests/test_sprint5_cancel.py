"""Sprint 5 — In-app subscription cancel/reactivate."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture()
def free_token():
    """Ephemeral Free-tier user — does NOT have a Pro subscription."""
    email = f"canceltest+{int(time.time()*1000)}@seriestrack.app"
    r = requests.post(f"{BASE_URL}/api/auth/register",
                      json={"email": email, "password": "Test@1234", "name": "Cancel Free"}, timeout=15)
    assert r.status_code == 200
    return r.json()["access_token"]


class TestSubscriptionCancel:
    def test_billing_me_includes_auto_renew_for_pro(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/billing/me",
                         headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["tier"] == "pro"
        assert "auto_renew" in data
        assert "cancel_pending" in data
        assert isinstance(data["auto_renew"], bool)
        assert isinstance(data["cancel_pending"], bool)

    def test_cancel_then_reactivate_round_trip(self, admin_token):
        # Cancel
        r = requests.post(f"{BASE_URL}/api/billing/cancel",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["auto_renew"] is False

        # Verify
        r2 = requests.get(f"{BASE_URL}/api/billing/me",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r2.json()["cancel_pending"] is True
        assert r2.json()["auto_renew"] is False
        # Still Pro until renews_at
        assert r2.json()["tier"] == "pro"

        # Reactivate
        r3 = requests.post(f"{BASE_URL}/api/billing/reactivate",
                           headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r3.status_code == 200
        assert r3.json()["auto_renew"] is True

        r4 = requests.get(f"{BASE_URL}/api/billing/me",
                          headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r4.json()["cancel_pending"] is False
        assert r4.json()["auto_renew"] is True

    def test_cancel_idempotent(self, admin_token):
        r1 = requests.post(f"{BASE_URL}/api/billing/cancel",
                           headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        r2 = requests.post(f"{BASE_URL}/api/billing/cancel",
                           headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Cleanup — restore
        requests.post(f"{BASE_URL}/api/billing/reactivate",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)

    def test_cancel_rejected_for_free_user(self, free_token):
        r = requests.post(f"{BASE_URL}/api/billing/cancel",
                          headers={"Authorization": f"Bearer {free_token}"}, timeout=15)
        assert r.status_code == 400
        assert "Pro" in r.json()["detail"]

    def test_reactivate_rejected_for_free_user(self, free_token):
        r = requests.post(f"{BASE_URL}/api/billing/reactivate",
                          headers={"Authorization": f"Bearer {free_token}"}, timeout=15)
        assert r.status_code == 400

    def test_endpoints_require_auth(self):
        assert requests.post(f"{BASE_URL}/api/billing/cancel", timeout=15).status_code == 401
        assert requests.post(f"{BASE_URL}/api/billing/reactivate", timeout=15).status_code == 401

    def test_free_user_billing_me_has_no_auto_renew(self, free_token):
        r = requests.get(f"{BASE_URL}/api/billing/me",
                         headers={"Authorization": f"Bearer {free_token}"}, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert data["tier"] == "free"
        assert data["auto_renew"] is None
        assert data["cancel_pending"] is False
