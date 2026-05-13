"""Lifetime-Pro auto-grant for owner emails listed in env PRO_OWNERS.
Imported by auth routes so it runs on every register/login/google flow —
guarantees the owner is Pro even on first signup."""
import os
from datetime import datetime, timezone, timedelta
from .db import db
from .config import logger


def _owner_emails() -> list[str]:
    raw = os.environ.get("PRO_OWNERS", "vitor.blessa@gmail.com")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


async def ensure_owner_pro(email: str) -> bool:
    """If `email` is in PRO_OWNERS, ensure their user doc is Pro for 10 years.
    Returns True if a grant was applied. Idempotent and safe to call every login.
    """
    email_norm = (email or "").lower().strip()
    if email_norm not in _owner_emails():
        return False
    u = await db.users.find_one({"email": email_norm})
    if not u:
        return False
    far_future = (datetime.now(timezone.utc) + timedelta(days=365 * 10)).isoformat()
    await db.users.update_one(
        {"_id": u["_id"]},
        {
            "$set": {
                "subscription_tier": "pro",
                "subscription_renews_at": far_future,
                "subscription_status": "active",
                "auto_renew": True,
                "is_owner": True,
            },
            "$unset": {"canceled_at": ""},
        },
    )
    logger.info(f"Lifetime Pro auto-granted to owner {email_norm}")
    return True
