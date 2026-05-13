"""Backend tests for new features: UI themes + Wrapped 2026."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://show-notify.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASS = "Admin@123"

EXPECTED_PRO_THEMES = {
    "oled", "netflix", "disney_plus", "hbo_max",
    "prime_video", "apple_tv", "paramount_plus", "globoplay",
}
EXPECTED_FREE_THEMES = {"default"}


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_id(admin_token):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(scope="module")
def free_token():
    email = f"TEST_free_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={
        "email": email, "password": "FreeTest@123", "name": "TEST Free"
    })
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


# ---------- /api/me/preferences ----------
class TestPreferencesGet:
    def test_unauth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/me/preferences")
        assert r.status_code in (401, 403)

    def test_admin_preferences_shape(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/me/preferences",
                         headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "preferences" in data and "ui_theme" in data["preferences"]
        assert set(data["free_themes"]) == EXPECTED_FREE_THEMES
        assert set(data["pro_themes"]) == EXPECTED_PRO_THEMES
        assert set(data["available_themes"]) == EXPECTED_FREE_THEMES | EXPECTED_PRO_THEMES
        assert len(data["available_themes"]) == 9
        assert data["tier"] == "pro"

    def test_free_user_tier(self, free_token):
        r = requests.get(f"{BASE_URL}/api/me/preferences",
                         headers={"Authorization": f"Bearer {free_token}"})
        assert r.status_code == 200
        assert r.json()["tier"] == "free"


class TestPreferencesPatch:
    def test_free_user_cannot_set_pro_theme(self, free_token):
        r = requests.patch(f"{BASE_URL}/api/me/preferences",
                           headers={"Authorization": f"Bearer {free_token}"},
                           json={"ui_theme": "netflix"})
        assert r.status_code == 402
        body = r.json()
        detail = body.get("detail")
        assert isinstance(detail, dict)
        assert detail.get("code") == "pro_theme_required"

    def test_free_user_can_set_default(self, free_token):
        r = requests.patch(f"{BASE_URL}/api/me/preferences",
                           headers={"Authorization": f"Bearer {free_token}"},
                           json={"ui_theme": "default"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_unknown_theme_400(self, admin_token):
        r = requests.patch(f"{BASE_URL}/api/me/preferences",
                           headers={"Authorization": f"Bearer {admin_token}"},
                           json={"ui_theme": "not_a_theme"})
        assert r.status_code == 400

    @pytest.mark.parametrize("theme", ["netflix", "oled", "disney_plus", "globoplay"])
    def test_admin_can_set_pro_themes(self, admin_token, theme):
        r = requests.patch(f"{BASE_URL}/api/me/preferences",
                           headers={"Authorization": f"Bearer {admin_token}"},
                           json={"ui_theme": theme})
        assert r.status_code == 200, f"theme {theme}: {r.text}"
        # Verify persistence via GET
        g = requests.get(f"{BASE_URL}/api/me/preferences",
                         headers={"Authorization": f"Bearer {admin_token}"})
        assert g.status_code == 200
        assert g.json()["preferences"]["ui_theme"] == theme

    def test_reset_admin_to_default(self, admin_token):
        # Cleanup so admin stays on default for UI tests
        r = requests.patch(f"{BASE_URL}/api/me/preferences",
                           headers={"Authorization": f"Bearer {admin_token}"},
                           json={"ui_theme": "default"})
        assert r.status_code == 200


# ---------- /api/wrapped/{year} ----------
class TestWrapped:
    def test_unauth_401(self):
        r = requests.get(f"{BASE_URL}/api/wrapped/2026")
        assert r.status_code in (401, 403)

    def test_invalid_year_low(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/wrapped/1999",
                         headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 400

    def test_invalid_year_high(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/wrapped/2100",
                         headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 400

    def test_admin_wrapped_2026_shape(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/wrapped/2026",
                         headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        d = r.json()
        assert d["year"] == 2026
        # Admin is supposed to have progress per main agent
        if d.get("empty"):
            pytest.skip("Admin has no progress for 2026 — empty wrapped")
        assert d["empty"] is False
        totals = d["totals"]
        for k in ("episodes", "estimated_hours", "estimated_days",
                  "unique_series", "library_size", "library_breakdown"):
            assert k in totals
        assert isinstance(d["top_series"], list)
        if d["top_series"]:
            ts = d["top_series"][0]
            for k in ("tmdb_id", "name", "episodes", "estimated_hours"):
                assert k in ts
        assert "top_day_of_week" in d
        assert "label" in d["top_day_of_week"] and "iso_day" in d["top_day_of_week"]
        assert "top_month" in d
        assert "label" in d["top_month"] and "number" in d["top_month"]
        assert "longest_streak_days" in d
        assert "biggest_binge" in d
        assert "first_episode" in d and "last_episode" in d
        assert "reviews" in d and "count" in d["reviews"]

    def test_free_user_empty_wrapped(self, free_token):
        r = requests.get(f"{BASE_URL}/api/wrapped/2026",
                         headers={"Authorization": f"Bearer {free_token}"})
        assert r.status_code == 200
        d = r.json()
        assert d.get("empty") is True
        assert "message" in d


class TestWrappedShare:
    def test_public_endpoint_no_auth(self, admin_id):
        r = requests.get(f"{BASE_URL}/api/wrapped/2026/share/{admin_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["year"] == 2026
        assert "user" in d
        assert d["user"]["id"] == admin_id
        assert "name" in d["user"]

    def test_public_invalid_user(self):
        r = requests.get(f"{BASE_URL}/api/wrapped/2026/share/507f1f77bcf86cd799439011")
        assert r.status_code == 404

    def test_public_malformed_user_id(self):
        r = requests.get(f"{BASE_URL}/api/wrapped/2026/share/not_an_object_id")
        assert r.status_code == 404

    def test_public_invalid_year(self, admin_id):
        r = requests.get(f"{BASE_URL}/api/wrapped/1999/share/{admin_id}")
        assert r.status_code == 400
