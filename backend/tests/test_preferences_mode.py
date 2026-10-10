"""Unit tests for /me/preferences's ui_mode (light/dark) field, run against the
in-memory mongomock DB (unlike test_themes_wrapped.py, which hits a live
deployed backend with `requests` and can't run in this sandbox). ui_mode is a
free, non-Pro-gated preference — unlike ui_theme, which this file doesn't
re-test (already covered live in test_themes_wrapped.py).
"""
import pytest
from tests.conftest import register_user, auth_headers


@pytest.mark.asyncio
async def test_default_mode_is_dark(client):
    data = await register_user(client, "modedefault@example.com")
    headers = auth_headers(data["access_token"])
    r = await client.get("/api/me/preferences", headers=headers)
    assert r.status_code == 200
    assert r.json()["preferences"]["ui_mode"] == "dark"


@pytest.mark.asyncio
async def test_free_user_can_set_light_and_dark(client):
    data = await register_user(client, "modefree@example.com")
    headers = auth_headers(data["access_token"])

    r = await client.patch("/api/me/preferences", json={"ui_mode": "light"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["preferences"]["ui_mode"] == "light"

    g = await client.get("/api/me/preferences", headers=headers)
    assert g.json()["preferences"]["ui_mode"] == "light"

    r2 = await client.patch("/api/me/preferences", json={"ui_mode": "dark"}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["preferences"]["ui_mode"] == "dark"


@pytest.mark.asyncio
async def test_unknown_mode_rejected(client):
    data = await register_user(client, "modebad@example.com")
    headers = auth_headers(data["access_token"])
    r = await client.patch("/api/me/preferences", json={"ui_mode": "sepia"}, headers=headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_setting_mode_does_not_touch_theme(client):
    """ui_mode and ui_theme are independent fields — patching one shouldn't
    reset the other."""
    data = await register_user(client, "modeindep@example.com")
    headers = auth_headers(data["access_token"])

    await client.patch("/api/me/preferences", json={"ui_theme": "default"}, headers=headers)
    r = await client.patch("/api/me/preferences", json={"ui_mode": "light"}, headers=headers)
    assert r.status_code == 200
    prefs = r.json()["preferences"]
    assert prefs["ui_mode"] == "light"
    assert prefs["ui_theme"] == "default"


@pytest.mark.asyncio
async def test_unauth_returns_401(client):
    r = await client.patch("/api/me/preferences", json={"ui_mode": "light"})
    assert r.status_code in (401, 403)
