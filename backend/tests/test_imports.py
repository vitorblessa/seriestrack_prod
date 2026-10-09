"""Tests for /import/trakt and /import/letterboxd — both funnel through the
shared _bulk_import() helper in routes/imports.py, resolving each parsed row
against TMDB's TV search. Uses the same sys.modules['core.tmdb'] trick
documented in conftest.py's docstring to swap in a fake TMDB HTTP client.
"""
import pytest

from tests.conftest import register_user, auth_headers
import routes.imports as routes_imports


class _FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class _FakeTmdbClient:
    def __init__(self, routes):
        self.routes = routes

    async def get(self, path, params=None):
        if path == "/search/tv":
            query = (params or {}).get("query", "").lower()
            for key, payload in self.routes.items():
                if key.lower() in query:
                    return _FakeResponse(200, payload)
            return _FakeResponse(200, {"results": []})
        return _FakeResponse(404, {})


@pytest.fixture(autouse=True)
def fake_tmdb(monkeypatch):
    # "query contains this substring" -> canned /search/tv results
    routes = {
        "breaking bad": {"results": [{"id": 1396, "name": "Breaking Bad", "poster_path": None, "backdrop_path": None, "overview": ""}]},
        "the wire": {"results": [{"id": 1413, "name": "The Wire", "poster_path": None, "backdrop_path": None, "overview": ""}]},
    }
    client = _FakeTmdbClient(routes)

    async def fake_tmdb_factory():
        return client

    # routes/imports.py does `from core import tmdb`, binding its own `tmdb`
    # name to the function object at import time — patching core.tmdb.tmdb
    # wouldn't reach it, so patch the name where it's actually looked up.
    monkeypatch.setattr(routes_imports, "tmdb", fake_tmdb_factory)
    return client


async def _upload(client, headers, path, filename, content):
    files = {"file": (filename, content, "text/csv")}
    return await client.post(path, headers=headers, files=files)


@pytest.mark.asyncio
async def test_trakt_csv_import_adds_matched_shows(client):
    user = await register_user(client, "trakt1@test.com")
    headers = auth_headers(user["access_token"])

    csv = "Title,Year,Status\nBreaking Bad,2008,watching\nSome Unknown Show,2020,want\n"
    r = await _upload(client, headers, "/api/import/trakt", "trakt.csv", csv.encode())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert body["added"] == 1
    assert body["not_found_count"] == 1
    assert "Some Unknown Show" in body["not_found"]

    lib = await client.get("/api/library", headers=headers)
    names = {s["name"] for s in lib.json()}
    assert "Breaking Bad" in names


@pytest.mark.asyncio
async def test_letterboxd_watched_csv_defaults_to_finished(client):
    user = await register_user(client, "lbx1@test.com")
    headers = auth_headers(user["access_token"])

    csv = "Date,Name,Year,Letterboxd URI\n2024-01-01,The Wire,2002,https://letterboxd.com/film/the-wire/\n"
    r = await _upload(client, headers, "/api/import/letterboxd", "watched.csv", csv.encode())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["added"] == 1

    lib = await client.get("/api/library", headers=headers)
    items = lib.json()
    assert len(items) == 1
    assert items[0]["name"] == "The Wire"
    assert items[0]["status"] == "finished"


@pytest.mark.asyncio
async def test_letterboxd_watchlist_csv_defaults_to_want(client):
    user = await register_user(client, "lbx2@test.com")
    headers = auth_headers(user["access_token"])

    csv = "Name,Year,Letterboxd URI\nThe Wire,2002,https://letterboxd.com/film/the-wire/\n"
    r = await _upload(client, headers, "/api/import/letterboxd", "watchlist.csv", csv.encode())
    assert r.status_code == 200, r.text

    lib = await client.get("/api/library", headers=headers)
    items = lib.json()
    assert len(items) == 1
    assert items[0]["status"] == "want"


@pytest.mark.asyncio
async def test_letterboxd_import_tags_source(client):
    user = await register_user(client, "lbx3@test.com")
    headers = auth_headers(user["access_token"])

    csv = "Name,Year\nThe Wire,2002\n"
    r = await _upload(client, headers, "/api/import/letterboxd", "watchlist.csv", csv.encode())
    assert r.status_code == 200, r.text

    from core import db
    doc = await db.library.find_one({"user_id": user["user"]["id"], "name": "The Wire"})
    assert doc is not None
    assert doc["imported_from"] == "letterboxd"


@pytest.mark.asyncio
async def test_letterboxd_csv_missing_name_column_400(client):
    user = await register_user(client, "lbx4@test.com")
    headers = auth_headers(user["access_token"])

    csv = "Foo,Bar\n1,2\n"
    r = await _upload(client, headers, "/api/import/letterboxd", "watchlist.csv", csv.encode())
    assert r.status_code == 400
