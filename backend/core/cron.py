"""Daily push notification cron — runs in-process via APScheduler.
Fires once per day at 12:00 UTC (~ 9am BRT). For every user with at least one
push subscription, finds episodes airing TODAY and TOMORROW in their library
and sends push notifications. Idempotent — each notification is keyed by
(user_id, tmdb_id, season, episode) so re-runs don't spam users.

Also runs a separate daily Google Calendar re-sync (see run_daily_calendar_sync):
sync_series() only ever gets called when a user connects Calendar or adds a
series, so without this, a connected user's calendar goes stale the moment
TMDB's "next episode" rolls over to the following week's episode — nothing
was pushing that new event to Google. This sweep re-syncs every
Calendar-connected user's whole library once a day so it never drifts.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core import db, logger, tmdb_get_tv
from core import google_calendar as gcal
from routes.push import _send_push, _is_stale_token_error

_scheduler: Optional[AsyncIOScheduler] = None

# Tracks the UTC calendar date the daily sweep last actually ran, in a tiny
# single-document collection — lets an opportunistic caller (the keepalive
# ping, see run_daily_push_pass_if_due) safely run "at most once per day"
# without needing its own cron infrastructure.
_CRON_STATE_ID = "daily_push"
_CALENDAR_CRON_STATE_ID = "daily_calendar_sync"


async def run_daily_push_pass() -> dict:
    """Iterate all users with push subs, send notifications for today/tomorrow's episodes."""
    started = datetime.now(timezone.utc)
    today = started.date()
    tomorrow = today + timedelta(days=1)
    target_dates = {today.isoformat(), tomorrow.isoformat()}

    # Distinct user_ids that have at least one push sub
    user_ids = await db.push_subscriptions.distinct("user_id")
    if not user_ids:
        logger.info("[cron] daily_push: no users with push subscriptions")
        return {"users": 0, "created": 0, "pushed": 0}

    total_created = 0
    total_pushed = 0

    for user_id in user_ids:
        try:
            subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)
            if not subs:
                continue
            items = await db.library.find(
                {"user_id": user_id, "status": {"$in": ["watching", "want"]}}
            ).to_list(500)
            if not items:
                continue

            for it in items:
                s = await tmdb_get_tv(it["tmdb_id"])
                if not s:
                    continue
                ep = s.get("next_episode_to_air")
                if not ep or ep.get("air_date") not in target_dates:
                    continue

                # Idempotency check — don't double-send for the same episode
                already = await db.notifications.find_one({
                    "user_id": user_id,
                    "type": "episode_release",
                    "tmdb_id": it["tmdb_id"],
                    "season": ep.get("season_number"),
                    "episode": ep.get("episode_number"),
                })
                if already:
                    continue

                title = f"Novo episódio: {s.get('name')}"
                body = (
                    f"T{ep.get('season_number')}·E{ep.get('episode_number')} — "
                    f"{ep.get('name')} estreia em {ep.get('air_date')}"
                )

                await db.notifications.insert_one({
                    "user_id": user_id,
                    "type": "episode_release",
                    "title": title,
                    "message": body,
                    "tmdb_id": it["tmdb_id"],
                    "poster_url": it.get("poster_url"),
                    "season": ep.get("season_number"),
                    "episode": ep.get("episode_number"),
                    "read": False,
                    "source": "cron_daily",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                total_created += 1

                for sub in subs:
                    ok, err = _send_push(sub, title, body, url=f"/series/{it['tmdb_id']}", icon=it.get("poster_url"))
                    if ok:
                        total_pushed += 1
                    elif _is_stale_token_error(err):
                        await db.push_subscriptions.delete_one({"_id": sub["_id"]})
        except Exception as e:
            logger.warning(f"[cron] daily_push user={user_id} failed: {e}")
            continue

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info(f"[cron] daily_push done: users={len(user_ids)} created={total_created} pushed={total_pushed} elapsed={elapsed:.1f}s")
    return {"users": len(user_ids), "created": total_created, "pushed": total_pushed, "elapsed_s": elapsed}


async def run_daily_push_pass_if_due() -> dict:
    """Opportunistic version of run_daily_push_pass(), safe to call as often
    as every few minutes (e.g. from an external keepalive pinger): it only
    actually runs the sweep once per UTC calendar day.

    Why this exists: the APScheduler job below only fires if the process
    happens to be alive at exactly 12:00 UTC. On Render's free tier that
    used to be unreliable (the service sleeps after ~15 min idle, so a cold
    instance simply never hits that trigger). This is the safety net —
    anything that pings the backend regularly can call this and the daily
    push will go out even if the exact-time trigger was missed that day.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    state = await db.cron_state.find_one({"_id": _CRON_STATE_ID})
    if state and state.get("last_run_date") == today:
        return {"skipped": True, "reason": "already ran today", "date": today}

    result = await run_daily_push_pass()
    await db.cron_state.update_one(
        {"_id": _CRON_STATE_ID},
        {"$set": {"last_run_date": today, "last_run_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"skipped": False, "date": today, **result}


async def run_daily_calendar_sync() -> dict:
    """Re-sync every Calendar-connected user's whole library into their Google
    Calendar. sync_series() (core/google_calendar.py) only ever runs when a
    user connects Calendar, adds a series, or hits the manual "sync" button —
    nothing re-pushes a series once its TMDB next_episode_to_air rolls over to
    the following episode, so without this the Calendar silently goes stale."""
    started = datetime.now(timezone.utc)
    users = await db.users.find(
        {"google_calendar_refresh_token": {"$exists": True, "$ne": None}}
    ).to_list(1000)
    if not users:
        logger.info("[cron] daily_calendar_sync: no users with Google Calendar connected")
        return {"users": 0, "series_synced": 0}

    total_series = 0
    for user in users:
        try:
            # One token refresh per USER (not per series) — same reasoning as
            # _sync_all_series in routes/calendar_routes.py.
            access_token = await gcal.get_access_token_for_user(user)
            if not access_token:
                logger.warning(f"[cron] daily_calendar_sync: no valid token for user={user.get('_id')}, skipping")
                continue
            items = await db.library.find(
                {"user_id": str(user["_id"]), "status": {"$in": ["watching", "want"]}}
            ).to_list(500)
            for it in items:
                try:
                    show = await tmdb_get_tv(it["tmdb_id"])
                    if not show:
                        continue
                    await gcal.sync_series(user, it["tmdb_id"], it.get("name") or show.get("name") or "Série", show, access_token=access_token)
                    total_series += 1
                except Exception as e:
                    logger.warning(f"[cron] daily_calendar_sync series={it.get('tmdb_id')} user={user.get('_id')} failed: {e}")
                    continue
        except Exception as e:
            logger.warning(f"[cron] daily_calendar_sync user={user.get('_id')} failed: {e}")
            continue

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info(f"[cron] daily_calendar_sync done: users={len(users)} series_synced={total_series} elapsed={elapsed:.1f}s")
    return {"users": len(users), "series_synced": total_series, "elapsed_s": elapsed}


async def run_daily_calendar_sync_if_due() -> dict:
    """Opportunistic version of run_daily_calendar_sync() — same "at most once
    per UTC day" pattern as run_daily_push_pass_if_due(), with its own
    cron_state document so the two sweeps track independently."""
    today = datetime.now(timezone.utc).date().isoformat()
    state = await db.cron_state.find_one({"_id": _CALENDAR_CRON_STATE_ID})
    if state and state.get("last_run_date") == today:
        return {"skipped": True, "reason": "already ran today", "date": today}

    result = await run_daily_calendar_sync()
    await db.cron_state.update_one(
        {"_id": _CALENDAR_CRON_STATE_ID},
        {"$set": {"last_run_date": today, "last_run_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"skipped": False, "date": today, **result}


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    # 12:00 UTC daily = 9:00 BRT — sweet spot for "today's episodes" notifications.
    # Goes through the _if_due wrapper so this and the keepalive's opportunistic
    # ping (routes/push.py: POST /push/cron/ping) share the same "ran today"
    # bookkeeping and never double-send.
    _scheduler.add_job(
        run_daily_push_pass_if_due,
        trigger=CronTrigger(hour=12, minute=0),
        id="daily_push",
        replace_existing=True,
        max_instances=1,  # don't overlap if previous run is still going
        coalesce=True,    # if we missed a run (e.g. server down), only fire once
    )
    # 12:30 UTC — staggered 30min after daily_push so the two sweeps don't
    # compete for TMDB/API time on a cold Render instance.
    _scheduler.add_job(
        run_daily_calendar_sync_if_due,
        trigger=CronTrigger(hour=12, minute=30),
        id="daily_calendar_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("[cron] scheduler started — daily_push at 12:00 UTC, daily_calendar_sync at 12:30 UTC")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[cron] scheduler stopped")
