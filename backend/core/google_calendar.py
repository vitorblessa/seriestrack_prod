"""Google Calendar push sync.

Separate from the login OAuth (core/config.py GOOGLE_CLIENT_ID / routes/auth.py),
which only ever sees a short-lived ID token. This module does the full
authorization-code flow (offline access) so we can hold a refresh token per
user and push calendar events on our own schedule — see routes/calendar_routes.py
for the /calendar/google/* endpoints and routes/library.py for where events get
pushed/removed as the user's library changes.
"""
import httpx
from typing import Optional
from .config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, logger
from .db import db

TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"
CALENDAR_NAME = "SeriesTrack"

_http: Optional[httpx.AsyncClient] = None


async def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=20.0)
    return _http


async def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange a fresh authorization code for access_token + refresh_token.
    Only returns a refresh_token if the frontend asked for offline access +
    consent prompt (see CalendarConnect.jsx) — raises if it's missing, since
    without it we can't sync in the background at all.
    """
    hc = await _client()
    r = await hc.post(TOKEN_URL, data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })
    if r.status_code != 200:
        logger.warning(f"google calendar code exchange failed: {r.status_code} {r.text[:300]}")
        raise RuntimeError("Falha ao trocar código de autorização com o Google")
    data = r.json()
    if not data.get("refresh_token"):
        raise RuntimeError("Google não retornou permissão offline — tente conectar de novo")
    return data


async def _refresh_access_token(refresh_token: str) -> str:
    hc = await _client()
    r = await hc.post(TOKEN_URL, data={
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "grant_type": "refresh_token",
    })
    if r.status_code != 200:
        logger.warning(f"google calendar token refresh failed: {r.status_code} {r.text[:300]}")
        raise RuntimeError("Sessão do Google Calendar expirada — reconecte")
    return r.json()["access_token"]


async def revoke(refresh_token: str):
    hc = await _client()
    try:
        await hc.post(REVOKE_URL, data={"token": refresh_token})
    except Exception as e:
        logger.warning(f"google calendar revoke failed (ignoring): {e}")


async def _get_access_token_for_user(user: dict) -> Optional[str]:
    rt = user.get("google_calendar_refresh_token")
    if not rt:
        return None
    try:
        return await _refresh_access_token(rt)
    except Exception as e:
        logger.warning(f"could not refresh google calendar token for user {user.get('_id')}: {e}")
        return None


async def ensure_calendar(access_token: str, existing_calendar_id: Optional[str]) -> str:
    """Return the id of the user's 'SeriesTrack' secondary calendar, creating it
    if needed. Keeping a separate calendar (rather than writing into the user's
    primary one) means they can hide/delete it independently."""
    hc = await _client()
    headers = {"Authorization": f"Bearer {access_token}"}
    if existing_calendar_id:
        r = await hc.get(f"{CALENDAR_API}/calendars/{existing_calendar_id}", headers=headers)
        if r.status_code == 200:
            return existing_calendar_id
        # Fall through and (re)create if it 404'd (user deleted it on Google's side)
    r = await hc.post(f"{CALENDAR_API}/calendars", headers=headers, json={"summary": CALENDAR_NAME})
    if r.status_code not in (200, 201):
        logger.warning(f"google calendar create failed: {r.status_code} {r.text[:300]}")
        raise RuntimeError("Não foi possível criar o calendário no Google")
    return r.json()["id"]


def _event_body(summary: str, description: str, date_str: str, end_date_str: str, url: str) -> dict:
    return {
        "summary": summary,
        "description": description,
        "start": {"date": date_str},
        "end": {"date": end_date_str},
        "source": {"title": "TMDB", "url": url},
    }


async def upsert_event(
    user: dict, calendar_id: str, google_event_id: Optional[str],
    summary: str, description: str, date_str: str, end_date_str: str, url: str,
) -> Optional[str]:
    """Create or update one event. Returns the Google event id (store it so we
    can update/delete this exact event later), or None if the user isn't
    connected / the call failed (best-effort — never raises)."""
    access_token = await _get_access_token_for_user(user)
    if not access_token:
        return None
    hc = await _client()
    headers = {"Authorization": f"Bearer {access_token}"}
    body = _event_body(summary, description, date_str, end_date_str, url)
    try:
        if google_event_id:
            r = await hc.patch(
                f"{CALENDAR_API}/calendars/{calendar_id}/events/{google_event_id}",
                headers=headers, json=body,
            )
            if r.status_code == 200:
                return r.json()["id"]
            if r.status_code not in (404, 410):
                logger.warning(f"google calendar event update failed: {r.status_code} {r.text[:300]}")
                return google_event_id
            # 404/410 — the event was deleted on Google's side; fall through and recreate
        r = await hc.post(f"{CALENDAR_API}/calendars/{calendar_id}/events", headers=headers, json=body)
        if r.status_code in (200, 201):
            return r.json()["id"]
        logger.warning(f"google calendar event create failed: {r.status_code} {r.text[:300]}")
        return None
    except Exception as e:
        logger.warning(f"google calendar upsert_event error: {e}")
        return None


async def delete_event(user: dict, calendar_id: str, google_event_id: str):
    """Best-effort delete — never raises."""
    access_token = await _get_access_token_for_user(user)
    if not access_token:
        return
    hc = await _client()
    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        r = await hc.delete(f"{CALENDAR_API}/calendars/{calendar_id}/events/{google_event_id}", headers=headers)
        if r.status_code not in (200, 204, 404, 410):
            logger.warning(f"google calendar event delete failed: {r.status_code} {r.text[:300]}")
    except Exception as e:
        logger.warning(f"google calendar delete_event error: {e}")


async def sync_series(user: dict, tmdb_id: int, series_name: str, show: dict):
    """Push (create/update) the 1-2 events (most recent aired + next upcoming
    episode) for one series into the user's connected Google Calendar. Mirrors
    the pair the .ics feed already exposes. Best-effort: swallows all errors so
    a Calendar hiccup never breaks adding a series to the library."""
    calendar_id = user.get("google_calendar_id")
    if not calendar_id or not user.get("google_calendar_refresh_token"):
        return
    from datetime import datetime, timedelta

    for ep, kind in [(show.get("next_episode_to_air"), "upcoming"), (show.get("last_episode_to_air"), "recent")]:
        if not ep or not ep.get("air_date"):
            continue
        try:
            d = datetime.strptime(ep["air_date"], "%Y-%m-%d").date()
        except Exception:
            continue
        key = {"user_id": str(user["_id"]), "tmdb_id": tmdb_id, "season": ep.get("season_number"), "episode": ep.get("episode_number")}
        existing = await db.calendar_events.find_one(key)
        summary = f"{series_name} — T{ep.get('season_number')}·E{ep.get('episode_number')}: {ep.get('name') or ''}".strip(": ")
        description = ep.get("overview") or ""
        url = f"https://www.themoviedb.org/tv/{tmdb_id}"
        google_event_id = await upsert_event(
            user, calendar_id,
            existing.get("google_event_id") if existing else None,
            summary, description,
            d.strftime("%Y-%m-%d"), (d + timedelta(days=1)).strftime("%Y-%m-%d"),
            url,
        )
        if google_event_id:
            await db.calendar_events.update_one(
                key, {"$set": {**key, "google_event_id": google_event_id, "kind": kind}}, upsert=True,
            )


async def remove_series(user: dict, tmdb_id: int):
    """Delete every event we created for this series, for this user, from
    their connected Google Calendar (best-effort)."""
    calendar_id = user.get("google_calendar_id")
    if not calendar_id or not user.get("google_calendar_refresh_token"):
        return
    docs = await db.calendar_events.find({"user_id": str(user["_id"]), "tmdb_id": tmdb_id}).to_list(20)
    for doc in docs:
        await delete_event(user, calendar_id, doc["google_event_id"])
    await db.calendar_events.delete_many({"user_id": str(user["_id"]), "tmdb_id": tmdb_id})
