"""FCM (native Android push) registration + unified _send_push dispatch.

firebase-admin isn't installed in this sandbox, so core.fcm's send_fcm/_get_app
are exercised with monkeypatch rather than a real Firebase project: we patch
core.fcm's module-level flags/functions directly, the same way other optional
integrations (Sentry, Gemini) are tested elsewhere in this suite.
"""
import pytest
from tests.conftest import register_user, auth_headers
import routes.push as routes_push
from core import db


@pytest.mark.asyncio
async def test_register_fcm_token_upserts_subscription(client):
    data = await register_user(client, "fcmuser@example.com")
    headers = auth_headers(data["access_token"])

    r = await client.post("/api/push/register_fcm_token", json={"token": "DEVICE_TOKEN_ABC"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}

    sub = await db.push_subscriptions.find_one({"user_id": data["user"]["id"], "platform": "fcm"})
    assert sub is not None
    assert sub["fcm_token"] == "DEVICE_TOKEN_ABC"
    assert sub["endpoint"] == "fcm:DEVICE_TOKEN_ABC"

    # Re-registering the same token upserts (no duplicate row) rather than erroring.
    r2 = await client.post("/api/push/register_fcm_token", json={"token": "DEVICE_TOKEN_ABC"}, headers=headers)
    assert r2.status_code == 200
    count = await db.push_subscriptions.count_documents({"user_id": data["user"]["id"], "platform": "fcm"})
    assert count == 1


def test_send_push_dispatches_fcm_subs_to_send_fcm(monkeypatch):
    """A sub with platform="fcm" must be routed to core.fcm.send_fcm, never
    to the Web Push (pywebpush) branch — the two have incompatible payload
    shapes (no 'endpoint'/'keys' on an FCM sub)."""
    called = {}

    def fake_send_fcm(token, title, body, url=None, icon=None):
        called["args"] = (token, title, body, url, icon)
        return True, None

    monkeypatch.setattr(routes_push, "FCM_AVAILABLE", True)
    monkeypatch.setattr(routes_push, "send_fcm", fake_send_fcm)

    sub = {"platform": "fcm", "fcm_token": "tok123"}
    ok, err = routes_push._send_push(sub, "Title", "Body", url="/x", icon="/icon.png")

    assert ok is True
    assert err is None
    assert called["args"] == ("tok123", "Title", "Body", "/x", "/icon.png")


def test_send_push_fcm_not_configured_returns_error(monkeypatch):
    monkeypatch.setattr(routes_push, "FCM_AVAILABLE", False)
    sub = {"platform": "fcm", "fcm_token": "tok123"}
    ok, err = routes_push._send_push(sub, "Title", "Body")
    assert ok is False
    assert err == "FCM not configured"


def test_send_push_webpush_subs_unaffected_by_fcm_branch():
    """A legacy/web sub (no 'platform' key) must still go through the
    existing pywebpush path, not be mistaken for an FCM sub."""
    sub = {
        "endpoint": "https://updates.push.services.mozilla.com/wpush/v2/X",
        "keys": {"p256dh": "x", "auth": "y"},
    }
    ok, err = routes_push._send_push(sub, "x", "y")
    # Not configured in this test env either way, but must NOT short-circuit
    # via the FCM branch (that would return "FCM not configured" instead).
    assert ok is False
    assert err != "FCM not configured"


@pytest.mark.parametrize("err,expected", [
    ("410: Gone", True),
    ("404: Not Found", True),
    ("messaging/registration-token-not-registered", True),
    ("NOT_FOUND", True),
    (None, False),
    ("", False),
    ("500: Internal Server Error", False),
])
def test_is_stale_token_error(err, expected):
    assert routes_push._is_stale_token_error(err) is expected


def test_fcm_send_not_configured_when_sdk_or_env_missing():
    """core.fcm.send_fcm must fail soft (ok=False, error string) rather than
    raise when firebase-admin isn't installed or no service account is set —
    exactly the state of this sandbox."""
    from core.fcm import send_fcm
    ok, err = send_fcm("sometoken", "Title", "Body")
    assert ok is False
    assert err
