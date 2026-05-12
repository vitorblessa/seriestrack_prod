from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import re
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

import bcrypt
import jwt
import httpx
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

try:
    from pywebpush import webpush, WebPushException
    PUSH_AVAILABLE = True
except Exception:
    PUSH_AVAILABLE = False

try:
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest,
    )
    STRIPE_AVAILABLE = True
except Exception:
    STRIPE_AVAILABLE = False

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False

# ---------------------- Setup ----------------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = "HS256"
TMDB_TOKEN = os.environ['TMDB_READ_TOKEN']
TMDB_REGION = os.environ.get('TMDB_REGION', 'US')
TMDB_LANG = os.environ.get('TMDB_LANG', 'en-US')
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"

VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_PEM_PATH = os.environ.get('VAPID_PRIVATE_PEM_PATH', '')
VAPID_SUBJECT = os.environ.get('VAPID_SUBJECT', 'mailto:admin@example.com')
EMERGENT_OAUTH_SESSION_ENDPOINT = os.environ.get(
    'EMERGENT_OAUTH_SESSION_ENDPOINT',
    'https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data'
)
VAPID_PRIVATE_PEM = ''
if VAPID_PRIVATE_PEM_PATH and os.path.exists(VAPID_PRIVATE_PEM_PATH):
    with open(VAPID_PRIVATE_PEM_PATH, 'r') as f:
        VAPID_PRIVATE_PEM = f.read()

STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Free tier limits
FREE_LIBRARY_CAP = 50

# Server-side fixed pricing (NEVER trust client-supplied amounts)
PRO_PLANS = {
    "pro_monthly": {"amount": 12.90, "currency": "brl", "days": 30, "label": "Pro Mensal"},
    "pro_yearly": {"amount": 99.00, "currency": "brl", "days": 365, "label": "Pro Anual"},
}

app = FastAPI(title="SeriesTrack API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("seriestrack")


# ---------------------- Helpers ----------------------
def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode(), h.encode())
    except Exception:
        return False


def create_token(user_id: str, email: str, kind: str = "access") -> str:
    exp = datetime.now(timezone.utc) + (timedelta(minutes=60 * 24 * 7) if kind == "access" else timedelta(days=30))
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


# ---------------------- TMDB client ----------------------
_http: Optional[httpx.AsyncClient] = None


async def tmdb() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=TMDB_BASE,
            headers={"Authorization": f"Bearer {TMDB_TOKEN}", "accept": "application/json"},
            timeout=20.0,
        )
    return _http


def normalize_show(s: dict) -> dict:
    poster = s.get("poster_path")
    backdrop = s.get("backdrop_path")
    return {
        "id": s.get("id"),
        "name": s.get("name") or s.get("title"),
        "overview": s.get("overview", ""),
        "poster_url": f"{TMDB_IMG}/w500{poster}" if poster else None,
        "backdrop_url": f"{TMDB_IMG}/original{backdrop}" if backdrop else None,
        "first_air_date": s.get("first_air_date"),
        "vote_average": s.get("vote_average", 0),
        "popularity": s.get("popularity", 0),
        "genre_ids": s.get("genre_ids", []),
    }


# ---------------------- Models ----------------------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class LibraryUpsertIn(BaseModel):
    tmdb_id: int
    status: str = Field(pattern="^(watching|paused|finished|want)$")
    name: Optional[str] = None
    poster_url: Optional[str] = None
    backdrop_url: Optional[str] = None
    overview: Optional[str] = None


class ProgressIn(BaseModel):
    tmdb_id: int
    season: int
    episode: int
    watched: bool = True


class ProgressBulkIn(BaseModel):
    tmdb_id: int
    season: int
    watched: bool = True


class GoogleCallbackIn(BaseModel):
    session_id: str


class ReviewIn(BaseModel):
    tmdb_id: int
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


class PushKeysIn(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: PushKeysIn


class CheckoutIn(BaseModel):
    plan: str
    origin_url: str


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


# ---------------------- Auth routes ----------------------
@api.post("/auth/register")
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


@api.post("/auth/login")
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


@api.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return serialize_user(user)


# ---------------------- TMDB / Series routes ----------------------
@api.get("/series/trending")
async def trending(window: str = "week"):
    tc = await tmdb()
    r = await tc.get(f"/trending/tv/{window}", params={"language": TMDB_LANG})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@api.get("/series/popular")
async def popular():
    tc = await tmdb()
    r = await tc.get("/tv/popular", params={"language": TMDB_LANG, "region": TMDB_REGION})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@api.get("/series/top_rated")
async def top_rated():
    tc = await tmdb()
    r = await tc.get("/tv/top_rated", params={"language": TMDB_LANG})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@api.get("/series/airing_today")
async def airing_today():
    tc = await tmdb()
    r = await tc.get("/tv/airing_today", params={"language": TMDB_LANG})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@api.get("/series/on_the_air")
async def on_the_air():
    tc = await tmdb()
    r = await tc.get("/tv/on_the_air", params={"language": TMDB_LANG})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@api.get("/series/search")
async def search(q: str):
    if not q.strip():
        return []
    tc = await tmdb()
    r = await tc.get("/search/tv", params={"query": q, "language": TMDB_LANG, "include_adult": False})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])]


@api.get("/series/{tmdb_id}")
async def series_detail(tmdb_id: int):
    tc = await tmdb()
    # Detail with credits + videos + recommendations + watch providers
    r = await tc.get(
        f"/tv/{tmdb_id}",
        params={"language": TMDB_LANG, "append_to_response": "watch/providers,credits,videos,recommendations,external_ids"},
    )
    if r.status_code == 404:
        raise HTTPException(404, "Series not found")
    r.raise_for_status()
    s = r.json()

    providers_block = (s.get("watch/providers", {}) or {}).get("results", {}) or {}
    region_block = providers_block.get(TMDB_REGION) or providers_block.get("US") or {}
    flatrate = region_block.get("flatrate") or region_block.get("free") or []
    providers = [
        {
            "provider_id": p.get("provider_id"),
            "provider_name": p.get("provider_name"),
            "logo_url": f"{TMDB_IMG}/w92{p.get('logo_path')}" if p.get("logo_path") else None,
        }
        for p in flatrate
    ]

    cast = [
        {
            "name": c.get("name"),
            "character": c.get("character"),
            "profile_url": f"{TMDB_IMG}/w185{c.get('profile_path')}" if c.get("profile_path") else None,
        }
        for c in (s.get("credits", {}).get("cast") or [])[:10]
    ]

    recommendations = [normalize_show(x) for x in (s.get("recommendations", {}).get("results") or [])][:12]

    seasons = [
        {
            "id": se.get("id"),
            "season_number": se.get("season_number"),
            "name": se.get("name"),
            "episode_count": se.get("episode_count"),
            "air_date": se.get("air_date"),
            "overview": se.get("overview"),
            "poster_url": f"{TMDB_IMG}/w300{se.get('poster_path')}" if se.get("poster_path") else None,
        }
        for se in (s.get("seasons") or [])
        if se.get("season_number", 0) > 0
    ]

    return {
        "id": s.get("id"),
        "name": s.get("name"),
        "tagline": s.get("tagline"),
        "overview": s.get("overview"),
        "poster_url": f"{TMDB_IMG}/w500{s.get('poster_path')}" if s.get("poster_path") else None,
        "backdrop_url": f"{TMDB_IMG}/original{s.get('backdrop_path')}" if s.get("backdrop_path") else None,
        "first_air_date": s.get("first_air_date"),
        "last_air_date": s.get("last_air_date"),
        "next_episode_to_air": s.get("next_episode_to_air"),
        "last_episode_to_air": s.get("last_episode_to_air"),
        "status": s.get("status"),
        "in_production": s.get("in_production"),
        "vote_average": s.get("vote_average"),
        "number_of_seasons": s.get("number_of_seasons"),
        "number_of_episodes": s.get("number_of_episodes"),
        "genres": [g.get("name") for g in (s.get("genres") or [])],
        "networks": [
            {"name": n.get("name"), "logo_url": f"{TMDB_IMG}/w92{n.get('logo_path')}" if n.get("logo_path") else None}
            for n in (s.get("networks") or [])
        ],
        "providers": providers,
        "providers_link": region_block.get("link"),
        "cast": cast,
        "seasons": seasons,
        "recommendations": recommendations,
    }


@api.get("/series/{tmdb_id}/season/{season_number}")
async def season_detail(tmdb_id: int, season_number: int):
    tc = await tmdb()
    r = await tc.get(f"/tv/{tmdb_id}/season/{season_number}", params={"language": TMDB_LANG})
    if r.status_code == 404:
        raise HTTPException(404, "Season not found")
    r.raise_for_status()
    s = r.json()
    return {
        "id": s.get("id"),
        "season_number": s.get("season_number"),
        "name": s.get("name"),
        "overview": s.get("overview"),
        "poster_url": f"{TMDB_IMG}/w300{s.get('poster_path')}" if s.get("poster_path") else None,
        "episodes": [
            {
                "id": e.get("id"),
                "episode_number": e.get("episode_number"),
                "season_number": e.get("season_number"),
                "name": e.get("name"),
                "overview": e.get("overview"),
                "still_url": f"{TMDB_IMG}/w300{e.get('still_path')}" if e.get("still_path") else None,
                "air_date": e.get("air_date"),
                "runtime": e.get("runtime"),
                "vote_average": e.get("vote_average"),
            }
            for e in (s.get("episodes") or [])
        ],
    }


# ---------------------- Library routes ----------------------
@api.get("/library")
async def get_library(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"user_id": str(user["_id"])}
    if status:
        q["status"] = status
    items = await db.library.find(q, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return items


@api.post("/library")
async def upsert_library(payload: LibraryUpsertIn, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    # Free-tier cap: 50 series. Existing items can be updated; new adds are blocked.
    existing_in_lib = await db.library.find_one({"user_id": user_id, "tmdb_id": payload.tmdb_id})
    if not existing_in_lib and not await is_pro(user):
        count = await db.library.count_documents({"user_id": user_id})
        if count >= FREE_LIBRARY_CAP:
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "library_cap_reached",
                    "message": f"Limite gratuito de {FREE_LIBRARY_CAP} séries atingido. Faça upgrade para Pro para biblioteca ilimitada.",
                    "cap": FREE_LIBRARY_CAP,
                    "current": count,
                },
            )

    # Fetch missing details from TMDB if needed
    name = payload.name
    poster_url = payload.poster_url
    backdrop_url = payload.backdrop_url
    overview = payload.overview
    if not name or not poster_url:
        try:
            tc = await tmdb()
            r = await tc.get(f"/tv/{payload.tmdb_id}", params={"language": TMDB_LANG})
            if r.status_code == 200:
                s = r.json()
                name = name or s.get("name")
                poster_url = poster_url or (f"{TMDB_IMG}/w500{s.get('poster_path')}" if s.get("poster_path") else None)
                backdrop_url = backdrop_url or (f"{TMDB_IMG}/original{s.get('backdrop_path')}" if s.get("backdrop_path") else None)
                overview = overview or s.get("overview")
        except Exception as e:
            logger.warning(f"library upsert tmdb fetch failed: {e}")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id": user_id,
        "tmdb_id": payload.tmdb_id,
        "status": payload.status,
        "name": name,
        "poster_url": poster_url,
        "backdrop_url": backdrop_url,
        "overview": overview,
        "updated_at": now,
    }
    await db.library.update_one(
        {"user_id": user_id, "tmdb_id": payload.tmdb_id},
        {"$set": doc, "$setOnInsert": {"added_at": now}},
        upsert=True,
    )

    # Create welcome notification
    await db.notifications.insert_one({
        "user_id": user_id,
        "type": "library_added",
        "title": f"{name or 'Série'} adicionada como {payload.status}",
        "message": "Você receberá avisos sobre novos episódios.",
        "tmdb_id": payload.tmdb_id,
        "poster_url": poster_url,
        "read": False,
        "created_at": now,
    })

    return {"ok": True}


@api.delete("/library/{tmdb_id}")
async def remove_library(tmdb_id: int, user: dict = Depends(get_current_user)):
    await db.library.delete_one({"user_id": str(user["_id"]), "tmdb_id": tmdb_id})
    return {"ok": True}


@api.get("/library/contains/{tmdb_id}")
async def library_contains(tmdb_id: int, user: dict = Depends(get_current_user)):
    item = await db.library.find_one({"user_id": str(user["_id"]), "tmdb_id": tmdb_id}, {"_id": 0})
    return {"in_library": bool(item), "item": item}


# ---------------------- Calendar / Upcoming ----------------------
@api.get("/calendar/upcoming")
async def calendar_upcoming(user: dict = Depends(get_current_user)):
    """Return upcoming episodes for shows in user's library."""
    items = await db.library.find({"user_id": str(user["_id"])}).to_list(200)
    tc = await tmdb()
    out = []
    for it in items:
        try:
            r = await tc.get(f"/tv/{it['tmdb_id']}", params={"language": TMDB_LANG, "append_to_response": "watch/providers"})
            if r.status_code != 200:
                continue
            s = r.json()
            providers_block = (s.get("watch/providers", {}) or {}).get("results", {}) or {}
            region_block = providers_block.get(TMDB_REGION) or providers_block.get("US") or {}
            flatrate = region_block.get("flatrate") or []
            provider_names = [p.get("provider_name") for p in flatrate]

            nxt = s.get("next_episode_to_air")
            last = s.get("last_episode_to_air")
            for ep, kind in [(nxt, "upcoming"), (last, "recent")]:
                if not ep:
                    continue
                out.append({
                    "tmdb_id": it["tmdb_id"],
                    "series_name": s.get("name"),
                    "poster_url": it.get("poster_url"),
                    "backdrop_url": it.get("backdrop_url"),
                    "episode_name": ep.get("name"),
                    "season_number": ep.get("season_number"),
                    "episode_number": ep.get("episode_number"),
                    "air_date": ep.get("air_date"),
                    "still_url": f"{TMDB_IMG}/w300{ep.get('still_path')}" if ep.get("still_path") else None,
                    "overview": ep.get("overview"),
                    "kind": kind,
                    "providers": provider_names,
                })
        except Exception as e:
            logger.warning(f"calendar fetch failed for {it.get('tmdb_id')}: {e}")
            continue
    out.sort(key=lambda x: x.get("air_date") or "")
    return out


# ---------------------- Notifications ----------------------
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = await db.notifications.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    return items


@api.post("/notifications/read_all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": str(user["_id"])}, {"$set": {"read": True}})
    return {"ok": True}


@api.get("/notifications/unread_count")
async def unread_count(user: dict = Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": str(user["_id"]), "read": False})
    return {"count": n}


# ---------------------- Stats ----------------------
@api.get("/stats")
async def stats(user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    counts = {}
    for st in ("watching", "paused", "finished", "want"):
        counts[st] = await db.library.count_documents({"user_id": user_id, "status": st})
    counts["total"] = sum(counts.values())
    return counts


# ---------------------- Google OAuth (Emergent) ----------------------
# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
@api.post("/auth/google")
async def auth_google(payload: GoogleCallbackIn, response: Response):
    """Exchange an Emergent session_id for our app's JWT.
    Frontend obtains session_id via redirect from auth.emergentagent.com after Google login,
    and POSTs it here. We hit Emergent's session-data endpoint, upsert the user,
    and return our standard { user, access_token } shape so the existing AuthContext keeps working.
    """
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


# ---------------------- Episode progress ----------------------
@api.post("/progress")
async def upsert_progress(payload: ProgressIn, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    key = {"user_id": user_id, "tmdb_id": payload.tmdb_id, "season": payload.season, "episode": payload.episode}
    if payload.watched:
        await db.progress.update_one(
            key,
            {"$set": {**key, "watched_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
    else:
        await db.progress.delete_one(key)
    return {"ok": True}


@api.get("/progress/{tmdb_id}")
async def get_progress(tmdb_id: int, user: dict = Depends(get_current_user)):
    items = await db.progress.find(
        {"user_id": str(user["_id"]), "tmdb_id": tmdb_id}, {"_id": 0}
    ).to_list(2000)
    return items


@api.post("/progress/bulk")
async def bulk_progress(payload: ProgressBulkIn, user: dict = Depends(get_current_user)):
    """Mark ALL episodes of a season as watched (or unwatched). Useful for fast catch-up."""
    user_id = str(user["_id"])
    if payload.watched:
        # Need episode list from TMDB to upsert each
        tc = await tmdb()
        r = await tc.get(f"/tv/{payload.tmdb_id}/season/{payload.season}", params={"language": TMDB_LANG})
        if r.status_code != 200:
            raise HTTPException(404, "Season not found")
        episodes = r.json().get("episodes", [])
        if not episodes:
            return {"updated": 0, "watched": True}
        now = datetime.now(timezone.utc).isoformat()
        # Use individual upserts (small N per season, fine without bulk_write)
        for ep in episodes:
            ep_num = ep.get("episode_number")
            if ep_num is None:
                continue
            await db.progress.update_one(
                {"user_id": user_id, "tmdb_id": payload.tmdb_id, "season": payload.season, "episode": ep_num},
                {"$set": {"user_id": user_id, "tmdb_id": payload.tmdb_id, "season": payload.season, "episode": ep_num, "watched_at": now}},
                upsert=True,
            )
        return {"updated": len(episodes), "watched": True}
    # unmark all
    result = await db.progress.delete_many({
        "user_id": user_id,
        "tmdb_id": payload.tmdb_id,
        "season": payload.season,
    })
    return {"deleted": result.deleted_count, "watched": False}


@api.get("/progress/{tmdb_id}/summary")
async def progress_summary(tmdb_id: int, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    # Get series info to know total episodes per season
    tc = await tmdb()
    r = await tc.get(f"/tv/{tmdb_id}", params={"language": TMDB_LANG})
    if r.status_code != 200:
        raise HTTPException(404, "Series not found")
    s = r.json()
    seasons = [se for se in (s.get("seasons") or []) if se.get("season_number", 0) > 0]

    watched_docs = await db.progress.find(
        {"user_id": user_id, "tmdb_id": tmdb_id}, {"_id": 0}
    ).to_list(5000)
    watched_set = {(d["season"], d["episode"]) for d in watched_docs}

    season_summaries = []
    total_watched = 0
    total_eps = 0
    for se in seasons:
        sn = se["season_number"]
        ec = se.get("episode_count") or 0
        wc = sum(1 for (sx, ex) in watched_set if sx == sn)
        total_watched += wc
        total_eps += ec
        season_summaries.append({
            "season_number": sn,
            "watched": wc,
            "total": ec,
            "percent": int((wc / ec) * 100) if ec else 0,
        })

    return {
        "tmdb_id": tmdb_id,
        "seasons": season_summaries,
        "total_watched": total_watched,
        "total_episodes": total_eps,
        "percent": int((total_watched / total_eps) * 100) if total_eps else 0,
    }


# ---------------------- Reviews & Ratings ----------------------
@api.post("/reviews")
async def upsert_review(payload: ReviewIn, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id": user_id,
        "user_name": user.get("name") or "Anônimo",
        "tmdb_id": payload.tmdb_id,
        "rating": payload.rating,
        "comment": payload.comment or "",
        "updated_at": now,
    }
    await db.reviews.update_one(
        {"user_id": user_id, "tmdb_id": payload.tmdb_id},
        {"$set": doc, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {"ok": True}


@api.delete("/reviews/{tmdb_id}")
async def delete_review(tmdb_id: int, user: dict = Depends(get_current_user)):
    await db.reviews.delete_one({"user_id": str(user["_id"]), "tmdb_id": tmdb_id})
    return {"ok": True}


@api.get("/reviews/{tmdb_id}")
async def list_reviews(tmdb_id: int):
    items = await db.reviews.find({"tmdb_id": tmdb_id}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    avg = None
    if items:
        avg = round(sum(r["rating"] for r in items) / len(items), 2)
    return {"reviews": items, "average": avg, "count": len(items)}


@api.get("/reviews/{tmdb_id}/mine")
async def my_review(tmdb_id: int, user: dict = Depends(get_current_user)):
    item = await db.reviews.find_one({"user_id": str(user["_id"]), "tmdb_id": tmdb_id}, {"_id": 0})
    return item or {}


# ---------------------- Public profile / shared library ----------------------
@api.get("/users/{user_id}/public")
async def public_profile(user_id: str):
    try:
        u = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(404, "User not found")
    if not u:
        raise HTTPException(404, "User not found")
    counts = {}
    for st in ("watching", "paused", "finished", "want"):
        counts[st] = await db.library.count_documents({"user_id": user_id, "status": st})
    counts["total"] = sum(counts.values())
    recent_reviews = await db.reviews.find({"user_id": user_id}, {"_id": 0}).sort("updated_at", -1).limit(8).to_list(8)
    return {
        "id": user_id,
        "name": u.get("name"),
        "avatar_url": u.get("avatar_url"),
        "joined_at": (u.get("created_at").isoformat() if isinstance(u.get("created_at"), datetime) else u.get("created_at")),
        "stats": counts,
        "recent_reviews": recent_reviews,
    }


@api.get("/users/{user_id}/library")
async def public_library(user_id: str, status: Optional[str] = None):
    q = {"user_id": user_id}
    if status:
        q["status"] = status
    items = await db.library.find(q, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return items


# ---------------------- Web Push ----------------------
@api.get("/push/public_key")
async def push_public_key():
    return {"public_key": VAPID_PUBLIC_KEY, "available": bool(VAPID_PUBLIC_KEY) and PUSH_AVAILABLE}


@api.post("/push/subscribe")
async def push_subscribe(payload: PushSubscriptionIn, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    doc = {
        "user_id": user_id,
        "endpoint": payload.endpoint,
        "keys": payload.keys.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.push_subscriptions.update_one(
        {"user_id": user_id, "endpoint": payload.endpoint},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True}


@api.delete("/push/subscribe")
async def push_unsubscribe(endpoint: str, user: dict = Depends(get_current_user)):
    await db.push_subscriptions.delete_one({"user_id": str(user["_id"]), "endpoint": endpoint})
    return {"ok": True}


def _send_push(sub: dict, title: str, body: str, url: Optional[str] = None, icon: Optional[str] = None):
    if not (PUSH_AVAILABLE and VAPID_PRIVATE_PEM):
        return False, "push not configured"
    try:
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": sub["keys"],
            },
            data=json.dumps({"title": title, "body": body, "url": url, "icon": icon}),
            vapid_private_key=VAPID_PRIVATE_PEM,
            vapid_claims={"sub": VAPID_SUBJECT},
            ttl=60 * 60 * 24,
        )
        return True, None
    except WebPushException as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


@api.post("/push/test")
async def push_test(user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)
    if not subs:
        raise HTTPException(400, "Sem inscrições ativas. Ative as notificações primeiro.")
    sent = 0
    failed = 0
    for s in subs:
        ok, err = _send_push(s, "SeriesTrack 🎬", "Notificações ativadas com sucesso!", url="/dashboard")
        if ok:
            sent += 1
        else:
            failed += 1
            if err and ("410" in err or "404" in err):
                await db.push_subscriptions.delete_one({"_id": s["_id"]})
    return {"sent": sent, "failed": failed}


@api.post("/push/notify_today")
async def push_notify_today(user: dict = Depends(get_current_user)):
    """Manually trigger notifications for episodes airing today/tomorrow in the user's library.
    Creates an in-app notification AND pushes a web-push if subscriptions exist.
    """
    user_id = str(user["_id"])
    items = await db.library.find({"user_id": user_id}).to_list(500)
    if not items:
        return {"created": 0, "pushed": 0}

    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    target_dates = {today.isoformat(), tomorrow.isoformat()}

    tc = await tmdb()
    created = 0
    pushed = 0
    subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)

    for it in items:
        try:
            r = await tc.get(f"/tv/{it['tmdb_id']}", params={"language": TMDB_LANG})
            if r.status_code != 200:
                continue
            s = r.json()
            ep = s.get("next_episode_to_air")
            if not ep or ep.get("air_date") not in target_dates:
                continue

            title = f"Novo episódio: {s.get('name')}"
            body = f"T{ep.get('season_number')}·E{ep.get('episode_number')} — {ep.get('name')} estreia em {ep.get('air_date')}"

            existing_notif = await db.notifications.find_one({
                "user_id": user_id,
                "type": "episode_release",
                "tmdb_id": it["tmdb_id"],
                "season": ep.get("season_number"),
                "episode": ep.get("episode_number"),
            })
            if not existing_notif:
                await db.notifications.insert_one({
                    "user_id": user_id,
                    "type": "episode_release",
                    "title": title,
                    "message": body,
                    "tmdb_id": it["tmdb_id"],
                    "poster_url": it.get("poster_url"),
                    "season": ep.get("season_number"),
                    "episode": ep.get("episode_number"),
                    "read": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                created += 1

            for sub in subs:
                ok, err = _send_push(sub, title, body, url=f"/series/{it['tmdb_id']}", icon=it.get("poster_url"))
                if ok:
                    pushed += 1
                elif err and ("410" in err or "404" in err):
                    await db.push_subscriptions.delete_one({"_id": sub["_id"]})
        except Exception as e:
            logger.warning(f"notify_today err {it.get('tmdb_id')}: {e}")
            continue

    return {"created": created, "pushed": pushed}


# ---------------------- Streaming search ----------------------
def _normalize_provider(s: str) -> str:
    """Normalize provider name for fuzzy matching.
    Handles '+' / 'Plus' variants and strips punctuation/extra whitespace.
    'Disney+' / 'Disney Plus' / 'disney plus' -> 'disney'
    'Apple TV+' / 'Apple TV Plus' -> 'apple tv'
    'Amazon Prime Video' -> 'amazon prime video'
    """
    n = (s or "").lower().strip()
    n = n.replace("+", " plus ")
    n = re.sub(r"\bplus\b", " ", n)  # remove the word "plus"
    n = re.sub(r"[^a-z0-9 ]+", " ", n)  # strip remaining punctuation
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _provider_matches(needle_norm: str, provider_norm: str) -> bool:
    """True when the needle matches the provider as exact, or as a word-sequence
    that appears at the start or end of the provider (avoids false-positive midmatches
    like 'apple tv' matching 'Paramount Plus Apple TV Channel').
    Also rejects sub-channel variants (* channel) when the needle doesn't explicitly
    include 'channel' — e.g. 'apple tv' must NOT match 'apple tv amazon channel'."""
    if not needle_norm or not provider_norm:
        return False
    if needle_norm == provider_norm:
        return True
    n_words = needle_norm.split()
    p_words = provider_norm.split()
    if len(n_words) > len(p_words):
        return False
    # Reject sub-channel variants unless user explicitly searched for "channel"
    if "channel" in p_words and "channel" not in n_words:
        return False
    if p_words[: len(n_words)] == n_words:
        return True
    if p_words[-len(n_words):] == n_words:
        return True
    return False


# Cache TMDB tv watch-providers list for the configured region (24h)
_tv_providers_cache: dict = {"data": None, "ts": 0.0}


async def _resolve_provider_ids(needle_norm: str) -> tuple[list[int], list[str]]:
    """Resolve all TMDB provider_ids whose normalized name matches the needle.
    Returns (provider_ids, matched_provider_names). Caches the providers list for 24h.
    """
    import time as _time
    now = _time.time()
    if not _tv_providers_cache["data"] or (now - _tv_providers_cache["ts"]) > 86400:
        try:
            tc = await tmdb()
            r = await tc.get("/watch/providers/tv", params={"language": TMDB_LANG, "watch_region": TMDB_REGION})
            if r.status_code == 200:
                _tv_providers_cache["data"] = r.json().get("results", [])
                _tv_providers_cache["ts"] = now
        except Exception as e:
            logger.warning(f"providers cache refresh failed: {e}")
    providers = _tv_providers_cache["data"] or []
    ids: list[int] = []
    names: list[str] = []
    for p in providers:
        pn = _normalize_provider(p.get("provider_name"))
        if _provider_matches(needle_norm, pn):
            pid = p.get("provider_id")
            if pid:
                ids.append(pid)
                names.append(p.get("provider_name"))
    return ids, names


@api.get("/streaming/episodes")
async def streaming_episodes(name: str, user: dict = Depends(get_current_user)):
    """Return the latest episodes for shows currently available on a streaming platform.
    Queries TMDB globally (NOT the user's library) — discovers popular shows on the
    platform in the user's region, fetches last_episode_to_air for each, and returns
    them sorted by air_date desc.
    """
    needle_norm = _normalize_provider(name)
    if not needle_norm:
        return {"matched_providers": [], "episodes": []}

    provider_ids, matched_names = await _resolve_provider_ids(needle_norm)
    if not provider_ids:
        return {"matched_providers": [], "episodes": []}

    tc = await tmdb()
    today = datetime.now(timezone.utc).date()
    # 90-day window: episodes that aired in last 60d OR will air in next 30d
    min_date = (today - timedelta(days=60)).isoformat()
    max_date = (today + timedelta(days=30)).isoformat()

    # Discover popular shows on this platform with recent episode activity
    discover_params = {
        "language": TMDB_LANG,
        "watch_region": TMDB_REGION,
        "with_watch_providers": "|".join(str(pid) for pid in provider_ids),
        "with_watch_monetization_types": "flatrate",
        "sort_by": "popularity.desc",
        "air_date.gte": (today - timedelta(days=180)).isoformat(),
        "page": 1,
    }
    try:
        r = await tc.get("/discover/tv", params=discover_params)
        if r.status_code != 200:
            logger.warning(f"discover/tv failed {r.status_code}: {r.text[:200]}")
            return {"matched_providers": matched_names, "episodes": []}
        shows = r.json().get("results", [])[:25]
    except Exception as e:
        logger.warning(f"discover/tv error: {e}")
        return {"matched_providers": matched_names, "episodes": []}

    async def fetch_show_eps(show: dict):
        try:
            rr = await tc.get(f"/tv/{show['id']}", params={"language": TMDB_LANG})
            if rr.status_code != 200:
                return []
            s = rr.json()
            poster = show.get("poster_path") or s.get("poster_path")
            backdrop = show.get("backdrop_path") or s.get("backdrop_path")
            out = []
            for ep, kind in [(s.get("last_episode_to_air"), "recent"), (s.get("next_episode_to_air"), "upcoming")]:
                if not ep or not ep.get("air_date"):
                    continue
                if ep["air_date"] < min_date or ep["air_date"] > max_date:
                    continue
                out.append({
                    "tmdb_id": show["id"],
                    "series_name": s.get("name") or show.get("name"),
                    "poster_url": f"{TMDB_IMG}/w500{poster}" if poster else None,
                    "backdrop_url": f"{TMDB_IMG}/original{backdrop}" if backdrop else None,
                    "episode_name": ep.get("name"),
                    "season_number": ep.get("season_number"),
                    "episode_number": ep.get("episode_number"),
                    "air_date": ep.get("air_date"),
                    "still_url": f"{TMDB_IMG}/w300{ep.get('still_path')}" if ep.get("still_path") else None,
                    "overview": ep.get("overview"),
                    "kind": kind,
                    "providers": matched_names,
                    "matched_providers": matched_names,
                })
            return out
        except Exception:
            return []

    results = await asyncio.gather(*(fetch_show_eps(sh) for sh in shows))
    episodes: list = []
    for r in results:
        episodes.extend(r)
    episodes.sort(key=lambda x: x.get("air_date") or "", reverse=True)
    # In-library marking — annotate which ones are in the user's library
    user_id = str(user["_id"])
    lib_ids = {it["tmdb_id"] for it in await db.library.find({"user_id": user_id}, {"_id": 0, "tmdb_id": 1}).to_list(500)}
    for e in episodes:
        e["in_library"] = e["tmdb_id"] in lib_ids
    return {
        "matched_providers": sorted(set(matched_names)),
        "episodes": episodes[:30],
    }


# ---------------------- Billing (Stripe) ----------------------
def _stripe_client(request: Request) -> "StripeCheckout":
    if not STRIPE_AVAILABLE:
        raise HTTPException(503, "Pagamentos indisponíveis no momento")
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe não configurado")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)


@api.get("/billing/plans")
async def billing_plans():
    return {"plans": [
        {"id": k, "label": v["label"], "amount": v["amount"], "currency": v["currency"], "days": v["days"]}
        for k, v in PRO_PLANS.items()
    ]}


@api.post("/billing/checkout")
async def billing_checkout(payload: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    plan = PRO_PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(400, "Plano inválido")
    sc = _stripe_client(request)
    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/pricing"
    metadata = {
        "user_id": str(user["_id"]),
        "user_email": user["email"],
        "plan": payload.plan,
        "days": str(plan["days"]),
    }
    req = CheckoutSessionRequest(
        amount=float(plan["amount"]),
        currency=plan["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    try:
        session = await sc.create_checkout_session(req)
    except Exception as e:
        logger.warning(f"stripe checkout error: {e}")
        raise HTTPException(502, f"Erro ao criar sessão de pagamento: {e}")

    # MANDATORY: create payment_transactions row BEFORE redirecting
    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "user_id": str(user["_id"]),
        "user_email": user["email"],
        "plan": payload.plan,
        "amount": plan["amount"],
        "currency": plan["currency"],
        "days": plan["days"],
        "metadata": metadata,
        "status": "initiated",
        "payment_status": "unpaid",
        "credited": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": session.url, "session_id": session.session_id}


async def _credit_pro(user_id: str, days: int) -> Optional[str]:
    """Idempotently extend the user's Pro subscription by `days`. Returns new renews_at iso."""
    try:
        u = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
    if not u:
        return None
    now = datetime.now(timezone.utc)
    cur = u.get("subscription_renews_at")
    cur_dt = None
    if cur:
        try:
            cur_dt = cur if isinstance(cur, datetime) else datetime.fromisoformat(cur)
            if cur_dt.tzinfo is None:
                cur_dt = cur_dt.replace(tzinfo=timezone.utc)
        except Exception:
            cur_dt = None
    base = cur_dt if (cur_dt and cur_dt > now) else now
    new_renews = base + timedelta(days=days)
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"subscription_tier": "pro", "subscription_renews_at": new_renews.isoformat(), "subscription_status": "active"}},
    )
    return new_renews.isoformat()


@api.get("/billing/status/{session_id}")
async def billing_status(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    """Polled by frontend after Stripe redirect. Verifies + credits Pro idempotently."""
    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": str(user["_id"])}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Transação não encontrada")

    sc = _stripe_client(request)
    try:
        st = await sc.get_checkout_status(session_id)
    except Exception as e:
        logger.warning(f"stripe status error: {e}")
        raise HTTPException(502, f"Erro ao consultar Stripe: {e}")

    new_status = st.status
    new_payment_status = st.payment_status

    update = {
        "status": new_status,
        "payment_status": new_payment_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "amount_total": st.amount_total,
        "currency_received": st.currency,
    }

    # Credit only once
    credited = tx.get("credited", False)
    if not credited and new_payment_status == "paid":
        days = int(tx.get("days") or 30)
        new_renews = await _credit_pro(tx["user_id"], days)
        update["credited"] = True
        update["credited_at"] = datetime.now(timezone.utc).isoformat()
        update["new_renews_at"] = new_renews

    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": update})

    return {
        "status": new_status,
        "payment_status": new_payment_status,
        "amount_total": st.amount_total,
        "currency": st.currency,
        "plan": tx.get("plan"),
        "credited": update.get("credited", credited),
        "new_renews_at": update.get("new_renews_at"),
    }


@api.get("/billing/me")
async def billing_me(user: dict = Depends(get_current_user)):
    pro = await is_pro(user)
    renews = user.get("subscription_renews_at")
    if isinstance(renews, datetime):
        renews = renews.isoformat()
    days_left = None
    if pro and renews:
        try:
            ren_dt = datetime.fromisoformat(renews)
            if ren_dt.tzinfo is None:
                ren_dt = ren_dt.replace(tzinfo=timezone.utc)
            delta = ren_dt - datetime.now(timezone.utc)
            days_left = max(0, delta.days)
        except Exception:
            pass
    return {"tier": "pro" if pro else "free", "renews_at": renews, "days_left": days_left}


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_AVAILABLE:
        return {"received": False}
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    sc = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=str(request.base_url).rstrip("/") + "/api/webhook/stripe")
    try:
        ev = await sc.handle_webhook(body, sig)
    except Exception as e:
        logger.warning(f"stripe webhook verify failed: {e}")
        raise HTTPException(400, "invalid signature")

    session_id = getattr(ev, "session_id", None)
    if session_id:
        tx = await db.payment_transactions.find_one({"session_id": session_id})
        if tx and ev.payment_status == "paid" and not tx.get("credited"):
            days = int(tx.get("days") or 30)
            new_renews = await _credit_pro(tx["user_id"], days)
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "credited": True,
                    "credited_at": datetime.now(timezone.utc).isoformat(),
                    "new_renews_at": new_renews,
                    "status": "complete",
                    "payment_status": ev.payment_status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
    return {"received": True, "event_type": getattr(ev, "event_type", None)}


# ---------------------- Health ----------------------
@api.get("/")
async def root():
    return {"app": "SeriesTrack", "version": "1.0.0"}


# ---------------------- AI Recommendations (Pro) ----------------------
@api.post("/ai/recommendations")
async def ai_recommendations(user: dict = Depends(require_pro)):
    if not LLM_AVAILABLE or not EMERGENT_LLM_KEY:
        raise HTTPException(503, "Recomendações IA indisponíveis no momento")
    user_id = str(user["_id"])

    # Build user context
    lib = await db.library.find({"user_id": user_id}, {"_id": 0}).limit(40).to_list(40)
    reviews = await db.reviews.find({"user_id": user_id}, {"_id": 0}).limit(20).to_list(20)
    if not lib and not reviews:
        return {"recommendations": [], "reason": "no_history"}

    # Compose a compact prompt
    seen_lines = []
    for it in lib[:30]:
        seen_lines.append(f"- {it.get('name')} ({it.get('status')})")
    review_lines = []
    for r in reviews:
        c = (r.get('comment') or '').strip()
        review_lines.append(f"- {r.get('user_name','')}: rated {r.get('rating')}/5{(' — ' + c) if c else ''}")

    system = (
        "Você é um curador especialista em séries de TV. Recomende 5 séries que o usuário "
        "provavelmente vai amar, baseado no que ele já assistiu e avaliou. Cada recomendação "
        "DEVE ser de uma série diferente, NÃO repita séries que já estão na lista do usuário. "
        "Responda APENAS com JSON válido no formato: "
        '{"recommendations":[{"title":"<nome em inglês ou original>","year":<ano>,"why":"<1-2 frases em pt-BR explicando por que essa pessoa vai gostar>"}]}'
    )
    prompt = (
        "Séries que o usuário tem na biblioteca:\n" + "\n".join(seen_lines or ["(vazio)"]) +
        "\n\nAvaliações do usuário:\n" + "\n".join(review_lines or ["(nenhuma)"]) +
        "\n\nGere as 5 recomendações em JSON puro. Sem markdown, sem ```."
    )

    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"recs-{user_id}",
            system_message=system,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        msg = UserMessage(text=prompt)
        raw = await chat.send_message(msg)
    except Exception as e:
        logger.warning(f"LLM recs failed: {e}")
        raise HTTPException(502, "Erro ao gerar recomendações")

    # Strip code fences if present + parse
    txt = (raw or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.MULTILINE)
    try:
        data = json.loads(txt)
        recs = data.get("recommendations", [])[:5]
    except Exception:
        logger.warning(f"Bad LLM JSON: {txt[:300]}")
        raise HTTPException(502, "Resposta inválida do modelo")

    # Enrich with TMDB poster + tmdb_id for each
    tc = await tmdb()

    async def enrich(r: dict):
        title = (r.get("title") or "").strip()
        if not title:
            return None
        try:
            sr = await tc.get("/search/tv", params={"query": title, "language": TMDB_LANG, "include_adult": False})
            results = sr.json().get("results") or [] if sr.status_code == 200 else []
            if r.get("year"):
                yr = str(r["year"])
                exact = [x for x in results if (x.get("first_air_date") or "").startswith(yr)]
                if exact:
                    results = exact
            top = results[0] if results else None
        except Exception:
            top = None
        if not top:
            return None
        return {
            "tmdb_id": top.get("id"),
            "name": top.get("name"),
            "poster_url": f"{TMDB_IMG}/w500{top.get('poster_path')}" if top.get("poster_path") else None,
            "backdrop_url": f"{TMDB_IMG}/original{top.get('backdrop_path')}" if top.get("backdrop_path") else None,
            "first_air_date": top.get("first_air_date"),
            "vote_average": top.get("vote_average"),
            "ai_why": r.get("why", ""),
        }

    enriched = await asyncio.gather(*(enrich(r) for r in recs))
    out = [e for e in enriched if e]

    # Mark which are already in library
    lib_ids = {it["tmdb_id"] for it in lib}
    for e in out:
        e["in_library"] = e["tmdb_id"] in lib_ids

    return {"recommendations": out, "model": "claude-sonnet-4-5"}


# ---------------------- Advanced Stats (Pro) ----------------------
@api.get("/stats/advanced")
async def advanced_stats(user: dict = Depends(require_pro)):
    user_id = str(user["_id"])
    progress = await db.progress.find({"user_id": user_id}, {"_id": 0}).to_list(20000)
    library = await db.library.find({"user_id": user_id}, {"_id": 0}).to_list(500)

    # Total episodes watched and approx hours (45min avg per episode)
    total_eps = len(progress)
    estimated_minutes = total_eps * 45
    estimated_hours = round(estimated_minutes / 60, 1)
    estimated_days = round(estimated_minutes / 60 / 24, 2)

    # Episodes per series (top 5)
    by_series: dict = {}
    for p in progress:
        by_series[p["tmdb_id"]] = by_series.get(p["tmdb_id"], 0) + 1
    series_name_map = {it["tmdb_id"]: it.get("name") for it in library}
    top_series = sorted(
        [{"tmdb_id": k, "name": series_name_map.get(k, f"Série {k}"), "episodes": v} for k, v in by_series.items()],
        key=lambda x: x["episodes"], reverse=True,
    )[:5]

    # Heatmap: episodes watched per day (last 365 days, ISO date → count)
    from collections import Counter
    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=365)).isoformat()
    heat: dict = {}
    for p in progress:
        d = (p.get("watched_at") or "")[:10]
        if d and d >= cutoff:
            heat[d] = heat.get(d, 0) + 1
    heatmap = [{"date": k, "count": v} for k, v in sorted(heat.items())]

    # Genre breakdown — fetch genres for each library show in parallel (cached implicitly by TMDB CDN)
    tc = await tmdb()
    async def fetch_genres(it: dict):
        try:
            r = await tc.get(f"/tv/{it['tmdb_id']}", params={"language": TMDB_LANG})
            if r.status_code != 200:
                return []
            return [g.get("name") for g in (r.json().get("genres") or [])]
        except Exception:
            return []
    genre_lists = await asyncio.gather(*(fetch_genres(it) for it in library[:50]))
    genre_counter = Counter()
    for gs in genre_lists:
        for g in gs:
            if g:
                genre_counter[g] += 1
    top_genres = [{"genre": g, "count": c} for g, c in genre_counter.most_common(10)]

    # Library status breakdown (also in /api/stats but include here)
    statuses = {}
    for st in ("watching", "paused", "finished", "want"):
        statuses[st] = sum(1 for it in library if it.get("status") == st)

    # Most active month (last 12 months)
    month_counter = Counter()
    for p in progress:
        d = (p.get("watched_at") or "")[:7]
        if d:
            month_counter[d] += 1
    top_months = [{"month": m, "count": c} for m, c in month_counter.most_common(6)]

    return {
        "total_episodes_watched": total_eps,
        "estimated_minutes": estimated_minutes,
        "estimated_hours": estimated_hours,
        "estimated_days": estimated_days,
        "top_series": top_series,
        "top_genres": top_genres,
        "heatmap": heatmap,
        "library_breakdown": statuses,
        "top_months": top_months,
        "library_size": len(library),
    }


@api.get("/limits")
async def usage_limits(user: dict = Depends(get_current_user)):
    """Return current usage vs limits for the authenticated user."""
    user_id = str(user["_id"])
    pro = await is_pro(user)
    library_count = await db.library.count_documents({"user_id": user_id})
    return {
        "tier": "pro" if pro else "free",
        "library": {
            "used": library_count,
            "cap": None if pro else FREE_LIBRARY_CAP,
            "remaining": None if pro else max(0, FREE_LIBRARY_CAP - library_count),
        },
    }


# ---------------------- AI Preview rec (Free upsell hook) ----------------------
@api.get("/ai/preview_rec")
async def ai_preview_rec(user: dict = Depends(get_current_user)):
    """Return ONE recommendation preview for Free users — used as upsell hook on the Dashboard.
    Uses TMDB-native recommendations (no LLM cost) seeded by user's most-recent library item.
    Pro users hit /ai/recommendations directly for the full 5-rec list.
    """
    user_id = str(user["_id"])
    lib_items = await db.library.find({"user_id": user_id}, {"_id": 0}).sort("updated_at", -1).to_list(20)
    if not lib_items:
        return {"rec": None, "reason": "empty_library"}

    lib_ids = {it["tmdb_id"] for it in lib_items}
    tc = await tmdb()

    # Try up to first 5 most-recent library items in order until we find a new rec
    for seed in lib_items[:5]:
        try:
            r = await tc.get(
                f"/tv/{seed['tmdb_id']}/recommendations",
                params={"language": TMDB_LANG, "page": 1},
            )
            if r.status_code != 200:
                continue
            results = r.json().get("results") or []
            for cand in results:
                if cand.get("id") in lib_ids:
                    continue
                if not cand.get("poster_path"):
                    continue
                return {
                    "rec": {
                        "tmdb_id": cand.get("id"),
                        "name": cand.get("name"),
                        "poster_url": f"{TMDB_IMG}/w500{cand.get('poster_path')}",
                        "backdrop_url": f"{TMDB_IMG}/original{cand.get('backdrop_path')}" if cand.get("backdrop_path") else None,
                        "first_air_date": cand.get("first_air_date"),
                        "vote_average": cand.get("vote_average"),
                        "overview": cand.get("overview"),
                        "seed_name": seed.get("name"),
                    },
                }
        except Exception as e:
            logger.warning(f"preview_rec seed {seed.get('tmdb_id')} failed: {e}")
            continue
    return {"rec": None, "reason": "no_match"}


# ---------------------- Trakt Import ----------------------
def _normalize_trakt_title(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _parse_trakt_file(content: bytes, filename: str) -> List[Dict[str, Any]]:
    """Parse a Trakt export (JSON list/object OR CSV) and return [{title, year?, tmdb_id?, status?}]."""
    text = content.decode("utf-8", errors="ignore").strip()
    if not text:
        return []
    items: List[Dict[str, Any]] = []
    is_json = filename.lower().endswith(".json") or text.startswith("[") or text.startswith("{")
    if is_json:
        try:
            data = json.loads(text)
        except Exception as e:
            raise HTTPException(400, f"JSON inválido: {e}")
        if isinstance(data, dict):
            # Trakt format may wrap shows under "shows" / "items"
            data = data.get("shows") or data.get("items") or data.get("watchlist") or []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            show = entry.get("show") or entry
            ids = show.get("ids") or {}
            title = _normalize_trakt_title(show.get("title") or entry.get("title") or "")
            if not title:
                continue
            items.append({
                "title": title,
                "year": show.get("year") or entry.get("year"),
                "tmdb_id": ids.get("tmdb") if isinstance(ids, dict) else None,
                "status": entry.get("status") or "want",
            })
    else:
        # CSV — accept Trakt's "Title,Year,..." style or any with a Title column
        import csv as _csv
        from io import StringIO
        reader = _csv.DictReader(StringIO(text))
        if not reader.fieldnames:
            return []
        # find case-insensitive title/year/tmdb columns
        cols = {c.lower().strip(): c for c in reader.fieldnames}
        title_col = cols.get("title") or cols.get("name") or cols.get("show")
        year_col = cols.get("year")
        tmdb_col = cols.get("tmdb") or cols.get("tmdb_id") or cols.get("tmdbid")
        status_col = cols.get("status")
        if not title_col:
            raise HTTPException(400, "CSV precisa de uma coluna 'Title'")
        for row in reader:
            title = _normalize_trakt_title(row.get(title_col) or "")
            if not title:
                continue
            try:
                yr = int(row[year_col]) if year_col and row.get(year_col) else None
            except Exception:
                yr = None
            try:
                tid = int(row[tmdb_col]) if tmdb_col and row.get(tmdb_col) else None
            except Exception:
                tid = None
            items.append({
                "title": title,
                "year": yr,
                "tmdb_id": tid,
                "status": (row.get(status_col) or "want").lower() if status_col else "want",
            })
    return items


def _coerce_status(s: str) -> str:
    s = (s or "").lower().strip()
    if s in ("watching", "paused", "finished", "want"):
        return s
    # Trakt-ish aliases
    if s in ("watched", "completed", "ended"):
        return "finished"
    if s in ("watchlist", "plan_to_watch", "plan-to-watch"):
        return "want"
    if s in ("on_hold", "on-hold", "hold"):
        return "paused"
    return "want"


@api.post("/import/trakt")
async def import_trakt(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a Trakt export (CSV or JSON). Matches each title against TMDB and inserts into the
    user's library as `want` (unless status hints otherwise). Free users are still capped at
    FREE_LIBRARY_CAP — extra items are skipped and reported in `skipped_cap`.
    """
    user_id = str(user["_id"])
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "Arquivo muito grande (max 5MB)")
    items = _parse_trakt_file(raw, file.filename or "")
    if not items:
        raise HTTPException(400, "Nenhum item encontrado no arquivo")

    pro = await is_pro(user)
    current_count = await db.library.count_documents({"user_id": user_id})
    cap = None if pro else FREE_LIBRARY_CAP

    tc = await tmdb()
    added = 0
    skipped_cap = 0
    not_found: List[str] = []
    duplicates = 0

    # Cap parallelism to avoid TMDB rate limit and keep it within request budget
    semaphore = asyncio.Semaphore(8)

    async def resolve(it: Dict[str, Any]):
        async with semaphore:
            if it.get("tmdb_id"):
                try:
                    r = await tc.get(f"/tv/{it['tmdb_id']}", params={"language": TMDB_LANG})
                    if r.status_code == 200:
                        s = r.json()
                        return {
                            "tmdb_id": s.get("id"),
                            "name": s.get("name") or it["title"],
                            "poster_url": f"{TMDB_IMG}/w500{s.get('poster_path')}" if s.get("poster_path") else None,
                            "backdrop_url": f"{TMDB_IMG}/original{s.get('backdrop_path')}" if s.get("backdrop_path") else None,
                            "overview": s.get("overview"),
                            "status": _coerce_status(it.get("status")),
                        }
                except Exception:
                    pass
            # search by title (+year if available)
            try:
                params = {"query": it["title"], "language": TMDB_LANG, "include_adult": False}
                if it.get("year"):
                    params["first_air_date_year"] = it["year"]
                sr = await tc.get("/search/tv", params=params)
                if sr.status_code != 200:
                    return None
                results = sr.json().get("results") or []
                if not results and it.get("year"):
                    sr = await tc.get("/search/tv", params={"query": it["title"], "language": TMDB_LANG, "include_adult": False})
                    results = sr.json().get("results") or [] if sr.status_code == 200 else []
                if not results:
                    return None
                top = results[0]
                return {
                    "tmdb_id": top.get("id"),
                    "name": top.get("name") or it["title"],
                    "poster_url": f"{TMDB_IMG}/w500{top.get('poster_path')}" if top.get("poster_path") else None,
                    "backdrop_url": f"{TMDB_IMG}/original{top.get('backdrop_path')}" if top.get("backdrop_path") else None,
                    "overview": top.get("overview"),
                    "status": _coerce_status(it.get("status")),
                }
            except Exception:
                return None

    resolved = await asyncio.gather(*(resolve(it) for it in items[:300]))  # hard limit 300
    now = datetime.now(timezone.utc).isoformat()
    for src_item, found in zip(items[:300], resolved):
        if not found:
            not_found.append(src_item["title"])
            continue
        # Duplicate check
        existing = await db.library.find_one({"user_id": user_id, "tmdb_id": found["tmdb_id"]})
        if existing:
            duplicates += 1
            continue
        # Cap check (Free)
        if cap is not None and current_count >= cap:
            skipped_cap += 1
            continue
        await db.library.update_one(
            {"user_id": user_id, "tmdb_id": found["tmdb_id"]},
            {
                "$set": {
                    "user_id": user_id,
                    "tmdb_id": found["tmdb_id"],
                    "status": found["status"],
                    "name": found["name"],
                    "poster_url": found["poster_url"],
                    "backdrop_url": found["backdrop_url"],
                    "overview": found["overview"],
                    "updated_at": now,
                },
                "$setOnInsert": {"added_at": now, "imported_from": "trakt"},
            },
            upsert=True,
        )
        added += 1
        current_count += 1

    return {
        "total": len(items),
        "added": added,
        "duplicates": duplicates,
        "skipped_cap": skipped_cap,
        "not_found": not_found[:50],
        "not_found_count": len(not_found),
        "tier": "pro" if pro else "free",
        "cap": cap,
    }


# ---------------------- iCal Export ----------------------
def _ics_escape(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")


def _ics_fold(line: str) -> str:
    """Fold long lines per RFC 5545 (75 octets, continuation lines start with a space)."""
    if len(line) <= 73:
        return line
    out = []
    while len(line) > 73:
        out.append(line[:73])
        line = " " + line[73:]
    out.append(line)
    return "\r\n".join(out)


@api.get("/calendar/ical")
async def calendar_ical(request: Request, token: Optional[str] = None):
    """Returns user's upcoming/recent episodes as an iCalendar (.ics) feed.
    Authentication: prefers normal access cookie/Authorization header; ALSO accepts
    `?token=<jwt>` so Google Calendar / Apple Calendar subscriptions (which can't
    send custom headers) work. The token is a normal access JWT — same one used
    elsewhere — so users must keep their feed URL private.
    """
    # Auth — try cookie / bearer first; fallback to ?token
    try:
        user = await get_current_user(request)
    except Exception:
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

    user_id = str(user["_id"])
    items = await db.library.find({"user_id": user_id}).to_list(500)
    tc = await tmdb()
    events: list[str] = []
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    async def fetch_show(it: dict):
        try:
            r = await tc.get(f"/tv/{it['tmdb_id']}", params={"language": TMDB_LANG})
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    results = await asyncio.gather(*(fetch_show(it) for it in items))
    for it, s in zip(items, results):
        if not s:
            continue
        for ep in (s.get("next_episode_to_air"), s.get("last_episode_to_air")):
            if not ep or not ep.get("air_date"):
                continue
            try:
                d = datetime.strptime(ep["air_date"], "%Y-%m-%d").date()
            except Exception:
                continue
            dtstart = d.strftime("%Y%m%d")
            dtend = (d + timedelta(days=1)).strftime("%Y%m%d")
            uid = f"{it['tmdb_id']}-s{ep.get('season_number')}e{ep.get('episode_number')}@seriestrack"
            summary = f"{s.get('name')} — T{ep.get('season_number')}·E{ep.get('episode_number')}: {ep.get('name') or ''}".strip(": ")
            desc_parts = [ep.get("overview") or ""]
            if it.get("name"):
                desc_parts.append(f"Série: {it.get('name')}")
            desc = " — ".join([p for p in desc_parts if p])
            url = f"https://www.themoviedb.org/tv/{it['tmdb_id']}"
            ev = [
                "BEGIN:VEVENT",
                _ics_fold(f"UID:{uid}"),
                f"DTSTAMP:{now_stamp}",
                f"DTSTART;VALUE=DATE:{dtstart}",
                f"DTEND;VALUE=DATE:{dtend}",
                _ics_fold(f"SUMMARY:{_ics_escape(summary)}"),
                _ics_fold(f"DESCRIPTION:{_ics_escape(desc)}"),
                _ics_fold(f"URL:{url}"),
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
            events.append("\r\n".join(ev))

    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SeriesTrack//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:SeriesTrack — Próximos episódios",
        "X-WR-TIMEZONE:UTC",
        *events,
        "END:VCALENDAR",
    ]
    body = "\r\n".join(cal) + "\r\n"
    return Response(
        content=body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="seriestrack.ics"'},
    )


# Mount router & CORS
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # using Authorization header for cross-origin auth
    allow_methods=["*"],
    allow_headers=["*"],
)


# Note: On cross-origin (preview URL), browsers won't send httpOnly cookies set with SameSite=None
# unless allow_credentials is true with explicit origin. To keep things simple we ALSO return
# access_token in the JSON body, and frontend stores it and sends as Authorization: Bearer.


# ---------------------- Startup ----------------------
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
    global _http
    if _http is not None:
        await _http.aclose()
    client.close()
