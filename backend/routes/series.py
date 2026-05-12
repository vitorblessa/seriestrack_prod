"""TMDB series proxy routes: trending, popular, top_rated, airing_today, on_the_air, search, detail, season."""
from fastapi import APIRouter, HTTPException
from core import tmdb, normalize_show, TMDB_LANG, TMDB_REGION, TMDB_IMG

router = APIRouter()


@router.get("/series/trending")
async def trending(window: str = "week"):
    tc = await tmdb()
    r = await tc.get(f"/trending/tv/{window}", params={"language": TMDB_LANG})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@router.get("/series/popular")
async def popular():
    tc = await tmdb()
    r = await tc.get("/tv/popular", params={"language": TMDB_LANG, "region": TMDB_REGION})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@router.get("/series/top_rated")
async def top_rated():
    tc = await tmdb()
    r = await tc.get("/tv/top_rated", params={"language": TMDB_LANG})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@router.get("/series/airing_today")
async def airing_today():
    tc = await tmdb()
    r = await tc.get("/tv/airing_today", params={"language": TMDB_LANG})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@router.get("/series/on_the_air")
async def on_the_air():
    tc = await tmdb()
    r = await tc.get("/tv/on_the_air", params={"language": TMDB_LANG})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])][:20]


@router.get("/series/search")
async def search(q: str):
    if not q.strip():
        return []
    tc = await tmdb()
    r = await tc.get("/search/tv", params={"query": q, "language": TMDB_LANG, "include_adult": False})
    r.raise_for_status()
    return [normalize_show(x) for x in r.json().get("results", [])]


@router.get("/series/{tmdb_id}")
async def series_detail(tmdb_id: int):
    tc = await tmdb()
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


@router.get("/series/{tmdb_id}/season/{season_number}")
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
