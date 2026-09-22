"""SeriesTrack API — FastAPI app factory.
All route definitions live in /app/backend/routes/*.py and shared infra in /app/backend/core/*.py.
"""
import os
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core import db, logger, hash_password, close_tmdb
from core.cron import start_scheduler, stop_scheduler, run_daily_push_pass
from routes import api_router

app = FastAPI(title="SeriesTrack API")
app.include_router(api_router)

# CORS: comma-separated allowlist via env. Default "*" for preview/dev only.
# Production MUST set CORS_ORIGINS to an explicit domain list.
_cors_raw = os.environ.get("CORS_ORIGINS", "*").strip()
_cors_list = ["*"] if _cors_raw == "*" else [o.strip() for o in _cors_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=False,  # cross-origin uses Authorization: Bearer, not cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.library.create_index([("user_id", 1), ("tmdb_id", 1)], unique=True)
        await db.library.create_index([("user_id", 1), ("status", 1)])
        await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
        await db.progress.create_index(
            [("user_id", 1), ("tmdb_id", 1), ("season", 1), ("episode", 1)],
            unique=True,
        )
        # Compound index supports the Wrapped year-range query
        await db.progress.create_index([("user_id", 1), ("watched_at", 1)])
        await db.reviews.create_index([("user_id", 1), ("tmdb_id", 1)], unique=True)
        await db.reviews.create_index([("tmdb_id", 1), ("updated_at", -1)])
        await db.push_subscriptions.create_index([("user_id", 1), ("endpoint", 1)], unique=True)
        await db.payment_transactions.create_index("session_id", unique=True)
        await db.payment_transactions.create_index([("user_id", 1), ("created_at", -1)])
    except Exception as e:
        logger.warning(f"index creation: {e}")

    # Seed admin — production requires ADMIN_PASSWORD env var, no insecure default.
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@seriestrack.app").lower()
    admin_pw = os.environ.get("ADMIN_PASSWORD")
    is_prod = os.environ.get("APP_ENV", "development").lower() == "production"
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
        if not admin_pw:
            if is_prod:
                # Fail fast: never seed a default admin in production.
                logger.error("ADMIN_PASSWORD unset in production — refusing to seed admin.")
            else:
                # Dev/preview convenience: seed with a well-known default and log a loud warning.
                admin_pw = "Admin@123"
                logger.warning("ADMIN_PASSWORD unset — seeding admin with dev default (NOT for production).")
        if admin_pw:
            await db.users.insert_one({
                "email": admin_email,
                "password_hash": hash_password(admin_pw),
                "name": "Admin",
                "avatar_url": None,
                "created_at": datetime.now(timezone.utc),
            })
            logger.info(f"Seeded admin user {admin_email}")

    # Lifetime Pro accounts — env-driven so we can roll the list without code changes.
    # Format: comma-separated emails, e.g. PRO_OWNERS=foo@bar.com,baz@qux.com
    # On every backend startup we ensure each listed email has subscription_tier=pro
    # with renews_at extended at least 10 years out. Idempotent.
    owners_raw = os.environ.get("PRO_OWNERS", "vitor.blessa@gmail.com")
    owner_emails = [e.strip().lower() for e in owners_raw.split(",") if e.strip()]
    now_dt = datetime.now(timezone.utc)
    far_future = (now_dt + timedelta(days=365 * 10)).isoformat()
    for owner_email in owner_emails:
        try:
            u = await db.users.find_one({"email": owner_email})
            if not u:
                # User hasn't signed up yet — skip. We'll grant when they register/login.
                continue
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
            logger.info(f"Lifetime Pro ensured for owner {owner_email}")
        except Exception as e:
            logger.warning(f"Lifetime Pro ensure failed for {owner_email}: {e}")

    # Daily push notification cron (12:00 UTC)
    try:
        start_scheduler()
    except Exception as e:
        logger.warning(f"scheduler start failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    try:
        stop_scheduler()
    except Exception:
        pass
    await close_tmdb()
