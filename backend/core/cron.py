"""Daily push notification cron — runs in-process via APScheduler.
Fires once per day at 12:00 UTC (~ 9am BRT). For every user with at least one
push subscription, finds episodes airing TODAY and TOMORROW in their library
and sends push notifications. Idempotent — each notification is keyed by
(user_id, tmdb_id, season, episode) so re-runs don't spam users.
"""
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core import db, logger, tmdb_get_tv
from routes.push import _send_push

_scheduler: Optional[AsyncIOScheduler] = None


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
                    elif err and ("410" in err or "404" in err):
                        await db.push_subscriptions.delete_one({"_id": sub["_id"]})
        except Exception as e:
            logger.warning(f"[cron] daily_push user={user_id} failed: {e}")
            continue

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    logger.info(f"[cron] daily_push done: users={len(user_ids)} created={total_created} pushed={total_pushed} elapsed={elapsed:.1f}s")
    return {"users": len(user_ids), "created": total_created, "pushed": total_pushed, "elapsed_s": elapsed}


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    # 12:00 UTC daily = 9:00 BRT — sweet spot for "today's episodes" notifications
    _scheduler.add_job(
        run_daily_push_pass,
        trigger=CronTrigger(hour=12, minute=0),
        id="daily_push",
        replace_existing=True,
        max_instances=1,  # don't overlap if previous run is still going
        coalesce=True,    # if we missed a run (e.g. server down), only fire once
    )
    _scheduler.start()
    logger.info("[cron] scheduler started — daily_push at 12:00 UTC")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[cron] scheduler stopped")
