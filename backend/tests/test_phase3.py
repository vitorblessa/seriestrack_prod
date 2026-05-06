"""SeriesTrack Phase 3 — Google OAuth race fix + Streaming search.
Covers:
- POST /api/auth/google with bogus session_id must return 401 (not 500/502)
- GET /api/streaming/episodes?name=<provider> (admin-authed) returns matched_providers + sorted episodes
- name='' returns empty result
- Unauthenticated call returns 401
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    d = r.json()
    return {
        "token": d["access_token"],
        "id": d["user"]["id"],
        "headers": {"Authorization": f"Bearer {d['access_token']}", "Content-Type": "application/json"},
    }


# ---------------- Google OAuth race — backend negative path ----------------
class TestGoogleAuthNegative:
    def test_bogus_session_returns_401_strict(self):
        r = requests.post(
            f"{API}/auth/google",
            json={"session_id": "invalid-test-id"},
            timeout=30,
        )
        assert r.status_code != 500, f"crashed 500: {r.text}"
        assert r.status_code != 502, f"gateway 502 (broad except masks real error): {r.text}"
        assert r.status_code == 401, f"expected 401 got {r.status_code}: {r.text}"
        body = r.json()
        # detail may be 'Invalid Google session' or similar
        assert "detail" in body or "message" in body

    def test_random_session_id(self):
        r = requests.post(
            f"{API}/auth/google",
            json={"session_id": "bogus-" + uuid.uuid4().hex},
            timeout=30,
        )
        assert r.status_code != 500
        # Allow 401 or 502 (per iteration 2 notes) — but 500 is forbidden
        assert r.status_code in (401, 502)


# ---------------- Streaming search endpoint ----------------
class TestStreamingSearch:
    def test_requires_auth(self):
        r = requests.get(f"{API}/streaming/episodes", params={"name": "Netflix"}, timeout=20)
        assert r.status_code == 401

    def test_missing_name_is_422(self, admin):
        # name is a required query param -> 422 without it
        r = requests.get(f"{API}/streaming/episodes", headers=admin["headers"], timeout=15)
        assert r.status_code == 422

    def test_empty_name_returns_empty(self, admin):
        r = requests.get(
            f"{API}/streaming/episodes",
            params={"name": ""},
            headers=admin["headers"],
            timeout=30,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d == {"matched_providers": [], "episodes": []}

    def test_whitespace_name_returns_empty(self, admin):
        r = requests.get(
            f"{API}/streaming/episodes",
            params={"name": "   "},
            headers=admin["headers"],
            timeout=30,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["matched_providers"] == []
        assert d["episodes"] == []

    @pytest.mark.parametrize("provider_name", ["Netflix", "Prime Video", "Disney Plus", "HBO Max", "Apple TV"])
    def test_provider_search(self, admin, provider_name):
        r = requests.get(
            f"{API}/streaming/episodes",
            params={"name": provider_name},
            headers=admin["headers"],
            timeout=90,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert "matched_providers" in d and isinstance(d["matched_providers"], list)
        assert "episodes" in d and isinstance(d["episodes"], list)

        # Validate episode shape if any
        for ep in d["episodes"]:
            for k in ("tmdb_id", "series_name", "season_number", "episode_number",
                      "air_date", "kind", "providers", "matched_providers"):
                assert k in ep, f"missing {k} in episode for {provider_name}: {ep}"
            assert ep["kind"] in ("upcoming", "recent")
            # Matched providers for the episode should contain the needle (case-insensitive)
            assert any(provider_name.lower() in p.lower() for p in ep["matched_providers"]), \
                f"episode for {provider_name} has matched_providers={ep['matched_providers']}"

        # Verify sort desc by air_date
        dates = [ep["air_date"] for ep in d["episodes"] if ep.get("air_date")]
        assert dates == sorted(dates, reverse=True), f"not sorted desc for {provider_name}: {dates}"

    def test_netflix_returns_episodes_for_admin(self, admin):
        """Admin library is pre-populated; Netflix should return at least some episodes."""
        r = requests.get(
            f"{API}/streaming/episodes",
            params={"name": "Netflix"},
            headers=admin["headers"],
            timeout=90,
        )
        assert r.status_code == 200
        d = r.json()
        # Admin has series with Netflix availability (BR/US)
        # We don't hard-assert >0 because TMDB provider data can fluctuate by region,
        # but if matched_providers is non-empty then episodes should be non-empty.
        if d["matched_providers"]:
            # All matched providers include 'netflix'
            for mp in d["matched_providers"]:
                assert "netflix" in mp.lower()
            assert len(d["episodes"]) >= 1
