"""Calendar + Notifications + iCal feed routes."""
from datetime import datetime, timezone, timedelta
from typing import Optional
import jwt
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from core import (
    db, logger, get_current_user, tmdb, tmdb_get_tv,
    JWT_SECRET, JWT_ALGO, TMDB_LANG, TMDB_IMG, TMDB_REGION,
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_CALENDAR_REDIRECT_URI,
)
from core import google_calendar as gcal
from core.models import GoogleCalendarConnectIn

router = APIRouter()


# ---------------------- Calendar / Upcoming (in-app) ----------------------
@router.get("/calendar/upcoming")
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
@router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = await db.notifications.find({"user_id": str(user["_id"])}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    return items


@router.post("/notifications/read_all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": str(user["_id"])}, {"$set": {"read": True}})
    return {"ok": True}


@router.get("/notifications/unread_count")
async def unread_count(user: dict = Depends(get_current_user)):
    n = await db.notifications.count_documents({"user_id": str(user["_id"]), "read": False})
    return {"count": n}


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


@router.post("/calendar/ical/feed")
async def mint_calendar_feed_token(request: Request, user: dict = Depends(get_current_user)):
    """Mint a long-lived (365d) read-only token for the iCal feed.
    Bumps the user's calendar_feed_version — invalidates any previously-issued feed token.
    Returns a full subscribe URL ready to paste into Google Calendar / Apple Calendar.
    """
    new_version = (user.get("calendar_feed_version") or 0) + 1
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"calendar_feed_version": new_version}},
    )
    exp = datetime.now(timezone.utc) + timedelta(days=365)
    feed_token = jwt.encode(
        {
            "sub": str(user["_id"]),
            "email": user["email"],
            "type": "calendar_feed",
            "feed_version": new_version,
            "exp": exp,
        },
        JWT_SECRET, algorithm=JWT_ALGO,
    )
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    base = f"{proto}://{host}" if host else str(request.base_url).rstrip("/")
    feed_url = f"{base.rstrip('/')}/api/calendar/ical?token={feed_token}"
    return {"token": feed_token, "feed_url": feed_url, "expires_at": exp.isoformat()}


@router.delete("/calendar/ical/feed")
async def revoke_calendar_feed_token(user: dict = Depends(get_current_user)):
    """Revoke ALL previously-minted feed tokens by bumping calendar_feed_version."""
    new_version = (user.get("calendar_feed_version") or 0) + 1
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"calendar_feed_version": new_version}},
    )
    return {"ok": True, "new_version": new_version}


@router.get("/calendar/ical")
async def calendar_ical(request: Request, token: Optional[str] = None):
    """Returns the user's upcoming/recent episodes as an iCalendar (.ics) feed.
    Accepts Authorization Bearer header OR ?token=<calendar_feed JWT>.
    Full access tokens are NOT accepted on ?token= for security.
    """
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
        if payload.get("type") != "calendar_feed":
            raise HTTPException(401, "Wrong token type — use /calendar/ical/feed to mint a scoped token")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(401, "User not found")
        if payload.get("feed_version") != user.get("calendar_feed_version", 1):
            raise HTTPException(401, "Feed token revoked")

    user_id = str(user["_id"])
    items = await db.library.find(
        {"user_id": user_id, "status": {"$in": ["watching", "want"]}}
    ).to_list(500)
    events: list[str] = []
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    import asyncio
    async def fetch_show(it: dict):
        return await tmdb_get_tv(it["tmdb_id"])

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


# ---------------------- Google Calendar push sync ----------------------
@router.get("/calendar/google/status")
async def google_calendar_status(user: dict = Depends(get_current_user)):
    connected = bool(user.get("google_calendar_refresh_token"))
    return {
        "connected": connected,
        "calendar_id": user.get("google_calendar_id") if connected else None,
        "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
    }


@router.post("/calendar/google/connect")
async def google_calendar_connect(payload: GoogleCalendarConnectIn, user: dict = Depends(get_current_user)):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(503, "Integração com Google Calendar não configurada no servidor.")
    if GOOGLE_CALENDAR_REDIRECT_URI and payload.redirect_uri != GOOGLE_CALENDAR_REDIRECT_URI:
        raise HTTPException(400, "redirect_uri não confere com o configurado no servidor.")
    try:
        tokens = await gcal.exchange_code(payload.code, payload.redirect_uri)
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    refresh_token = tokens["refresh_token"]
    access_token = tokens["access_token"]
    try:
        calendar_id = await gcal.ensure_calendar(access_token, user.get("google_calendar_id"))
    except RuntimeError as e:
        raise HTTPException(502, str(e))

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "google_calendar_refresh_token": refresh_token,
            "google_calendar_id": calendar_id,
            "google_calendar_connected_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    user = await db.users.find_one({"_id": user["_id"]})
    synced = await _sync_all_series(user)
    return {"ok": True, "calendar_id": calendar_id, "synced": synced}


@router.delete("/calendar/google/connect")
async def google_calendar_disconnect(user: dict = Depends(get_current_user)):
    rt = user.get("google_calendar_refresh_token")
    if rt:
        await gcal.revoke(rt)
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$unset": {"google_calendar_refresh_token": "", "google_calendar_id": ""}},
    )
    return {"ok": True}


async def _sync_all_series(user: dict) -> int:
    items = await db.library.find(
        {"user_id": str(user["_id"]), "status": {"$in": ["watching", "want"]}}
    ).to_list(500)
    import asyncio
    shows = await asyncio.gather(*(tmdb_get_tv(it["tmdb_id"]) for it in items))
    n = 0
    for it, show in zip(items, shows):
        if not show:
            continue
        await gcal.sync_series(user, it["tmdb_id"], it.get("name") or show.get("name") or "Série", show)
        n += 1
    return n


@router.post("/calendar/google/sync")
async def google_calendar_sync(user: dict = Depends(get_current_user)):
    if not user.get("google_calendar_refresh_token"):
        raise HTTPException(400, "Conecte o Google Calendar primeiro.")
    synced = await _sync_all_series(user)
    return {"ok": True, "synced": synced}
