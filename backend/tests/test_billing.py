"""Tests for the billing routes that don't require a real Stripe account:
/billing/plans, /billing/me, /billing/admin/grant_pro."""
import pytest

from tests.conftest import register_user, auth_headers, _fake_db


@pytest.mark.asyncio
async def test_billing_plans_lists_fixed_server_side_prices(client):
    r = await client.get("/api/billing/plans")
    assert r.status_code == 200
    plans = r.json()["plans"]
    ids = {p["id"] for p in plans}
    assert {"pro_monthly", "pro_yearly"} <= ids
    for p in plans:
        assert p["amount"] > 0
        assert p["currency"] == "brl"


@pytest.mark.asyncio
async def test_billing_me_defaults_to_free_tier(client):
    data = await register_user(client, "free.user@example.com")
    r = await client.get("/api/billing/me", headers=auth_headers(data["access_token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "free"
    assert body["days_left"] is None


@pytest.mark.asyncio
async def test_grant_pro_rejected_for_non_owner(client):
    data = await register_user(client, "regular@example.com")
    r = await client.post(
        "/api/billing/admin/grant_pro",
        params={"email": "regular@example.com", "days": 30},
        headers=auth_headers(data["access_token"]),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_grant_pro_by_owner_extends_subscription_idempotently(client):
    # PRO_OWNERS=owner@seriestrack-tests.com is set in conftest's env — registering
    # with that email auto-grants is_owner (see core/owners.py).
    owner = await register_user(client, "owner@seriestrack-tests.com")
    target = await register_user(client, "target@example.com")
    owner_headers = auth_headers(owner["access_token"])

    r1 = await client.post(
        "/api/billing/admin/grant_pro",
        params={"email": "target@example.com", "days": 30},
        headers=owner_headers,
    )
    assert r1.status_code == 200
    first_renews = r1.json()["subscription_renews_at"]

    # Calling again extends from the LATER of now/current renewal, not from
    # scratch — the renewal date should move forward, never backward or reset.
    r2 = await client.post(
        "/api/billing/admin/grant_pro",
        params={"email": "target@example.com", "days": 30},
        headers=owner_headers,
    )
    assert r2.status_code == 200
    second_renews = r2.json()["subscription_renews_at"]
    assert second_renews > first_renews

    me = await client.get("/api/billing/me", headers=auth_headers(target["access_token"]))
    assert me.json()["tier"] == "pro"


@pytest.mark.asyncio
async def test_grant_pro_unknown_email_returns_404(client):
    owner = await register_user(client, "owner@seriestrack-tests.com")
    r = await client.post(
        "/api/billing/admin/grant_pro",
        params={"email": "nobody@example.com", "days": 30},
        headers=auth_headers(owner["access_token"]),
    )
    assert r.status_code == 404
