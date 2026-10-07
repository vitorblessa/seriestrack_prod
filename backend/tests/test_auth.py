"""Tests for POST /auth/register, /auth/login, /auth/me, forgot/reset password."""
import pytest

from tests.conftest import register_user, auth_headers


@pytest.mark.asyncio
async def test_register_creates_unverified_user_and_returns_token(client):
    data = await register_user(client, "new.user@example.com")
    assert data["access_token"]
    assert data["user"]["email"] == "new.user@example.com"
    assert data["user"]["email_verified"] is False
    assert data["user"]["subscription_tier"] == "free"


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client):
    await register_user(client, "dup@example.com")
    r = await client.post("/api/auth/register", json={"email": "dup@example.com", "password": "Another1!", "name": "Dup"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_register_rejects_short_password(client):
    r = await client.post("/api/auth/register", json={"email": "weak@example.com", "password": "123", "name": "Weak"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_login_with_correct_password_succeeds(client):
    await register_user(client, "login.ok@example.com", password="CorrectHorse1!")
    r = await client.post("/api/auth/login", json={"email": "login.ok@example.com", "password": "CorrectHorse1!"})
    assert r.status_code == 200
    assert r.json()["access_token"]


@pytest.mark.asyncio
async def test_login_with_wrong_password_rejected(client):
    await register_user(client, "login.bad@example.com", password="CorrectHorse1!")
    r = await client.post("/api/auth/login", json={"email": "login.bad@example.com", "password": "WrongPassword!"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email_rejected(client):
    r = await client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever1"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_authentication(client):
    r = await client.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client):
    data = await register_user(client, "me@example.com")
    r = await client.get("/api/auth/me", headers=auth_headers(data["access_token"]))
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_forgot_password_never_leaks_whether_email_exists(client):
    """Same ok:true response whether or not the account exists — that's the
    whole point of the endpoint (no account-enumeration via timing/content)."""
    r1 = await client.post("/api/auth/forgot_password", json={"email": "ghost@example.com"})
    assert r1.status_code == 200
    assert r1.json() == {"ok": True}

    await register_user(client, "real@example.com")
    r2 = await client.post("/api/auth/forgot_password", json={"email": "real@example.com"})
    assert r2.status_code == 200
    assert r2.json() == {"ok": True}


@pytest.mark.asyncio
async def test_reset_password_rejects_invalid_token(client):
    r = await client.post("/api/auth/reset_password", json={"token": "not-a-real-token", "password": "NewPassword1!"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_rejects_invalid_token(client):
    r = await client.post("/api/auth/verify_email", json={"token": "not-a-real-token"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_resend_verification_is_noop_once_verified(client):
    data = await register_user(client, "verified@example.com")
    headers = auth_headers(data["access_token"])

    # Directly flip the flag the way /auth/verify_email would — isolates this
    # test from the email-sending path (already covered: it soft-fails without
    # RESEND_API_KEY, see core/email.py).
    from tests.conftest import _fake_db
    await _fake_db.users.update_one({"email": "verified@example.com"}, {"$set": {"email_verified": True}})

    r = await client.post("/api/auth/resend_verification", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "already_verified": True}
