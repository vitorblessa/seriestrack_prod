"""Tests for the owner-only admin endpoints: /admin/stats, /admin/revoke_pro,
and the pre-existing /auth/admin/search_users, /billing/admin/grant_pro."""
import pytest

from tests.conftest import register_user, auth_headers


@pytest.mark.asyncio
async def test_admin_endpoints_reject_non_owner(client):
    data = await register_user(client, "nobody-special@example.com")
    headers = auth_headers(data["access_token"])

    r1 = await client.get("/api/admin/stats", headers=headers)
    assert r1.status_code == 403

    r2 = await client.post("/api/admin/revoke_pro", params={"email": "nobody-special@example.com"}, headers=headers)
    assert r2.status_code == 403

    r3 = await client.get("/api/auth/admin/search_users", params={"q": "a"}, headers=headers)
    assert r3.status_code == 403


@pytest.mark.asyncio
async def test_admin_stats_counts_users_and_pro(client):
    owner = await register_user(client, "owner@seriestrack-tests.com")
    owner_headers = auth_headers(owner["access_token"])
    await register_user(client, "free.person@example.com")

    r = await client.get("/api/admin/stats", headers=owner_headers)
    assert r.status_code == 200
    body = r.json()
    # owner + free.person == 2 users at minimum
    assert body["total_users"] >= 2
    assert body["pro_users"] >= 1  # the owner is auto-credited lifetime Pro
    assert body["free_users"] == body["total_users"] - body["pro_users"]
    assert "new_users_7d" in body
    assert "total_library_items" in body


@pytest.mark.asyncio
async def test_search_users_finds_by_partial_email(client):
    owner = await register_user(client, "owner@seriestrack-tests.com")
    owner_headers = auth_headers(owner["access_token"])
    await register_user(client, "findme12345@example.com")

    r = await client.get("/api/auth/admin/search_users", params={"q": "findme12345"}, headers=owner_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["users"][0]["email"] == "findme12345@example.com"


@pytest.mark.asyncio
async def test_grant_then_revoke_pro_roundtrip(client):
    owner = await register_user(client, "owner@seriestrack-tests.com")
    owner_headers = auth_headers(owner["access_token"])
    target = await register_user(client, "comp-account@example.com")

    grant = await client.post(
        "/api/billing/admin/grant_pro",
        params={"email": "comp-account@example.com", "days": 30},
        headers=owner_headers,
    )
    assert grant.status_code == 200

    me_after_grant = await client.get("/api/billing/me", headers=auth_headers(target["access_token"]))
    assert me_after_grant.json()["tier"] == "pro"

    revoke = await client.post(
        "/api/admin/revoke_pro",
        params={"email": "comp-account@example.com"},
        headers=owner_headers,
    )
    assert revoke.status_code == 200

    me_after_revoke = await client.get("/api/billing/me", headers=auth_headers(target["access_token"]))
    assert me_after_revoke.json()["tier"] == "free"


@pytest.mark.asyncio
async def test_revoke_pro_unknown_email_returns_404(client):
    owner = await register_user(client, "owner@seriestrack-tests.com")
    r = await client.post(
        "/api/admin/revoke_pro",
        params={"email": "ghost@example.com"},
        headers=auth_headers(owner["access_token"]),
    )
    assert r.status_code == 404
