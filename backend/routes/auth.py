"""Auth: register / login / logout / me / Google OAuth (Emergent)."""
from datetime import datetime, timezone
import httpx
from fastapi import APIRouter, HTTPException, Response, Depends
from core import (
    db, logger, hash_password, verify_password, create_token,
    set_auth_cookies, clear_auth_cookies, serialize_user, get_current_user,
    EMERGENT_OAUTH_SESSION_ENDPOINT,
)
from core.models import RegisterIn, LoginIn, GoogleCallbackIn

router = APIRouter()


@router.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "avatar_url": None,
        "created_at": datetime.now(timezone.utc),
    }
    res = await db.users.insert_one(doc)
    user_id = str(res.inserted_id)
    access = create_token(user_id, email, "access")
    refresh = create_token(user_id, email, "refresh")
    set_auth_cookies(response, access, refresh)
    doc["_id"] = res.inserted_id
    return {"user": serialize_user(doc), "access_token": access}


@router.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    user_id = str(user["_id"])
    access = create_token(user_id, email, "access")
    refresh = create_token(user_id, email, "refresh")
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(user), "access_token": access}


@router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return serialize_user(user)


# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
@router.post("/auth/google")
async def auth_google(payload: GoogleCallbackIn, response: Response):
    """Exchange an Emergent session_id for our app's JWT."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as hc:
            r = await hc.get(
                EMERGENT_OAUTH_SESSION_ENDPOINT,
                headers={"X-Session-ID": payload.session_id},
            )
        if r.status_code != 200:
            raise HTTPException(401, "Invalid Google session")
        info = r.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"emergent oauth fetch failed: {e}")
        raise HTTPException(502, "Auth provider unreachable")

    email = (info.get("email") or "").lower().strip()
    name = info.get("name") or "Usuário"
    picture = info.get("picture")
    if not email:
        raise HTTPException(401, "No email returned from provider")

    existing = await db.users.find_one({"email": email})
    now = datetime.now(timezone.utc)
    if existing:
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"name": existing.get("name") or name, "avatar_url": picture or existing.get("avatar_url"), "google_linked": True}},
        )
        user_id = str(existing["_id"])
        existing.update({"name": existing.get("name") or name, "avatar_url": picture or existing.get("avatar_url")})
        user_doc = existing
    else:
        doc = {
            "email": email,
            "name": name,
            "avatar_url": picture,
            "google_linked": True,
            "created_at": now,
        }
        res = await db.users.insert_one(doc)
        user_id = str(res.inserted_id)
        doc["_id"] = res.inserted_id
        user_doc = doc

    access = create_token(user_id, email, "access")
    refresh = create_token(user_id, email, "refresh")
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(user_doc), "access_token": access}
