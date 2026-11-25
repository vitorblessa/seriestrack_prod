"""Regression tests for the Nov-2026 security pass: response headers, auth
cookie attributes, and the default-deny admin seed."""
import pytest
import server as server_module
from core import db


@pytest.mark.asyncio
async def test_security_headers_on_every_response(client):
    r = await client.get("/api/push/public_key")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "max-age=" in r.headers["strict-transport-security"]


@pytest.mark.asyncio
async def test_auth_cookies_are_samesite_lax(client):
    """The cookie is accepted by get_current_user and there is no CSRF token,
    so it must never be sendable cross-site (SameSite=None)."""
    r = await client.post(
        "/api/auth/register",
        json={"email": "cookie@example.com", "password": "Sup3rSecret!", "name": "C"},
    )
    assert r.status_code == 200, r.text
    cookies = r.headers.get_list("set-cookie")
    assert cookies, "register should still set auth cookies"
    for c in cookies:
        low = c.lower()
        assert "samesite=lax" in low, c
        assert "samesite=none" not in low, c
        assert "httponly" in low and "secure" in low, c


@pytest.mark.asyncio
async def test_admin_not_seeded_with_default_password_when_app_env_unset(monkeypatch):
    """A missing APP_ENV must be treated as production: no well-known default
    admin password may be seeded."""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("ADMIN_EMAIL", "seedcheck@example.com")
    await server_module.startup()
    assert await db.users.find_one({"email": "seedcheck@example.com"}) is None


@pytest.mark.asyncio
async def test_admin_seeded_with_explicit_password_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_PASSWORD", "A-Strong-Unique-Pass-1!")
    monkeypatch.setenv("ADMIN_EMAIL", "seedcheck2@example.com")
    await server_module.startup()
    assert await db.users.find_one({"email": "seedcheck2@example.com"}) is not None
