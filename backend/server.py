"""SeriesTrack API — FastAPI app factory.
All route definitions live in /app/backend/routes/*.py and shared infra in /app/backend/core/*.py.
"""
import os
from datetime import datetime, timezone
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


@app.on_event("shutdown")
async def shutdown():
    await close_tmdb()
