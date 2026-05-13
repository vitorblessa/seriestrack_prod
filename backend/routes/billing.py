"""Stripe billing (Checkout sessions, status polling, webhooks)."""
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Request
from core import (
    db, logger, get_current_user, is_pro,
    PRO_PLANS, STRIPE_API_KEY, STRIPE_AVAILABLE,
)
from core.models import CheckoutIn

try:
    from emergentintegrations.payments.stripe.checkout import (
        StripeCheckout, CheckoutSessionRequest,
    )
except Exception:
    StripeCheckout = None  # type: ignore
    CheckoutSessionRequest = None  # type: ignore

router = APIRouter()


def _stripe_client(request: Request) -> "StripeCheckout":
    if not STRIPE_AVAILABLE:
        raise HTTPException(503, "Pagamentos indisponíveis no momento")
    if not STRIPE_API_KEY:
        raise HTTPException(503, "Stripe não configurado")
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    return StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)


@router.get("/billing/plans")
async def billing_plans():
    return {"plans": [
        {"id": k, "label": v["label"], "amount": v["amount"], "currency": v["currency"], "days": v["days"]}
        for k, v in PRO_PLANS.items()
    ]}


@router.post("/billing/checkout")
async def billing_checkout(payload: CheckoutIn, request: Request, user: dict = Depends(get_current_user)):
    plan = PRO_PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(400, "Plano inválido")
    sc = _stripe_client(request)
    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/pricing"
    metadata = {
        "user_id": str(user["_id"]),
        "user_email": user["email"],
        "plan": payload.plan,
        "days": str(plan["days"]),
    }
    req = CheckoutSessionRequest(
        amount=float(plan["amount"]),
        currency=plan["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )
    try:
        session = await sc.create_checkout_session(req)
    except Exception as e:
        logger.warning(f"stripe checkout error: {e}")
        raise HTTPException(502, f"Erro ao criar sessão de pagamento: {e}")

    await db.payment_transactions.insert_one({
        "session_id": session.session_id,
        "user_id": str(user["_id"]),
        "user_email": user["email"],
        "plan": payload.plan,
        "amount": plan["amount"],
        "currency": plan["currency"],
        "days": plan["days"],
        "metadata": metadata,
        "status": "initiated",
        "payment_status": "unpaid",
        "credited": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": session.url, "session_id": session.session_id}


async def _credit_pro(user_id: str, days: int) -> Optional[str]:
    """Idempotently extend the user's Pro subscription by `days`. Returns new renews_at iso."""
    try:
        u = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
    if not u:
        return None
    now = datetime.now(timezone.utc)
    cur = u.get("subscription_renews_at")
    cur_dt = None
    if cur:
        try:
            cur_dt = cur if isinstance(cur, datetime) else datetime.fromisoformat(cur)
            if cur_dt.tzinfo is None:
                cur_dt = cur_dt.replace(tzinfo=timezone.utc)
        except Exception:
            cur_dt = None
    base = cur_dt if (cur_dt and cur_dt > now) else now
    new_renews = base + timedelta(days=days)
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {
            "$set": {
                "subscription_tier": "pro",
                "subscription_renews_at": new_renews.isoformat(),
                "subscription_status": "active",
                "auto_renew": True,
            },
            "$unset": {"canceled_at": ""},
        },
    )
    return new_renews.isoformat()


@router.get("/billing/status/{session_id}")
async def billing_status(session_id: str, request: Request, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": str(user["_id"])}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Transação não encontrada")

    sc = _stripe_client(request)
    try:
        st = await sc.get_checkout_status(session_id)
    except Exception as e:
        logger.warning(f"stripe status error: {e}")
        raise HTTPException(502, f"Erro ao consultar Stripe: {e}")

    new_status = st.status
    new_payment_status = st.payment_status

    update = {
        "status": new_status,
        "payment_status": new_payment_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "amount_total": st.amount_total,
        "currency_received": st.currency,
    }

    credited = tx.get("credited", False)
    if not credited and new_payment_status == "paid":
        days = int(tx.get("days") or 30)
        new_renews = await _credit_pro(tx["user_id"], days)
        update["credited"] = True
        update["credited_at"] = datetime.now(timezone.utc).isoformat()
        update["new_renews_at"] = new_renews

    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": update})

    return {
        "status": new_status,
        "payment_status": new_payment_status,
        "amount_total": st.amount_total,
        "currency": st.currency,
        "plan": tx.get("plan"),
        "credited": update.get("credited", credited),
        "new_renews_at": update.get("new_renews_at"),
    }


@router.get("/billing/me")
async def billing_me(user: dict = Depends(get_current_user)):
    pro = await is_pro(user)
    renews = user.get("subscription_renews_at")
    if isinstance(renews, datetime):
        renews = renews.isoformat()
    days_left = None
    if pro and renews:
        try:
            ren_dt = datetime.fromisoformat(renews)
            if ren_dt.tzinfo is None:
                ren_dt = ren_dt.replace(tzinfo=timezone.utc)
            delta = ren_dt - datetime.now(timezone.utc)
            days_left = max(0, delta.days)
        except Exception:
            pass
    # auto_renew defaults to True so existing Pro users aren't surprised
    auto_renew = user.get("auto_renew", True) if pro else None
    cancel_pending = bool(pro and auto_renew is False)
    return {
        "tier": "pro" if pro else "free",
        "renews_at": renews,
        "days_left": days_left,
        "auto_renew": auto_renew,
        "cancel_pending": cancel_pending,
    }


@router.post("/billing/cancel")
async def cancel_subscription(user: dict = Depends(get_current_user)):
    """Self-service cancel — user keeps Pro until subscription_renews_at expires, then drops to Free.
    No refund (one-time payment model). Idempotent: calling twice keeps the same state.
    """
    if not await is_pro(user):
        raise HTTPException(400, "Você não tem uma assinatura Pro ativa")
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"auto_renew": False, "canceled_at": datetime.now(timezone.utc).isoformat()}},
    )
    renews = user.get("subscription_renews_at")
    if isinstance(renews, datetime):
        renews = renews.isoformat()
    return {"ok": True, "auto_renew": False, "renews_at": renews}


@router.post("/billing/reactivate")
async def reactivate_subscription(user: dict = Depends(get_current_user)):
    """Undo a pending cancel — user keeps Pro and will be reminded to renew."""
    if not await is_pro(user):
        raise HTTPException(400, "Você não tem uma assinatura Pro ativa para reativar")
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"auto_renew": True}, "$unset": {"canceled_at": ""}},
    )
    return {"ok": True, "auto_renew": True}


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    if not STRIPE_AVAILABLE:
        return {"received": False}
    body = await request.body()
    sig = request.headers.get("Stripe-Signature", "")
    sc = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=str(request.base_url).rstrip("/") + "/api/webhook/stripe")
    try:
        ev = await sc.handle_webhook(body, sig)
    except Exception as e:
        logger.warning(f"stripe webhook verify failed: {e}")
        raise HTTPException(400, "invalid signature")

    session_id = getattr(ev, "session_id", None)
    if session_id:
        tx = await db.payment_transactions.find_one({"session_id": session_id})
        if tx and ev.payment_status == "paid" and not tx.get("credited"):
            days = int(tx.get("days") or 30)
            new_renews = await _credit_pro(tx["user_id"], days)
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "credited": True,
                    "credited_at": datetime.now(timezone.utc).isoformat(),
                    "new_renews_at": new_renews,
                    "status": "complete",
                    "payment_status": ev.payment_status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
    return {"received": True, "event_type": getattr(ev, "event_type", None)}
