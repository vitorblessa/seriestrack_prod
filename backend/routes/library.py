"""Library + Progress + Reviews + Public-profile + Limits routes."""
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends
from core import (
    db, logger, get_current_user, is_pro, tmdb, tmdb_get_tv,
    TMDB_LANG, TMDB_IMG, FREE_LIBRARY_CAP,
)
from core.models import LibraryUpsertIn, ProgressIn, ProgressBulkIn, ReviewIn

router = APIRouter()


# ---------------------- Library ----------------------
@router.get("/library")
async def get_library(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"user_id": str(user["_id"])}
    if status:
        q["status"] = status
    items = await db.library.find(q, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return items


@router.post("/library")
async def upsert_library(payload: LibraryUpsertIn, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
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

    name = payload.name
    poster_url = payload.poster_url
    backdrop_url = payload.backdrop_url
    overview = payload.overview
    if not name or not poster_url:
        try:
            s = await tmdb_get_tv(payload.tmdb_id)
            if s:
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


@router.delete("/library/{tmdb_id}")
async def remove_library(tmdb_id: int, user: dict = Depends(get_current_user)):
    await db.library.delete_one({"user_id": str(user["_id"]), "tmdb_id": tmdb_id})
    return {"ok": True}


@router.get("/library/contains/{tmdb_id}")
async def library_contains(tmdb_id: int, user: dict = Depends(get_current_user)):
    item = await db.library.find_one({"user_id": str(user["_id"]), "tmdb_id": tmdb_id}, {"_id": 0})
    return {"in_library": bool(item), "item": item}


# ---------------------- Episode progress ----------------------
@router.post("/progress")
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


@router.get("/progress/{tmdb_id}")
async def get_progress(tmdb_id: int, user: dict = Depends(get_current_user)):
    items = await db.progress.find(
        {"user_id": str(user["_id"]), "tmdb_id": tmdb_id}, {"_id": 0}
    ).to_list(2000)
    return items


@router.post("/progress/bulk")
async def bulk_progress(payload: ProgressBulkIn, user: dict = Depends(get_current_user)):
    """Mark ALL episodes of a season as watched (or unwatched)."""
    user_id = str(user["_id"])
    if payload.watched:
        tc = await tmdb()
        r = await tc.get(f"/tv/{payload.tmdb_id}/season/{payload.season}", params={"language": TMDB_LANG})
        if r.status_code != 200:
            raise HTTPException(404, "Season not found")
        episodes = r.json().get("episodes", [])
        if not episodes:
            return {"updated": 0, "watched": True}
        now = datetime.now(timezone.utc).isoformat()
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
    result = await db.progress.delete_many({
        "user_id": user_id,
        "tmdb_id": payload.tmdb_id,
        "season": payload.season,
    })
    return {"deleted": result.deleted_count, "watched": False}


@router.get("/progress/{tmdb_id}/summary")
async def progress_summary(tmdb_id: int, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    s = await tmdb_get_tv(tmdb_id)
    if not s:
        raise HTTPException(404, "Series not found")
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


# ---------------------- Reviews ----------------------
@router.post("/reviews")
async def upsert_review(payload: ReviewIn, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "user_id": user_id,
        "user_name": user.get("name") or "Anônimo",
        "user_avatar": user.get("avatar_url"),
        "user_is_pro": await is_pro(user),
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


@router.delete("/reviews/{tmdb_id}")
async def delete_review(tmdb_id: int, user: dict = Depends(get_current_user)):
    await db.reviews.delete_one({"user_id": str(user["_id"]), "tmdb_id": tmdb_id})
    return {"ok": True}


@router.get("/reviews/{tmdb_id}")
async def list_reviews(tmdb_id: int):
    items = await db.reviews.find({"tmdb_id": tmdb_id}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    # Enrich each review with current is_pro status (cheap — reviews list is bounded at 200)
    if items:
        user_ids = list({r["user_id"] for r in items if r.get("user_id")})
        users = await db.users.find(
            {"_id": {"$in": [ObjectId(uid) for uid in user_ids]}},
            {"_id": 1, "subscription_tier": 1, "subscription_renews_at": 1, "avatar_url": 1},
        ).to_list(len(user_ids))
        now = datetime.now(timezone.utc)
        pro_map: dict = {}
        avatar_map: dict = {}
        for u in users:
            uid = str(u["_id"])
            avatar_map[uid] = u.get("avatar_url")
            renews = u.get("subscription_renews_at")
            try:
                if isinstance(renews, str):
                    renews = datetime.fromisoformat(renews)
                if renews and renews.tzinfo is None:
                    renews = renews.replace(tzinfo=timezone.utc)
                pro_map[uid] = u.get("subscription_tier") == "pro" and renews and renews > now
            except Exception:
                pro_map[uid] = False
        for r in items:
            r["user_is_pro"] = bool(pro_map.get(r["user_id"], False))
            if not r.get("user_avatar"):
                r["user_avatar"] = avatar_map.get(r["user_id"])
    avg = None
    if items:
        avg = round(sum(r["rating"] for r in items) / len(items), 2)
    return {"reviews": items, "average": avg, "count": len(items)}


@router.get("/reviews/{tmdb_id}/mine")
async def my_review(tmdb_id: int, user: dict = Depends(get_current_user)):
    item = await db.reviews.find_one({"user_id": str(user["_id"]), "tmdb_id": tmdb_id}, {"_id": 0})
    return item or {}


# ---------------------- Public profile / shared library ----------------------
@router.get("/users/{user_id}/public")
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
        "is_pro": await is_pro(u),
        "joined_at": (u.get("created_at").isoformat() if isinstance(u.get("created_at"), datetime) else u.get("created_at")),
        "stats": counts,
        "recent_reviews": recent_reviews,
    }


@router.get("/users/{user_id}/library")
async def public_library(user_id: str, status: Optional[str] = None):
    q = {"user_id": user_id}
    if status:
        q["status"] = status
    items = await db.library.find(q, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return items


# ---------------------- Stats & Limits ----------------------
@router.get("/stats")
async def stats(user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    counts = {}
    for st in ("watching", "paused", "finished", "want"):
        counts[st] = await db.library.count_documents({"user_id": user_id, "status": st})
    counts["total"] = sum(counts.values())
    return counts


@router.get("/limits")
async def usage_limits(user: dict = Depends(get_current_user)):
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
