"""AI recommendations (/ai/recommendations, Pro) must never return a series
already in the user's library, in ANY status (watching/paused/finished/
want/etc) — reported bug: the backend computed an `in_library` flag but
only used it to tag items, never to drop them, so the LLM's "don't repeat
the library" instruction (a soft prompt hint, not an enforced rule) could
still surface something the user already has.

Mocks google-genai's client (no real Gemini call, no network) and the TMDB
client (same fake pattern as test_series_discover.py), following this
suite's existing conventions — never hits a live service.
"""
import sys
import pytest
import routes.ai as routes_ai
from tests.conftest import register_user, auth_headers
from core import db

core_tmdb = sys.modules["core.tmdb"]


class _FakeTmdbResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class _FakeTmdbClient:
    """Resolves every /search/tv query to a fixed catalog keyed by title,
    so the test controls exactly which tmdb_id each AI-suggested title
    resolves to."""

    def __init__(self, catalog: dict):
        self.catalog = catalog

    async def get(self, path, params=None):
        if path == "/search/tv":
            title = (params or {}).get("query", "")
            show = self.catalog.get(title)
            results = [show] if show else []
            return _FakeTmdbResponse(200, {"results": results})
        return _FakeTmdbResponse(404, {})


class _FakeGenaiResponse:
    def __init__(self, text):
        self.text = text


class _FakeAioModels:
    def __init__(self, text):
        self._text = text

    async def generate_content(self, **kwargs):
        return _FakeGenaiResponse(self._text)


class _FakeAio:
    def __init__(self, text):
        self.models = _FakeAioModels(text)


class _FakeGenaiClient:
    def __init__(self, text):
        self.aio = _FakeAio(text)


def _install_fakes(monkeypatch, llm_json_text: str, tmdb_catalog: dict):
    monkeypatch.setattr(routes_ai, "LLM_AVAILABLE", True)
    monkeypatch.setattr(routes_ai, "GEMINI_API_KEY", "fake-key-for-tests")

    async def fake_tmdb_factory():
        return _FakeTmdbClient(tmdb_catalog)

    monkeypatch.setattr(core_tmdb, "tmdb", fake_tmdb_factory)
    monkeypatch.setattr(routes_ai, "tmdb", fake_tmdb_factory)

    class _FakeGenaiModule:
        @staticmethod
        def Client(api_key=None):
            return _FakeGenaiClient(llm_json_text)

    monkeypatch.setattr(routes_ai, "genai", _FakeGenaiModule)


async def _make_pro_user(client):
    data = await register_user(client, "owner@seriestrack-tests.com")
    return data


@pytest.mark.asyncio
async def test_already_in_library_series_is_excluded(monkeypatch, client):
    """Core regression test: the LLM "recommends" a show already in the
    user's library (status=paused) alongside one genuinely new show — only
    the new one should come back."""
    user = await _make_pro_user(client)
    headers = auth_headers(user["access_token"])

    # Already in the library, status "paused" — must be excluded regardless
    # of status, per the bug report ("assistido, pausada, finalizada etc").
    await db.library.insert_one({
        "user_id": user["user"]["id"], "tmdb_id": 100, "name": "Already Watching",
        "status": "paused", "updated_at": "2026-01-01T00:00:00Z",
    })

    llm_text = (
        '{"recommendations": ['
        '{"title": "Already Watching", "year": 2020, "why": "You liked similar shows"},'
        '{"title": "Brand New Show", "year": 2021, "why": "Great new pick"}'
        ']}'
    )
    tmdb_catalog = {
        "Already Watching": {"id": 100, "name": "Already Watching", "poster_path": "/p1.jpg", "backdrop_path": None, "first_air_date": "2020-01-01", "vote_average": 8.0},
        "Brand New Show": {"id": 200, "name": "Brand New Show", "poster_path": "/p2.jpg", "backdrop_path": None, "first_air_date": "2021-01-01", "vote_average": 7.5},
    }
    _install_fakes(monkeypatch, llm_text, tmdb_catalog)

    r = await client.post("/api/ai/recommendations", headers=headers)
    assert r.status_code == 200, r.text
    recs = r.json()["recommendations"]

    ids = [x["tmdb_id"] for x in recs]
    assert 100 not in ids, "a series already in the library (any status) must never be recommended"
    assert 200 in ids


@pytest.mark.asyncio
async def test_duplicate_tmdb_ids_from_llm_are_deduped(monkeypatch, client):
    """Two different AI-suggested titles resolving to the same real show
    (common with alternate titles/translations) shouldn't show up twice."""
    user = await _make_pro_user(client)
    headers = auth_headers(user["access_token"])

    # ai_recommendations() short-circuits to {"reason": "no_history"} when the
    # user has neither library items nor reviews — give it one unrelated
    # library item so the endpoint actually runs the LLM/enrich/filter path.
    await db.library.insert_one({
        "user_id": user["user"]["id"], "tmdb_id": 1, "name": "Seed Show",
        "status": "watching", "updated_at": "2026-01-01T00:00:00Z",
    })

    llm_text = (
        '{"recommendations": ['
        '{"title": "Show A", "year": 2021, "why": "reason 1"},'
        '{"title": "Show A Alt Title", "year": 2021, "why": "reason 2"}'
        ']}'
    )
    same_show = {"id": 300, "name": "Show A", "poster_path": "/p.jpg", "backdrop_path": None, "first_air_date": "2021-01-01", "vote_average": 9.0}
    tmdb_catalog = {"Show A": same_show, "Show A Alt Title": same_show}
    _install_fakes(monkeypatch, llm_text, tmdb_catalog)

    r = await client.post("/api/ai/recommendations", headers=headers)
    assert r.status_code == 200, r.text
    recs = r.json()["recommendations"]
    ids = [x["tmdb_id"] for x in recs]
    assert ids.count(300) == 1


@pytest.mark.asyncio
async def test_library_beyond_old_40_item_cap_still_excluded(monkeypatch, client):
    """Regression for the old `.limit(40)` library fetch: a Pro user (no
    library-size cap) with more than 40 items must still have ALL of them
    considered for exclusion, not just the first 40 read from the DB."""
    user = await _make_pro_user(client)
    headers = auth_headers(user["access_token"])

    # 45 filler items, then the one that matters at the end.
    for i in range(45):
        await db.library.insert_one({
            "user_id": user["user"]["id"], "tmdb_id": 1000 + i, "name": f"Filler {i}",
            "status": "finished", "updated_at": "2026-01-01T00:00:00Z",
        })
    await db.library.insert_one({
        "user_id": user["user"]["id"], "tmdb_id": 999, "name": "Late Entry Show",
        "status": "watching", "updated_at": "2026-01-01T00:00:00Z",
    })

    llm_text = '{"recommendations": [{"title": "Late Entry Show", "year": 2022, "why": "x"}]}'
    tmdb_catalog = {
        "Late Entry Show": {"id": 999, "name": "Late Entry Show", "poster_path": "/p.jpg", "backdrop_path": None, "first_air_date": "2022-01-01", "vote_average": 8.0},
    }
    _install_fakes(monkeypatch, llm_text, tmdb_catalog)

    r = await client.post("/api/ai/recommendations", headers=headers)
    assert r.status_code == 200, r.text
    ids = [x["tmdb_id"] for x in r.json()["recommendations"]]
    assert 999 not in ids
