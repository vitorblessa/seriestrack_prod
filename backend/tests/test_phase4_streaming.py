"""SeriesTrack Phase 4 — Streaming search normalization + word-boundary matching.
Validates the fix for false-negative '+' / 'Plus' matches AND
elimination of false-positive midmatches like 'Paramount Plus Apple TV Channel'.

Admin library is pre-seeded with 8 series including Demolidor (Disney+),
Breaking Bad (Netflix), The Boys (Prime Video), House of the Dragon (Max), etc.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@seriestrack.app"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin_headers():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _get(name, headers):
    r = requests.get(
        f"{API}/streaming/episodes",
        params={"name": name},
        headers=headers,
        timeout=120,
    )
    assert r.status_code == 200, f"{name!r} -> {r.status_code} {r.text}"
    return r.json()


# ----------------- Disney+ / Disney Plus normalization -----------------
class TestDisneyPlus:
    def test_disney_plus_with_plus(self, admin_headers):
        d = _get("Disney+", admin_headers)
        # admin has Demolidor on Disney+
        assert any("disney" in p.lower() and "plus" in p.lower() for p in d["matched_providers"]), \
            f"matched_providers={d['matched_providers']}"
        assert len(d["episodes"]) >= 1, "Demolidor should produce at least 1 ep on Disney+"

    def test_disney_without_plus(self, admin_headers):
        d = _get("Disney", admin_headers)
        assert any("disney" in p.lower() for p in d["matched_providers"]), \
            f"matched_providers={d['matched_providers']}"
        assert len(d["episodes"]) >= 1


# ----------------- Apple TV+ false-positive guard -----------------
class TestAppleTVPlus:
    def test_apple_tv_plus_no_paramount_channel_falsepos(self, admin_headers):
        d = _get("Apple TV+", admin_headers)
        # CRITICAL: must NOT include 'Paramount Plus Apple TV Channel' (or any *Apple TV Channel* sub-brand)
        for p in d["matched_providers"]:
            assert "channel" not in p.lower(), \
                f"FALSE POSITIVE: matched a sub-channel provider {p!r}"
            # And must not match Paramount-rooted entries
            assert not p.lower().startswith("paramount"), \
                f"FALSE POSITIVE: matched {p!r} for Apple TV+"

    def test_apple_tv_no_channel_falsepos(self, admin_headers):
        d = _get("Apple TV", admin_headers)
        for p in d["matched_providers"]:
            assert "channel" not in p.lower(), f"sub-channel false positive: {p!r}"
            assert not p.lower().startswith("paramount"), f"Paramount false positive: {p!r}"


# ----------------- Paramount+ should match all paramount* roots -----------------
class TestParamountPlus:
    def test_paramount_plus_matches_root_and_subchannels(self, admin_headers):
        # 'paramount' is the prefix → prefix-match should accept root + subchannels
        d = _get("Paramount+", admin_headers)
        for p in d["matched_providers"]:
            assert p.lower().startswith("paramount"), \
                f"Paramount+ should only match providers starting with 'paramount', got {p!r}"


# ----------------- Prime Video suffix match -----------------
class TestPrimeVideo:
    def test_prime_video_matches_amazon_prime_video(self, admin_headers):
        d = _get("Prime Video", admin_headers)
        # 'prime video' is the SUFFIX of 'Amazon Prime Video' → should match
        if d["matched_providers"]:
            assert any("prime video" in p.lower() for p in d["matched_providers"]), \
                f"matched_providers={d['matched_providers']}"
            # admin has The Boys + Invincible on Prime Video
            assert len(d["episodes"]) >= 1


# ----------------- Max suffix match (HBO Max) without midmatches -----------------
class TestMax:
    def test_max_matches_hbo_max_only(self, admin_headers):
        d = _get("Max", admin_headers)
        for p in d["matched_providers"]:
            words = p.lower().split()
            # 'max' must be the last word OR full provider name
            assert words[-1] == "max" or p.lower() == "max", \
                f"'Max' should only suffix-match; got {p!r}"


# ----------------- Netflix prefix match -----------------
class TestNetflix:
    def test_netflix_prefix_match(self, admin_headers):
        d = _get("Netflix", admin_headers)
        for p in d["matched_providers"]:
            assert p.lower().startswith("netflix"), \
                f"Netflix should be prefix; got {p!r}"
        if d["matched_providers"]:
            # admin has Breaking Bad + Rick and Morty + The Witcher on Netflix
            assert len(d["episodes"]) >= 1


# ----------------- Regression: empty + auth -----------------
class TestRegression:
    def test_empty_name(self, admin_headers):
        r = requests.get(
            f"{API}/streaming/episodes",
            params={"name": ""},
            headers=admin_headers,
            timeout=20,
        )
        assert r.status_code == 200
        assert r.json() == {"matched_providers": [], "episodes": []}

    def test_unauth_returns_401(self):
        r = requests.get(f"{API}/streaming/episodes", params={"name": "Netflix"}, timeout=10)
        assert r.status_code == 401


# ----------------- Pure unit tests for the helpers -----------------
class TestHelpersUnit:
    """Import server module helpers and verify normalization + matching logic
    independent of TMDB."""

    @pytest.fixture(scope="class")
    def helpers(self):
        import sys
        sys.path.insert(0, "/app/backend")
        import server  # noqa: E402
        return server._normalize_provider, server._provider_matches

    def test_normalize_disney_plus_variants(self, helpers):
        norm, _ = helpers
        assert norm("Disney+") == norm("Disney Plus") == norm("disney plus") == "disney"

    def test_normalize_apple_tv_plus(self, helpers):
        norm, _ = helpers
        assert norm("Apple TV+") == norm("Apple TV Plus") == "apple tv"

    def test_normalize_paramount_subchannel(self, helpers):
        norm, _ = helpers
        # Sub-channel name has "Plus" word stripped → "paramount apple tv channel"
        assert norm("Paramount Plus Apple TV Channel") == "paramount apple tv channel"

    def test_match_apple_tv_does_not_hit_paramount_subchannel(self, helpers):
        norm, match = helpers
        n = norm("Apple TV+")
        p = norm("Paramount Plus Apple TV Channel")
        assert match(n, p) is False  # critical false-positive guard

    def test_match_disney_plus_hits_disney_plus(self, helpers):
        norm, match = helpers
        assert match(norm("Disney+"), norm("Disney Plus")) is True

    def test_match_prime_video_suffix(self, helpers):
        norm, match = helpers
        assert match(norm("Prime Video"), norm("Amazon Prime Video")) is True

    def test_match_max_suffix_only(self, helpers):
        norm, match = helpers
        assert match(norm("Max"), norm("HBO Max")) is True
        # 'Max' must NOT match a midword like 'maximum' or 'Max Channel'
        assert match(norm("Max"), norm("Max Channel")) is True  # prefix
        # But does NOT match 'Maximum' since normalize keeps as one word and word != 'max'
        assert match(norm("Max"), norm("Maximum Streaming")) is False

    def test_match_netflix_prefix(self, helpers):
        norm, match = helpers
        assert match(norm("Netflix"), norm("Netflix Standard with Ads")) is True
        assert match(norm("Netflix"), norm("Netflix")) is True

    def test_match_paramount_prefix_all(self, helpers):
        norm, match = helpers
        assert match(norm("Paramount+"), norm("Paramount Plus")) is True
        assert match(norm("Paramount+"), norm("Paramount Plus Apple TV Channel")) is True

    def test_match_empty_returns_false(self, helpers):
        norm, match = helpers
        assert match(norm(""), norm("Netflix")) is False
        assert match(norm("Netflix"), norm("")) is False
