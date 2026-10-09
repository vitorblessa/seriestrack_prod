"""Admin panel endpoints — owner-only. Pairs with the existing
GET /auth/admin/search_users and POST /billing/admin/grant_pro
(kept in their original files since other routes there depend on helpers
local to those modules): this file adds the few endpoints a real admin UI
needs that didn't exist yet — aggregate stats and revoking a manually
granted Pro."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from core import db, logger, get_current_user

router = APIRouter()


def _require_owner(user: dict):
    if not user.get("is_owner"):
        raise HTTPException(403, "Apenas o dono pode acessar o painel admin")


@router.get("/admin/stats")
async def admin_stats(user: dict = Depends(get_current_user)):
    """High-level numbers for the admin dashboard — total/pro/free users,
    signups in the last 7/30 days, and total library items across everyone."""
    _require_owner(user)

    total_users = await db.users.count_documents({})
    pro_users = await db.users.count_documents({"subscription_tier": "pro"})
    free_users = total_users - pro_users

    now = datetime.now(timezone.utc)
    since_7d = (now - timedelta(days=7)).isoformat()
    since_30d = (now - timedelta(days=30)).isoformat()
    # created_at is stored as a datetime on most docs but as isoformat string
    # on a few older/edge paths — match both shapes.
    new_7d = await db.users.count_documents({
        "$or": [
            {"created_at": {"$gte": now - timedelta(days=7)}},
            {"created_at": {"$gte": since_7d}},
        ]
    })
    new_30d = await db.users.count_documents({
        "$or": [
            {"created_at": {"$gte": now - timedelta(days=30)}},
            {"created_at": {"$gte": since_30d}},
        ]
    })
    total_library_items = await db.library.count_documents({})

    return {
        "total_users": total_users,
        "pro_users": pro_users,
        "free_users": free_users,
        "new_users_7d": new_7d,
        "new_users_30d": new_30d,
        "total_library_items": total_library_items,
    }


@router.post("/admin/revoke_pro")
async def admin_revoke_pro(email: str, user: dict = Depends(get_current_user)):
    """Owner-only — manually revoke Pro from a user (the inverse of
    POST /billing/admin/grant_pro). Only clears our own local flags; if the
    user has an active Stripe subscription, cancel that separately via
    Stripe's dashboard or they'll be re-credited on their next renewal."""
    _require_owner(user)

    target = await db.users.find_one({"email": email.strip().lower()})
    if not target:
        raise HTTPException(404, f"Nenhum usuário encontrado com o e-mail {email}")

    await db.users.update_one(
        {"_id": target["_id"]},
        {
            "$set": {"subscription_tier": "free", "auto_renew": False},
            "$unset": {"subscription_renews_at": "", "subscription_status": ""},
        },
    )
    logger.info(f"admin_revoke_pro: {email} revoked by owner {user.get('email')}")
    return {"ok": True, "email": target["email"], "user_id": str(target["_id"])}
