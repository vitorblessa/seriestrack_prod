"""TMDB series proxy routes: trending, popular, top_rated, airing_today, on_the_air, search, detail, season."""
from fastapi import APIRouter, HTTPException
from core import tmdb_get_cached, normalize_show, TMDB_LANG, TMDB_REGION, TMDB_IMG

router = APIRouter()

# Same TMDB content served to every user — cache generously to cut latency
# and stay well clear of TMDB's rate limit. Discovery lists change slowly;
# search is cached shorter since it's free-text (many distinct queries).
_LIST_TTL = 30 * 60
_SEARCH_TTL = 10 * 60
_DETAIL_TTL = 30 * 60
_SEASON_TTL = 60 * 60
_GENRES_TTL = 24 * 60 * 60
_DISCOVER_TTL = 30 * 60
_KEYWORD_TTL = 24 * 60 * 60


# A single TMDB keyword rarely covers how a whole sub-genre actually gets
# tagged — e.g. the marquee medical dramas (Grey's Anatomy, Chicago Med,
# House, The Good Doctor, New Amsterdam, ER) are split across a few
# different keywords rather than all carrying the exact same one. Search
# several related terms and OR their resolved ids together so popular shows
# don't fall through the cracks just because they're tagged "hospital"
# instead of "medical".
_KEYWORD_SYNONYMS = {
    "medical": ["medical", "hospital", "doctor", "medical drama"],
}


async def _resolve_keyword_ids(keyword: str) -> list:
    """TMDB has no official "Medical" TV genre, but it does have keywords
    medical dramas are tagged with. Resolve them by name instead of
    hardcoding ids, so this doesn't silently break if TMDB ever changes one."""
    terms = _KEYWORD_SYNONYMS.get(keyword.lower(), [keyword])
    ids: list = []
    for term in terms:
        data = await tmdb_get_cached(f"keyword_search:{term.lower()}", "/search/keyword", {"query": term}, _KEYWORD_TTL)
        results = (data or {}).get("results") or []
        if not results:
            continue
        exact = next((r for r in results if (r.get("name") or "").lower() == term.lower()), None)
        chosen = exact or results[0]
        kw_id = chosen.get("id")
        if kw_id is not None and kw_id not in ids:
            ids.append(kw_id)
    return ids


@router.get("/series/trending")
async def trending(window: str = "week"):
    data = await tmdb_get_cached(f"trending:{window}", f"/trending/tv/{window}", {"language": TMDB_LANG}, _LIST_TTL)
    if data is None:
        raise HTTPException(502, "TMDB request failed")
    return [normalize_show(x) for x in data.get("results", [])][:20]


@router.get("/series/popular")
async def popular():
    data = await tmdb_get_cached("popular", "/tv/popular", {"language": TMDB_LANG, "region": TMDB_REGION}, _LIST_TTL)
    if data is None:
        raise HTTPException(502, "TMDB request failed")
    return [normalize_show(x) for x in data.get("results", [])][:20]


@router.get("/series/top_rated")
async def top_rated():
    data = await tmdb_get_cached("top_rated", "/tv/top_rated", {"language": TMDB_LANG}, _LIST_TTL)
    if data is None:
        raise HTTPException(502, "TMDB request failed")
    return [normalize_show(x) for x in data.get("results", [])][:20]


@router.get("/series/airing_today")
async def airing_today():
    data = await tmdb_get_cached("airing_today", "/tv/airing_today", {"language": TMDB_LANG}, _LIST_TTL)
    if data is None:
        raise HTTPException(502, "TMDB request failed")
    return [normalize_show(x) for x in data.get("results", [])][:20]


@router.get("/series/on_the_air")
async def on_the_air():
    data = await tmdb_get_cached("on_the_air", "/tv/on_the_air", {"language": TMDB_LANG}, _LIST_TTL)
    if data is None:
        raise HTTPException(502, "TMDB request failed")
    return [normalize_show(x) for x in data.get("results", [])][:20]


@router.get("/series/genres")
async def genres():
    """TV genre list for the discovery filter chips — barely ever changes,
    so it's cached for a full day."""
    data = await tmdb_get_cached("genres", "/genre/tv/list", {"language": TMDB_LANG}, _GENRES_TTL)
    if data is None:
        raise HTTPException(502, "TMDB request failed")
    return data.get("genres", [])


@router.get("/series/discover")
async def discover(genre: int = None, keyword: str = None, sort_by: str = "popularity.desc"):
    """Genre-filtered discovery — powers the "Filtrar por gênero" chips on
    the search/discovery page. sort_by accepts any TMDB discover sort value
    (popularity.desc, vote_average.desc, first_air_date.desc, ...).

    `keyword` powers pseudo-genre chips TMDB doesn't model as real genres —
    e.g. "médicas" (medical dramas), which is a TMDB keyword, not a genre."""
    allowed_sorts = {
        "popularity.desc", "vote_average.desc", "first_air_date.desc", "name.asc",
    }
    if sort_by not in allowed_sorts:
        sort_by = "popularity.desc"
    params = {
        "language": TMDB_LANG,
        "sort_by": sort_by,
        "vote_count.gte": 20,  # keeps vote_average.desc from surfacing obscure 1-vote shows
    }
    if genre:
        params["with_genres"] = genre
    if keyword:
        kw_ids = await _resolve_keyword_ids(keyword)
        if kw_ids:
            # TMDB's "|" means OR across keywords — any show tagged with any one of them matches.
            params["with_keywords"] = "|".join(str(i) for i in kw_ids)
    cache_key = f"discover_genre:{genre or 'all'}:{keyword or 'none'}:{sort_by}"
    data = await tmdb_get_cached(cache_key, "/discover/tv", params, _DISCOVER_TTL)
    if data is None:
        raise HTTPException(502, "TMDB request failed")
    return [normalize_show(x) for x in data.get("results", [])][:40]


@router.get("/series/search")
async def search(q: str):
    query = q.strip()
    if not query:
        return []
    data = await tmdb_get_cached(
        f"search:{query.lower()}", "/search/tv",
        {"query": query, "language": TMDB_LANG, "include_adult": False}, _SEARCH_TTL,
    )
    if data is None:
        raise HTTPException(502, "TMDB request failed")
    return [normalize_show(x) for x in data.get("results", [])]


@router.get("/series/{tmdb_id}")
async def series_detail(tmdb_id: int):
    s = await tmdb_get_cached(
        f"detail:{tmdb_id}", f"/tv/{tmdb_id}",
        {"language": TMDB_LANG, "append_to_response": "watch/providers,credits,videos,recommendations,external_ids"},
        _DETAIL_TTL,
    )
    if s is None:
        raise HTTPException(404, "Series not found")

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


@router.get("/series/{tmdb_id}/season/{season_number}")
async def season_detail(tmdb_id: int, season_number: int):
    s = await tmdb_get_cached(
        f"season:{tmdb_id}:{season_number}", f"/tv/{tmdb_id}/season/{season_number}",
        {"language": TMDB_LANG}, _SEASON_TTL,
    )
    if s is None:
        raise HTTPException(404, "Season not found")
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
