"""Shared test fixtures.

Swaps the real MongoDB connection for an in-memory mongomock-motor database
before any app module is imported, so the test suite never touches a real
database (or the network at all). Every module that already does
`from core import db` / `from .db import db` by the time this file finishes
running gets the fake database, because we patch each already-imported
module's `db` attribute directly rather than relying on import order.
"""
import os
import sys

os.environ.setdefault("JWT_SECRET", "test-secret-key-not-for-production")
os.environ.setdefault("TMDB_READ_TOKEN", "test-tmdb-token")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "seriestrack_test")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("PRO_OWNERS", "owner@seriestrack-tests.com")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from mongomock_motor import AsyncMongoMockClient

import core  # noqa: E402  (must run before patching its submodules below)
import core.security as core_security
import core.owners as core_owners
import core.google_calendar as core_gcal

_fake_client = AsyncMongoMockClient()
_fake_db = _fake_client["seriestrack_test"]

# `core`'s own `db` attribute, `core.security.db`, `core.owners.db` and
# `core.google_calendar.db` were each bound to the real (unreachable) Mongo
# database at their own import time — reassigning `core.db` alone wouldn't
# reach them, so each already-imported module is patched directly.
core.db = _fake_db
core_security.db = _fake_db
core_owners.db = _fake_db
core_gcal.db = _fake_db

# Import AFTER the patches above, so every route module's own
# `from core import db` (triggered while `routes/__init__.py` imports them)
# picks up the fake database too.
import server as server_module  # noqa: E402
from core.limiter import limiter  # noqa: E402

server_module.db = _fake_db


@pytest.fixture
def app():
    return server_module.app


@pytest_asyncio.fixture
async def client(app):
    """An httpx.AsyncClient wired directly to the app via ASGI transport —
    no real socket, no running server, and runs the app's startup event
    (index creation, admin seed, Pro-owner sync) exactly like production."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def _clean_db():
    """Every test starts with an empty database — mongomock-motor is a single
    shared in-memory instance across the whole test session. Also resets the
    rate limiter, since otherwise one test's requests count against the next
    test's limit (slowapi keys by client IP, same for every test request)."""
    limiter.reset()
    yield
    for name in await _fake_db.list_collection_names():
        await _fake_db[name].delete_many({})


async def register_user(client: AsyncClient, email: str, password: str = "Sup3rSecret!", name: str = "Test User") -> dict:
    """Helper: register a user and return the response JSON (user + access_token)."""
    r = await client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    assert r.status_code == 200, r.text
    return r.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
