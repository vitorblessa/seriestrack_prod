from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

import bcrypt
import jwt
import httpx
from bson import ObjectId
from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, EmailStr, Field

try:
    from pywebpush import webpush, WebPushException
    PUSH_AVAILABLE = True
except Exception:
    PUSH_AVAILABLE = False

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
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "name": doc.get("name", ""),
        "avatar_url": doc.get("avatar_url"),
        "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
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
@api.get("/streaming/episodes")
async def streaming_episodes(name: str, user: dict = Depends(get_current_user)):
    """Return the most recent episodes (recent + upcoming) for series in the user's library
    that are available on a streaming platform whose name contains `name` (case-insensitive).
    Sorted by air_date descending (most recent first).
    """
    user_id = str(user["_id"])
    items = await db.library.find({"user_id": user_id}).to_list(500)
    if not items:
        return {"matched_providers": [], "episodes": []}

    needle = name.strip().lower()
    if not needle:
        return {"matched_providers": [], "episodes": []}

    tc = await tmdb()
    matched_provider_set = set()
    out: list = []

    async def fetch(it: dict):
        try:
            r = await tc.get(
                f"/tv/{it['tmdb_id']}",
                params={"language": TMDB_LANG, "append_to_response": "watch/providers"},
            )
            if r.status_code != 200:
                return None
            return it, r.json()
        except Exception:
            return None

    results = await asyncio.gather(*(fetch(it) for it in items))
    for entry in results:
        if not entry:
            continue
        it, s = entry
        providers_block = (s.get("watch/providers", {}) or {}).get("results", {}) or {}
        region_block = providers_block.get(TMDB_REGION) or providers_block.get("US") or {}
        flatrate = region_block.get("flatrate") or []
        provider_names = [p.get("provider_name") for p in flatrate if p.get("provider_name")]

        # Match: any provider's name contains the search term (or vice versa)
        match_names = [p for p in provider_names if needle in p.lower()]
        if not match_names:
            continue
        for mn in match_names:
            matched_provider_set.add(mn)

        nxt = s.get("next_episode_to_air")
        last = s.get("last_episode_to_air")
        for ep, kind in [(nxt, "upcoming"), (last, "recent")]:
            if not ep or not ep.get("air_date"):
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
                "matched_providers": match_names,
            })

    out.sort(key=lambda x: x.get("air_date") or "", reverse=True)
    return {
        "matched_providers": sorted(matched_provider_set),
        "episodes": out,
    }


# ---------------------- Health ----------------------
@api.get("/")
async def root():
    return {"app": "SeriesTrack", "version": "1.0.0"}


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
