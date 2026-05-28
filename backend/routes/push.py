"""Web Push (VAPID) — subscriptions, test ping, notify_today."""
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from core import (
    db, logger, get_current_user, tmdb_get_tv,
    VAPID_PUBLIC_KEY, VAPID_PRIVATE_PEM, VAPID_PRIVATE_PEM_PATH, VAPID_SUBJECT, PUSH_AVAILABLE,
)
from core.models import PushSubscriptionIn

try:
    from pywebpush import webpush, WebPushException
except Exception:
    webpush = None
    WebPushException = Exception

router = APIRouter()


@router.get("/push/public_key")
async def push_public_key():
    return {"public_key": VAPID_PUBLIC_KEY, "available": bool(VAPID_PUBLIC_KEY) and PUSH_AVAILABLE}


@router.post("/push/subscribe")
async def push_subscribe(payload: PushSubscriptionIn, user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    doc = {
        "user_id": user_id,
        "endpoint": payload.endpoint,
        "keys": payload.keys.model_dump(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.push_subscriptions.update_one(
        {"user_id": user_id, "endpoint": payload.endpoint},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True}


@router.delete("/push/subscribe")
async def push_unsubscribe(endpoint: str, user: dict = Depends(get_current_user)):
    await db.push_subscriptions.delete_one({"user_id": str(user["_id"]), "endpoint": endpoint})
    return {"ok": True}


def _send_push(sub: dict, title: str, body: str, url: Optional[str] = None, icon: Optional[str] = None):
    if not (PUSH_AVAILABLE and VAPID_PRIVATE_PEM_PATH):
        return False, "push not configured"
    try:
        # pywebpush expects the PATH to the PEM file (not the file contents),
        # otherwise we hit an ASN.1 parse error on the EC curve.
        webpush(
            subscription_info={
                "endpoint": sub["endpoint"],
                "keys": sub["keys"],
            },
            data=json.dumps({"title": title, "body": body, "url": url, "icon": icon}),
            vapid_private_key=VAPID_PRIVATE_PEM_PATH,
            vapid_claims={"sub": VAPID_SUBJECT},
            ttl=60 * 60 * 24,
        )
        return True, None
    except WebPushException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        msg = f"{status}: {getattr(e.response, 'text', '')[:200]}" if status else str(e)
        logger.warning(f"webpush failed for {sub.get('endpoint','')[:60]}: {msg}")
        return False, msg
    except Exception as e:
        logger.warning(f"webpush unexpected error: {type(e).__name__}: {e}")
        return False, str(e)


@router.post("/push/test")
async def push_test(user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)
    if not subs:
        raise HTTPException(400, "Sem inscrições ativas. Ative as notificações primeiro.")
    sent = 0
    failed = 0
    last_err: Optional[str] = None
    for s in subs:
        ok, err = _send_push(s, "SeriesTrack 🎬", "Notificações ativadas com sucesso!", url="/dashboard")
        if ok:
            sent += 1
        else:
            failed += 1
            last_err = err
            if err and ("410" in err or "404" in err):
                await db.push_subscriptions.delete_one({"_id": s["_id"]})
    if sent == 0 and failed > 0:
        # Surface the underlying error so the UI doesn't show a silent fail.
        raise HTTPException(502, f"Envio falhou: {last_err or 'erro desconhecido'}")
    return {"sent": sent, "failed": failed}


@router.post("/push/notify_today")
async def push_notify_today(user: dict = Depends(get_current_user)):
    """Manually trigger notifications for episodes airing today/tomorrow in the user's library."""
    user_id = str(user["_id"])
    items = await db.library.find({"user_id": user_id}).to_list(500)
    if not items:
        return {"created": 0, "pushed": 0}

    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    target_dates = {today.isoformat(), tomorrow.isoformat()}

    created = 0
    pushed = 0
    subs = await db.push_subscriptions.find({"user_id": user_id}).to_list(20)

    for it in items:
        try:
            s = await tmdb_get_tv(it["tmdb_id"])
            if not s:
                continue
            ep = s.get("next_episode_to_air")
            if not ep or ep.get("air_date") not in target_dates:
                continue

            title = f"Novo episódio: {s.get('name')}"
            body = f"T{ep.get('season_number')}·E{ep.get('episode_number')} — {ep.get('name')} estreia em {ep.get('air_date')}"

            existing_notif = await db.notifications.find_one({
                "user_id": user_id,
                "type": "episode_release",
                "tmdb_id": it["tmdb_id"],
                "season": ep.get("season_number"),
                "episode": ep.get("episode_number"),
            })
            if not existing_notif:
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
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                created += 1

            for sub in subs:
                ok, err = _send_push(sub, title, body, url=f"/series/{it['tmdb_id']}", icon=it.get("poster_url"))
                if ok:
                    pushed += 1
                elif err and ("410" in err or "404" in err):
                    await db.push_subscriptions.delete_one({"_id": sub["_id"]})
        except Exception as e:
            logger.warning(f"notify_today err {it.get('tmdb_id')}: {e}")
            continue

    return {"created": created, "pushed": pushed}


@router.post("/push/cron/run")
async def trigger_cron(user: dict = Depends(get_current_user)):
    """Admin-only — manually fire the daily cron job. Useful for testing.
    Restricted to users with is_owner=True (set via PRO_OWNERS env)."""
    if not user.get("is_owner"):
        raise HTTPException(403, "Apenas o dono pode disparar o cron manualmente")
    from core.cron import run_daily_push_pass
    return await run_daily_push_pass()
