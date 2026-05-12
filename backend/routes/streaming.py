"""Streaming-platform discovery (/streaming/episodes) — global TMDB discover by provider."""
import re
import time
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from core import (
    db, logger, get_current_user, tmdb, tmdb_get_tv,
    TMDB_LANG, TMDB_REGION, TMDB_IMG,
)

router = APIRouter()


def _normalize_provider(s: str) -> str:
    """Normalize provider name for fuzzy matching."""
    n = (s or "").lower().strip()
    n = n.replace("+", " plus ")
    n = re.sub(r"\bplus\b", " ", n)
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _provider_matches(needle_norm: str, provider_norm: str) -> bool:
    if not needle_norm or not provider_norm:
        return False
    if needle_norm == provider_norm:
        return True
    n_words = needle_norm.split()
    p_words = provider_norm.split()
    if len(n_words) > len(p_words):
        return False
    if "channel" in p_words and "channel" not in n_words:
        return False
    if p_words[: len(n_words)] == n_words:
        return True
    if p_words[-len(n_words):] == n_words:
        return True
    return False


_tv_providers_cache: dict = {"data": None, "ts": 0.0}


async def _resolve_provider_ids(needle_norm: str):
    now = time.time()
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


@router.get("/streaming/episodes")
async def streaming_episodes(name: str, user: dict = Depends(get_current_user)):
    """Discover popular shows on a streaming platform and return their latest episodes."""
    needle_norm = _normalize_provider(name)
    if not needle_norm:
        return {"matched_providers": [], "episodes": []}

    provider_ids, matched_names = await _resolve_provider_ids(needle_norm)
    if not provider_ids:
        return {"matched_providers": [], "episodes": []}

    tc = await tmdb()
    today = datetime.now(timezone.utc).date()
    min_date = (today - timedelta(days=60)).isoformat()
    max_date = (today + timedelta(days=30)).isoformat()

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
            s = await tmdb_get_tv(show["id"])
            if not s:
                return []
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
    user_id = str(user["_id"])
    lib_ids = {it["tmdb_id"] for it in await db.library.find({"user_id": user_id}, {"_id": 0, "tmdb_id": 1}).to_list(500)}
    for e in episodes:
        e["in_library"] = e["tmdb_id"] in lib_ids
    return {
        "matched_providers": sorted(set(matched_names)),
        "episodes": episodes[:30],
    }
