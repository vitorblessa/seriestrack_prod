"""Year-in-review 'Wrapped' endpoint — Spotify-style stats for the year."""
import asyncio
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends
from core import db, get_current_user, tmdb_get_tv, TMDB_REGION, TMDB_IMG

router = APIRouter()

# Approximate runtime per episode when TMDB does not provide it.
DEFAULT_RUNTIME_MIN = 45

# Localized day-of-week labels (pt-BR), Monday-first.
WEEKDAY_LABELS_PT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
MONTH_LABELS_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _date_range_for_year(year: int):
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    return start, end


async def _build_wrapped(user_id: str, year: int) -> dict:
    start, end = _date_range_for_year(year)

    # Pull ALL progress for the year (date-string compare on watched_at[:10])
    progress = await db.progress.find(
        {"user_id": user_id},
        {"_id": 0},
    ).to_list(50000)
    year_progress = [p for p in progress if start <= (p.get("watched_at") or "")[:10] <= end]

    if not year_progress:
        return {
            "year": year,
            "empty": True,
            "message": f"Você ainda não assistiu nada em {year}. Bora marcar uns episódios?",
        }

    total_eps = len(year_progress)
    estimated_minutes = total_eps * DEFAULT_RUNTIME_MIN
    estimated_hours = round(estimated_minutes / 60, 1)
    estimated_days = round(estimated_minutes / 60 / 24, 2)

    # Episodes per series
    by_series: dict = {}
    for p in year_progress:
        by_series[p["tmdb_id"]] = by_series.get(p["tmdb_id"], 0) + 1

    library = await db.library.find({"user_id": user_id}, {"_id": 0}).to_list(500)
    lib_map = {it["tmdb_id"]: it for it in library}

    top_series_ids = sorted(by_series.items(), key=lambda x: x[1], reverse=True)[:5]
    top_series = []
    for tid, count in top_series_ids:
        lib_item = lib_map.get(tid) or {}
        top_series.append({
            "tmdb_id": tid,
            "name": lib_item.get("name") or f"Série {tid}",
            "poster_url": lib_item.get("poster_url"),
            "episodes": count,
            "estimated_hours": round((count * DEFAULT_RUNTIME_MIN) / 60, 1),
        })

    # Day-of-week + month distribution (ISO weekday 1..7 = Mon..Sun)
    dow_counter = Counter()
    month_counter = Counter()
    daily_counter: dict = {}
    for p in year_progress:
        d_iso = (p.get("watched_at") or "")[:10]
        try:
            d = datetime.strptime(d_iso, "%Y-%m-%d").date()
        except Exception:
            continue
        dow_counter[d.isoweekday()] += 1  # 1=Mon
        month_counter[d.month] += 1
        daily_counter[d_iso] = daily_counter.get(d_iso, 0) + 1

    top_dow_idx = max(dow_counter, key=dow_counter.get) if dow_counter else 1
    top_month_idx = max(month_counter, key=month_counter.get) if month_counter else 1
    top_dow = {
        "label": WEEKDAY_LABELS_PT[top_dow_idx - 1],
        "count": dow_counter[top_dow_idx] if dow_counter else 0,
        "iso_day": top_dow_idx,
    }
    top_month = {
        "label": MONTH_LABELS_PT[top_month_idx - 1],
        "count": month_counter[top_month_idx] if month_counter else 0,
        "number": top_month_idx,
    }

    # Longest watching streak (consecutive days with at least 1 episode)
    days_sorted = sorted(daily_counter.keys())
    longest_streak = 0
    current_streak = 0
    prev_d = None
    for ds in days_sorted:
        d = datetime.strptime(ds, "%Y-%m-%d").date()
        if prev_d and (d - prev_d).days == 1:
            current_streak += 1
        else:
            current_streak = 1
        longest_streak = max(longest_streak, current_streak)
        prev_d = d

    # Biggest single-day binge
    biggest_day = max(daily_counter.items(), key=lambda x: x[1]) if daily_counter else (None, 0)

    # First + last episode of the year
    sorted_progress = sorted(year_progress, key=lambda p: (p.get("watched_at") or ""))
    first = sorted_progress[0]
    last = sorted_progress[-1]

    def _ep_card(p: dict) -> dict:
        tid = p["tmdb_id"]
        it = lib_map.get(tid) or {}
        return {
            "tmdb_id": tid,
            "name": it.get("name") or f"Série {tid}",
            "poster_url": it.get("poster_url"),
            "season": p.get("season"),
            "episode": p.get("episode"),
            "watched_at": (p.get("watched_at") or "")[:10],
        }

    # Genre breakdown — only TOP-10 most-watched series in the year (saves TMDB calls)
    top_for_genres = [tid for tid, _ in sorted(by_series.items(), key=lambda x: x[1], reverse=True)[:10]]

    async def fetch_genres(tid: int):
        s = await tmdb_get_tv(tid)
        if not s:
            return []
        return [g.get("name") for g in (s.get("genres") or [])]

    genre_lists = await asyncio.gather(*(fetch_genres(t) for t in top_for_genres))
    genre_counter = Counter()
    for tid, genres in zip(top_for_genres, genre_lists):
        weight = by_series.get(tid, 1)
        for g in genres:
            if g:
                genre_counter[g] += weight
    top_genres = [{"genre": g, "weight": c} for g, c in genre_counter.most_common(5)]

    # Favorite streaming platform — derive from provider on user's top-10 watched series
    async def fetch_providers(tid: int):
        s = await tmdb_get_tv(tid)
        if not s:
            return []
        block = (s.get("watch/providers", {}) or {}).get("results", {}).get(TMDB_REGION) or {}
        return [p.get("provider_name") for p in (block.get("flatrate") or []) if p.get("provider_name")]

    # tmdb_get_tv doesn't include watch/providers — we just skip streaming detection if not present.
    # (Wrapped is shareable / public; we can return empty list — frontend will hide the card.)
    top_streaming: list = []

    # Library counts at year-end (snapshot)
    statuses = {}
    for st in ("watching", "paused", "finished", "want"):
        statuses[st] = sum(1 for it in library if it.get("status") == st)

    # Total reviews + average rating given
    reviews = await db.reviews.find({"user_id": user_id}, {"_id": 0}).to_list(500)
    year_reviews = [r for r in reviews if start <= (r.get("created_at") or r.get("updated_at") or "")[:10] <= end]
    avg_rating = round(sum(r["rating"] for r in year_reviews) / len(year_reviews), 2) if year_reviews else None

    return {
        "year": year,
        "empty": False,
        "totals": {
            "episodes": total_eps,
            "estimated_minutes": estimated_minutes,
            "estimated_hours": estimated_hours,
            "estimated_days": estimated_days,
            "unique_series": len(by_series),
            "library_size": len(library),
            "library_breakdown": statuses,
        },
        "top_series": top_series,
        "top_genres": top_genres,
        "top_streaming": top_streaming,
        "top_day_of_week": top_dow,
        "top_month": top_month,
        "longest_streak_days": longest_streak,
        "biggest_binge": {"date": biggest_day[0], "episodes": biggest_day[1]} if biggest_day[0] else None,
        "first_episode": _ep_card(first),
        "last_episode": _ep_card(last),
        "reviews": {"count": len(year_reviews), "average_rating": avg_rating},
    }


@router.get("/wrapped/{year}")
async def my_wrapped(year: int, user: dict = Depends(get_current_user)):
    if year < 2000 or year > datetime.now(timezone.utc).year + 1:
        raise HTTPException(400, "Ano inválido")
    return await _build_wrapped(str(user["_id"]), year)


@router.get("/wrapped/{year}/share/{user_id}")
async def public_wrapped(year: int, user_id: str):
    """Public sharable wrapped — anyone with the link can view a user's year-in-review."""
    if year < 2000 or year > datetime.now(timezone.utc).year + 1:
        raise HTTPException(400, "Ano inválido")
    try:
        u = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(404, "User not found")
    if not u:
        raise HTTPException(404, "User not found")
    wrapped = await _build_wrapped(user_id, year)
    return {
        **wrapped,
        "user": {
            "name": u.get("name"),
            "avatar_url": u.get("avatar_url"),
            "id": user_id,
        },
    }
