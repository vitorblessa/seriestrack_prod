"""Tests for the calendar routes that don't require real Google OAuth:
/calendar/upcoming and the iCal feed mint/fetch/revoke flow."""
import pytest

from tests.conftest import register_user, auth_headers


@pytest.mark.asyncio
async def test_upcoming_requires_authentication(client):
    r = await client.get("/api/calendar/upcoming")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_upcoming_is_empty_for_user_with_no_library_items(client):
    data = await register_user(client, "nolib@example.com")
    r = await client.get("/api/calendar/upcoming", headers=auth_headers(data["access_token"]))
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_ical_feed_mint_fetch_and_revoke(client):
    data = await register_user(client, "ical@example.com")
    headers = auth_headers(data["access_token"])

    mint = await client.post("/api/calendar/ical/feed", headers=headers)
    assert mint.status_code == 200
    token = mint.json()["token"]
    assert token

    fetch = await client.get("/api/calendar/ical", params={"token": token})
    assert fetch.status_code == 200
    assert "BEGIN:VCALENDAR" in fetch.text
    assert "END:VCALENDAR" in fetch.text

    revoke = await client.delete("/api/calendar/ical/feed", headers=headers)
    assert revoke.status_code == 200

    stale = await client.get("/api/calendar/ical", params={"token": token})
    assert stale.status_code in (401, 403, 404)
