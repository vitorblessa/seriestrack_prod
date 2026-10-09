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
    def __init__(self, routes, keyword_routes=None):
        self.routes = routes
        # /search/keyword is called once per synonym term with a different
        # `query` param each time — route those by query text, not just path.
        self.keyword_routes = keyword_routes or {}
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append((path, params))
        if path == "/search/keyword":
            query = ((params or {}).get("query") or "").lower()
            payload = self.keyword_routes.get(query, {"results": []})
            return _FakeResponse(200, payload)
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
    client = _FakeTmdbClient(
        routes={
            "/genre/tv/list": genres_payload,
            "/discover/tv": discover_payload,
        },
        keyword_routes={
            # "medical" resolves via _KEYWORD_SYNONYMS to 4 terms — each
            # returns a distinct id here so the OR'ing can be verified.
            "medical": {"results": [{"id": 6054, "name": "medical"}, {"id": 9999, "name": "medical malpractice"}]},
            "hospital": {"results": [{"id": 7777, "name": "hospital"}]},
            "doctor": {"results": [{"id": 8888, "name": "doctor"}]},
            "medical drama": {"results": [{"id": 6054, "name": "medical"}]},  # dupe of "medical"'s id, should be deduped
        },
    )

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


@pytest.mark.asyncio
async def test_discover_keyword_resolves_to_with_keywords_param(client, fake_tmdb):
    """The "Médicas" pseudo-genre chip has no TMDB genre id — it goes through
    a keyword search instead (TMDB models "medical" as a keyword, not a genre).
    Several related terms (medical/hospital/doctor/medical drama) are
    searched and OR'd together so popular shows tagged under any one of them
    (Grey's Anatomy, Chicago Med, House...) aren't missed."""
    r = await client.get("/api/series/discover", params={"keyword": "medical"})
    assert r.status_code == 200
    shows = r.json()
    assert len(shows) == 2

    keyword_calls = [c for c in fake_tmdb.calls if c[0] == "/search/keyword"]
    queried_terms = {c[1]["query"] for c in keyword_calls}
    assert queried_terms == {"medical", "hospital", "doctor", "medical drama"}

    discover_calls = [c for c in fake_tmdb.calls if c[0] == "/discover/tv"]
    # 6054 (exact "medical" match) + 7777 (hospital) + 8888 (doctor) — the
    # "medical drama" term's id (6054) is a dupe and shows up only once.
    assert discover_calls[-1][1]["with_keywords"] == "6054|7777|8888"


@pytest.mark.asyncio
async def test_discover_policial_keyword_synonyms(client, monkeypatch):
    """Same pseudo-genre mechanism as "Médicas", for "Policial" (police
    procedurals) — verifies the synonym set is wired up independently."""
    discover_payload = {"results": [{"id": 3, "name": "NCIS", "poster_path": None, "backdrop_path": None, "overview": "", "vote_average": 7.0, "first_air_date": "2003-01-01"}]}
    client_fake = _FakeTmdbClient(
        routes={"/discover/tv": discover_payload},
        keyword_routes={
            "police": {"results": [{"id": 111, "name": "police"}]},
            "detective": {"results": [{"id": 222, "name": "detective"}]},
            "police procedural": {"results": [{"id": 333, "name": "police procedural"}]},
            "fbi": {"results": [{"id": 444, "name": "fbi"}]},
        },
    )

    async def fake_tmdb_factory():
        return client_fake

    monkeypatch.setattr(core_tmdb, "tmdb", fake_tmdb_factory)

    r = await client.get("/api/series/discover", params={"keyword": "policial"})
    assert r.status_code == 200
    assert len(r.json()) == 1

    discover_calls = [c for c in client_fake.calls if c[0] == "/discover/tv"]
    assert discover_calls[-1][1]["with_keywords"] == "111|222|333|444"


@pytest.mark.asyncio
async def test_discover_unknown_keyword_omits_with_keywords_param(client, monkeypatch):
    discover_payload = {"results": []}
    no_match_client = _FakeTmdbClient(routes={"/discover/tv": discover_payload}, keyword_routes={})

    async def fake_tmdb_factory():
        return no_match_client

    monkeypatch.setattr(core_tmdb, "tmdb", fake_tmdb_factory)

    r = await client.get("/api/series/discover", params={"keyword": "nonexistent-xyz"})
    assert r.status_code == 200
    discover_calls = [c for c in no_match_client.calls if c[0] == "/discover/tv"]
    assert "with_keywords" not in discover_calls[-1][1]
