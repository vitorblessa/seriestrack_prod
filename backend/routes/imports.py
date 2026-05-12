"""Trakt import — parse CSV/JSON exports and bulk-add to user library."""
import re
import json
import asyncio
import csv as _csv
from io import StringIO
from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from core import (
    db, get_current_user, is_pro, tmdb, tmdb_get_tv,
    TMDB_LANG, TMDB_IMG, FREE_LIBRARY_CAP,
)

router = APIRouter()


def _normalize_trakt_title(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _parse_trakt_file(content: bytes, filename: str) -> List[Dict[str, Any]]:
    """Parse a Trakt export (JSON list/object OR CSV)."""
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
        reader = _csv.DictReader(StringIO(text))
        if not reader.fieldnames:
            return []
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
    if s in ("watched", "completed", "ended"):
        return "finished"
    if s in ("watchlist", "plan_to_watch", "plan-to-watch"):
        return "want"
    if s in ("on_hold", "on-hold", "hold"):
        return "paused"
    return "want"


@router.post("/import/trakt")
async def import_trakt(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """Upload a Trakt export (CSV or JSON) and bulk-add to library."""
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

    semaphore = asyncio.Semaphore(8)

    async def resolve(it: Dict[str, Any]):
        async with semaphore:
            if it.get("tmdb_id"):
                s = await tmdb_get_tv(it["tmdb_id"])
                if s:
                    return {
                        "tmdb_id": s.get("id"),
                        "name": s.get("name") or it["title"],
                        "poster_url": f"{TMDB_IMG}/w500{s.get('poster_path')}" if s.get("poster_path") else None,
                        "backdrop_url": f"{TMDB_IMG}/original{s.get('backdrop_path')}" if s.get("backdrop_path") else None,
                        "overview": s.get("overview"),
                        "status": _coerce_status(it.get("status")),
                    }
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

    resolved = await asyncio.gather(*(resolve(it) for it in items[:300]))
    now = datetime.now(timezone.utc).isoformat()
    for src_item, found in zip(items[:300], resolved):
        if not found:
            not_found.append(src_item["title"])
            continue
        existing = await db.library.find_one({"user_id": user_id, "tmdb_id": found["tmdb_id"]})
        if existing:
            duplicates += 1
            continue
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
