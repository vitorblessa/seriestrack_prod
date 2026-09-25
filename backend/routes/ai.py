"""Pro-tier features: AI recommendations (Gemini), preview rec, advanced stats."""
import re
import json
import time
import asyncio
import hashlib
from collections import Counter
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from core import (
    db, logger, get_current_user, require_pro, tmdb, tmdb_get_tv,
    TMDB_LANG, TMDB_IMG, GEMINI_API_KEY, GEMINI_MODEL, LLM_AVAILABLE,
)

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:
    genai = None  # type: ignore
    genai_types = None  # type: ignore

router = APIRouter()


# ---------------------- AI preview rec (Free upsell hook) ----------------------
@router.get("/ai/preview_rec")
async def ai_preview_rec(user: dict = Depends(get_current_user)):
    """Return ONE recommendation preview for Free users — used as upsell hook on the Dashboard.
    Uses TMDB-native recommendations (no LLM cost) seeded by user's most-recent library item.
    """
    user_id = str(user["_id"])
    lib_items = await db.library.find({"user_id": user_id}, {"_id": 0}).sort("updated_at", -1).to_list(20)
    if not lib_items:
        return {"rec": None, "reason": "empty_library"}

    lib_ids = {it["tmdb_id"] for it in lib_items}
    tc = await tmdb()

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


# ---------------------- AI Recommendations (Pro) ----------------------
_AI_RECS_TTL = 10 * 60
_ai_recs_cache: dict = {}


def _ai_recs_cache_key(user_id: str, lib: list, reviews: list) -> str:
    sig_parts = sorted(f"{it.get('tmdb_id')}:{it.get('status','')}" for it in lib)
    sig_parts += sorted(f"r{r.get('tmdb_id')}:{r.get('rating')}" for r in reviews)
    return f"{user_id}:" + hashlib.md5("|".join(sig_parts).encode()).hexdigest()


@router.post("/ai/recommendations")
async def ai_recommendations(user: dict = Depends(require_pro)):
    if not LLM_AVAILABLE or not GEMINI_API_KEY:
        raise HTTPException(503, "Recomendações IA indisponíveis no momento")
    user_id = str(user["_id"])

    lib = await db.library.find({"user_id": user_id}, {"_id": 0}).limit(40).to_list(40)
    reviews = await db.reviews.find({"user_id": user_id}, {"_id": 0}).limit(20).to_list(20)
    if not lib and not reviews:
        return {"recommendations": [], "reason": "no_history"}

    cache_key = _ai_recs_cache_key(user_id, lib, reviews)
    cached = _ai_recs_cache.get(cache_key)
    if cached and cached[1] > time.time():
        return {**cached[0], "cached": True}

    seen_lines = [f"- {it.get('name')} ({it.get('status')})" for it in lib[:30]]
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
        client = genai.Client(api_key=GEMINI_API_KEY)
        resp = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                temperature=0.8,
                max_output_tokens=2048,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=0),
            ),
        )
        raw = resp.text
    except Exception as e:
        logger.warning(f"LLM recs failed: {e}")
        raise HTTPException(502, "Erro ao gerar recomendações")

    txt = (raw or "").strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.MULTILINE)
    try:
        data = json.loads(txt)
        recs = data.get("recommendations", [])[:5]
    except Exception:
        logger.warning(f"Bad LLM JSON: {txt[:300]}")
        raise HTTPException(502, "Resposta inválida do modelo")

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

    lib_ids = {it["tmdb_id"] for it in lib}
    for e in out:
        e["in_library"] = e["tmdb_id"] in lib_ids

    result = {"recommendations": out, "model": GEMINI_MODEL}
    _ai_recs_cache[cache_key] = (result, time.time() + _AI_RECS_TTL)
    if len(_ai_recs_cache) > 500:
        for k, _ in sorted(_ai_recs_cache.items(), key=lambda x: x[1][1])[:100]:
            _ai_recs_cache.pop(k, None)
    return {**result, "cached": False}


# ---------------------- Advanced Stats (Pro) ----------------------
@router.get("/stats/advanced")
async def advanced_stats(user: dict = Depends(require_pro)):
    user_id = str(user["_id"])
    progress = await db.progress.find({"user_id": user_id}, {"_id": 0}).to_list(20000)
    library = await db.library.find({"user_id": user_id}, {"_id": 0}).to_list(500)

    total_eps = len(progress)
    estimated_minutes = total_eps * 45
    estimated_hours = round(estimated_minutes / 60, 1)
    estimated_days = round(estimated_minutes / 60 / 24, 2)

    by_series: dict = {}
    for p in progress:
        by_series[p["tmdb_id"]] = by_series.get(p["tmdb_id"], 0) + 1
    series_name_map = {it["tmdb_id"]: it.get("name") for it in library}
    top_series = sorted(
        [{"tmdb_id": k, "name": series_name_map.get(k, f"Série {k}"), "episodes": v} for k, v in by_series.items()],
        key=lambda x: x["episodes"], reverse=True,
    )[:5]

    today = datetime.now(timezone.utc).date()
    cutoff = (today - timedelta(days=365)).isoformat()
    heat: dict = {}
    for p in progress:
        d = (p.get("watched_at") or "")[:10]
        if d and d >= cutoff:
            heat[d] = heat.get(d, 0) + 1
    heatmap = [{"date": k, "count": v} for k, v in sorted(heat.items())]

    async def fetch_genres(it: dict):
        s = await tmdb_get_tv(it["tmdb_id"])
        if not s:
            return []
        return [g.get("name") for g in (s.get("genres") or [])]
    genre_lists = await asyncio.gather(*(fetch_genres(it) for it in library[:50]))
    genre_counter = Counter()
    for gs in genre_lists:
        for g in gs:
            if g:
                genre_counter[g] += 1
    top_genres = [{"genre": g, "count": c} for g, c in genre_counter.most_common(10)]

    statuses = {}
    for st in ("watching", "paused", "finished", "want"):
        statuses[st] = sum(1 for it in library if it.get("status") == st)

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
