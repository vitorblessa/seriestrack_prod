"""TMDB HTTP client + in-process cache for /tv/{id} responses."""
import time
from typing import Optional
import httpx
from .config import TMDB_TOKEN, TMDB_BASE, TMDB_LANG, TMDB_IMG

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


async def close_tmdb():
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


# In-process cache for TMDB /tv/{id} responses (no append_to_response).
# Used by hot paths that fetch the same show repeatedly: calendar/upcoming, ical,
# notify_today, import_trakt, advanced_stats genre_lookup, etc.
_TV_CACHE_TTL = 30 * 60
_tv_show_cache: dict = {}


async def tmdb_get_tv(tmdb_id: int) -> Optional[dict]:
    """Cached fetch of /tv/{id}. Returns None on non-200."""
    now = time.time()
    entry = _tv_show_cache.get(tmdb_id)
    if entry and entry[1] > now:
        return entry[0]
    try:
        tc = await tmdb()
        r = await tc.get(f"/tv/{tmdb_id}", params={"language": TMDB_LANG})
        if r.status_code != 200:
            return None
        data = r.json()
        _tv_show_cache[tmdb_id] = (data, now + _TV_CACHE_TTL)
        if len(_tv_show_cache) > 2000:
            for k, _ in sorted(_tv_show_cache.items(), key=lambda x: x[1][1])[:500]:
                _tv_show_cache.pop(k, None)
        return data
    except Exception:
        return None


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
