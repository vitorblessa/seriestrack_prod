"""SeriesTrack API — FastAPI app factory.
All route definitions live in /app/backend/routes/*.py and shared infra in /app/backend/core/*.py.
"""
import os
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core import db, logger, hash_password, close_tmdb
from routes import api_router

app = FastAPI(title="SeriesTrack API")
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
        await db.reviews.create_index([("user_id", 1), ("tmdb_id", 1)], unique=True)
        await db.reviews.create_index([("tmdb_id", 1), ("updated_at", -1)])
        await db.push_subscriptions.create_index([("user_id", 1), ("endpoint", 1)], unique=True)
        await db.payment_transactions.create_index("session_id", unique=True)
        await db.payment_transactions.create_index([("user_id", 1), ("created_at", -1)])
    except Exception as e:
        logger.warning(f"index creation: {e}")

    # Seed admin
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@seriestrack.app").lower()
    admin_pw = os.environ.get("ADMIN_PASSWORD", "Admin@123")
    existing = await db.users.find_one({"email": admin_email})
    if not existing:
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


@app.on_event("shutdown")
async def shutdown():
    await close_tmdb()
