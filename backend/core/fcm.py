"""Firebase Cloud Messaging — native push for the installed Android app.

Web (including the PWA) keeps using Web Push/VAPID (core/config.py,
routes/push.py's `_send_push`); this module is only for device tokens
registered by the Android app's @capacitor/push-notifications plugin.

Lazily initializes the firebase_admin SDK from the service account JSON in
FIREBASE_SERVICE_ACCOUNT_JSON (the whole JSON file's contents, not a path —
simplest to set as a single Render env var). Import-guarded like every other
optional integration in this codebase: if firebase-admin isn't installed, or
no service account is configured, FCM_AVAILABLE is False and callers skip
straight to "not configured" rather than crashing.
"""
import json
from typing import Optional
from core.config import FCM_AVAILABLE, FIREBASE_SERVICE_ACCOUNT_JSON, logger

_app = None


def _get_app():
    global _app
    if _app is not None:
        return _app
    if not FCM_AVAILABLE:
        return None
    import firebase_admin
    from firebase_admin import credentials
    try:
        cred_info = json.loads(FIREBASE_SERVICE_ACCOUNT_JSON)
        cred = credentials.Certificate(cred_info)
        _app = firebase_admin.initialize_app(cred, name="seriestrack-fcm")
    except ValueError:
        # initialize_app raises ValueError if an app with this name already
        # exists (e.g. hot-reload in dev) — reuse it instead of erroring.
        _app = firebase_admin.get_app(name="seriestrack-fcm")
    except Exception as e:
        logger.warning(f"FCM init failed: {type(e).__name__}: {e}")
        return None
    return _app


def send_fcm(token: str, title: str, body: str, url: Optional[str] = None, icon: Optional[str] = None):
    """Returns (ok: bool, error: Optional[str]). The error string is checked
    by callers for "not-registered"/"invalid-argument" style substrings to
    decide whether to drop the stale token, same pattern as _send_push for
    Web Push's 404/410."""
    app = _get_app()
    if app is None:
        return False, "FCM not configured"
    from firebase_admin import messaging
    try:
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data={k: v for k, v in {"url": url, "icon": icon}.items() if v is not None},
            android=messaging.AndroidConfig(priority="high"),
        )
        messaging.send(message, app=app)
        return True, None
    except Exception as e:
        msg = str(e)
        logger.warning(f"FCM send failed for token {token[:20]}...: {type(e).__name__}: {msg}")
        return False, msg
