"""Core shared infrastructure for SeriesTrack backend.
Re-exports the most-used symbols so route modules can `from core import db, api, ...`.
"""
from .config import (
    FREE_LIBRARY_CAP,
    PRO_PLANS,
    JWT_SECRET,
    JWT_ALGO,
    TMDB_TOKEN,
    TMDB_REGION,
    TMDB_LANG,
    TMDB_BASE,
    TMDB_IMG,
    VAPID_PUBLIC_KEY,
    VAPID_PRIVATE_PEM,
    VAPID_PRIVATE_PEM_PATH,
    VAPID_SUBJECT,
    EMERGENT_OAUTH_SESSION_ENDPOINT,
    GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET,
    GOOGLE_CALENDAR_REDIRECT_URI,
    STRIPE_API_KEY,
    STRIPE_SECRET_KEY,
    STRIPE_PUBLISHABLE_KEY,
    STRIPE_WEBHOOK_SECRET,
    STRIPE_MODE,
    EMERGENT_LLM_KEY,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    PUSH_AVAILABLE,
    STRIPE_AVAILABLE,
    LLM_AVAILABLE,
    logger,
)
from .db import db, mongo_client
from .security import (
    hash_password,
    verify_password,
    create_token,
    set_auth_cookies,
    clear_auth_cookies,
    serialize_user,
    get_current_user,
    is_pro,
    require_pro,
)
from .tmdb import tmdb, tmdb_get_tv, normalize_show, close_tmdb
from .owners import ensure_owner_pro

__all__ = [
    "FREE_LIBRARY_CAP", "PRO_PLANS",
    "JWT_SECRET", "JWT_ALGO",
    "TMDB_TOKEN", "TMDB_REGION", "TMDB_LANG", "TMDB_BASE", "TMDB_IMG",
    "VAPID_PUBLIC_KEY", "VAPID_PRIVATE_PEM", "VAPID_PRIVATE_PEM_PATH", "VAPID_SUBJECT",
    "EMERGENT_OAUTH_SESSION_ENDPOINT", "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET", "GOOGLE_CALENDAR_REDIRECT_URI",
    "STRIPE_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_WEBHOOK_SECRET", "STRIPE_MODE",
    "EMERGENT_LLM_KEY", "GEMINI_API_KEY", "GEMINI_MODEL",
    "PUSH_AVAILABLE", "STRIPE_AVAILABLE", "LLM_AVAILABLE",
    "logger",
    "db", "mongo_client",
    "hash_password", "verify_password", "create_token",
    "set_auth_cookies", "clear_auth_cookies", "serialize_user",
    "get_current_user", "is_pro", "require_pro",
    "tmdb", "tmdb_get_tv", "normalize_show", "close_tmdb",
    "ensure_owner_pro",
]
