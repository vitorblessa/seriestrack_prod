"""Regression test: VAPID PEM must be passed as PATH, not contents."""
import os
import pytest


@pytest.fixture(scope="module")
def vapid_pem_path():
    p = os.environ.get("VAPID_PRIVATE_PEM_PATH", "/app/backend/vapid_private.pem")
    assert os.path.exists(p), f"VAPID PEM not at {p}"
    return p


def test_send_push_uses_pem_path_not_contents(vapid_pem_path):
    """Smoke-test that pywebpush parses our PEM. Bug: passing file contents
    causes ASN.1 parse errors on the EC curve. Must pass the PATH."""
    from pywebpush import webpush
    from cryptography.hazmat.primitives import serialization
    # Should NOT raise on load:
    with open(vapid_pem_path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    assert key is not None
    # And our _send_push helper passes path correctly
    from routes.push import _send_push
    import inspect
    src = inspect.getsource(_send_push)
    assert "VAPID_PRIVATE_PEM_PATH" in src, "_send_push must use the PATH (not the file contents)"
    assert "vapid_private_key=VAPID_PRIVATE_PEM_PATH" in src.replace(" ", "").replace("\n", " "), \
        "vapid_private_key arg must be the PATH"


def test_send_push_returns_error_on_bad_endpoint(vapid_pem_path):
    """Sanity: with a clearly invalid endpoint, _send_push returns (False, error_msg) — does not raise."""
    from routes.push import _send_push
    bad_sub = {
        "endpoint": "https://updates.push.services.mozilla.com/wpush/v2/INVALID_BAD_TOKEN_12345",
        "keys": {
            "p256dh": "BL7ELU24fGE2OqEZIY8C7lpD6QypvAJ31wDxBM3OfNAKDS6_jxgkj-Vqyh7VtVSr8c4nALJYRr0FZk5IhBV-Ifg",
            "auth": "qXLAjbdLPxOTpQGqAh1qpA",
        },
    }
    ok, err = _send_push(bad_sub, "x", "y")
    assert ok is False
    assert err  # any error message is fine — we just need to NOT crash
