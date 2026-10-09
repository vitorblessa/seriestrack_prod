"""Tests for the new discovery endpoints (/series/genres, /series/discover)
added for the "Busca e descoberta melhores" roadmap item. These never hit
the real TMDB — the sandbox can't reach it anyway — so the TMDB HTTP client
is swapped for a fake one that serves canned responses by path.

Uses the same sys.modules['core.tmdb'] trick documented in conftest.py's
docstring: core/__init__.py's `from .tmdb import tmdb, ...` shadows the
`core.tmdb` package attribute with the function itself, so `import
core.tmdb` doesn't get you the submodule — you have to reach it through
sys.modules.
"""
import sys
import pytest

core_tmdb = sys.modules["core.tmdb"]


class _FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class _FakeTmdbClient:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append((path, params))
        if path in self.routes:
            return _FakeResponse(200, self.routes[path])
        return _FakeResponse(404, {})


@pytest.fixture(autouse=True)
def _clean_generic_cache():
    """tmdb_get_cached's cache is a plain module-level dict shared across the
    whole test session — clear it so one test's canned response doesn't leak
    into the next test's assertions."""
    core_tmdb._generic_cache.clear()
    yield
    core_tmdb._generic_cache.clear()


@pytest.fixture
def fake_tmdb(monkeypatch):
    genres_payload = {"genres": [{"id": 18, "name": "Drama"}, {"id": 35, "name": "Comédia"}]}
    discover_payload = {
        "results": [
            {"id": 1, "name": "Drama Show", "poster_path": None, "backdrop_path": None, "overview": "", "vote_average": 8.0, "first_air_date": "2024-01-01"},
            {"id": 2, "name": "Another Drama", "poster_path": None, "backdrop_path": None, "overview": "", "vote_average": 7.5, "first_air_date": "2023-01-01"},
        ]
    }
    client = _FakeTmdbClient({
        "/genre/tv/list": genres_payload,
        "/discover/tv": discover_payload,
    })

    async def fake_tmdb_factory():
        return client

    monkeypatch.setattr(core_tmdb, "tmdb", fake_tmdb_factory)
    return client


@pytest.mark.asyncio
async def test_genres_returns_tmdb_genre_list(client, fake_tmdb):
    r = await client.get("/api/series/genres")
    assert r.status_code == 200
    body = r.json()
    assert {"id": 18, "name": "Drama"} in body
    assert {"id": 35, "name": "Comédia"} in body


@pytest.mark.asyncio
async def test_discover_passes_genre_filter_to_tmdb(client, fake_tmdb):
    r = await client.get("/api/series/discover", params={"genre": 18})
    assert r.status_code == 200
    shows = r.json()
    assert len(shows) == 2
    assert {s["name"] for s in shows} == {"Drama Show", "Another Drama"}

    # Confirm the genre filter actually reached the TMDB request params
    discover_calls = [c for c in fake_tmdb.calls if c[0] == "/discover/tv"]
    assert discover_calls, "no /discover/tv call was made"
    assert discover_calls[-1][1]["with_genres"] == 18


@pytest.mark.asyncio
async def test_discover_rejects_unknown_sort_by_falls_back_to_popularity(client, fake_tmdb):
    r = await client.get("/api/series/discover", params={"sort_by": "not-a-real-sort"})
    assert r.status_code == 200
    discover_calls = [c for c in fake_tmdb.calls if c[0] == "/discover/tv"]
    assert discover_calls[-1][1]["sort_by"] == "popularity.desc"


@pytest.mark.asyncio
async def test_discover_without_genre_omits_with_genres_param(client, fake_tmdb):
    r = await client.get("/api/series/discover")
    assert r.status_code == 200
    discover_calls = [c for c in fake_tmdb.calls if c[0] == "/discover/tv"]
    assert "with_genres" not in discover_calls[-1][1]
