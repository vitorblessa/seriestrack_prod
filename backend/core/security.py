"""Auth helpers: bcrypt + JWT issue/verify, FastAPI dependencies."""
from datetime import datetime, timezone, timedelta

import bcrypt
import jwt
from bson import ObjectId
from fastapi import HTTPException, Request, Response, Depends

from .config import JWT_SECRET, JWT_ALGO
from .db import db


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def create_token(user_id: str, email: str, kind: str = "access") -> str:
    if kind == "calendar_feed":
        exp = datetime.now(timezone.utc) + timedelta(days=365)
    elif kind == "refresh":
        exp = datetime.now(timezone.utc) + timedelta(days=30)
    else:
        exp = datetime.now(timezone.utc) + timedelta(minutes=60 * 24 * 7)
    return jwt.encode(
        {"sub": user_id, "email": email, "type": kind, "exp": exp},
        JWT_SECRET, algorithm=JWT_ALGO,
    )


def set_auth_cookies(response: Response, access: str, refresh: str):
    response.set_cookie("access_token", access, httponly=True, secure=True, samesite="none", max_age=60 * 60 * 24 * 7, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=True, samesite="none", max_age=60 * 60 * 24 * 30, path="/")


def clear_auth_cookies(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def serialize_user(doc: dict) -> dict:
    tier = doc.get("subscription_tier") or "free"
    renews = doc.get("subscription_renews_at")
    is_active_pro = False
    if tier == "pro" and renews:
        try:
            ren_dt = renews if isinstance(renews, datetime) else datetime.fromisoformat(renews)
            if ren_dt.tzinfo is None:
                ren_dt = ren_dt.replace(tzinfo=timezone.utc)
            is_active_pro = ren_dt > datetime.now(timezone.utc)
        except Exception:
            is_active_pro = False
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "name": doc.get("name", ""),
        "avatar_url": doc.get("avatar_url"),
        "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
        "subscription_tier": "pro" if is_active_pro else "free",
        "subscription_renews_at": (renews.isoformat() if isinstance(renews, datetime) else renews),
    }


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(401, "Wrong token type")
    user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
    if not user:
        raise HTTPException(401, "User not found")
    return user


async def is_pro(user: dict) -> bool:
    tier = user.get("subscription_tier")
    renews = user.get("subscription_renews_at")
    if tier != "pro" or not renews:
        return False
    try:
        ren_dt = renews if isinstance(renews, datetime) else datetime.fromisoformat(renews)
        if ren_dt.tzinfo is None:
            ren_dt = ren_dt.replace(tzinfo=timezone.utc)
        return ren_dt > datetime.now(timezone.utc)
    except Exception:
        return False


async def require_pro(user: dict = Depends(get_current_user)) -> dict:
    if not await is_pro(user):
        raise HTTPException(402, "Pro subscription required")
    return user
