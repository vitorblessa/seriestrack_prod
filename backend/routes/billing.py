"""Stripe billing via Emergent-managed claimable sandbox (Flow A).
Uses raw `stripe` SDK + Stripe Prices with lookup_keys — no client-supplied amounts.
Webhook path: /api/stripe/webhook (Flow A convention).
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends, Request

import stripe

from core import (
    db, logger, get_current_user, is_pro,
    PRO_PLANS, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET,
)
from core.models import CheckoutIn

# Configure the SDK once at import time. Sandbox keys are auto-injected on deploy;
# preview keys already live in backend/.env.
stripe.api_key = STRIPE_SECRET_KEY or "sk_test_emergent"

router = APIRouter()

# Tax handling — BR sandbox is NOT SMP-supported, so Stripe Tax (calc_only) is used.
# Change to "diy" to skip tax entirely, or "full" once the sandbox lands in an SMP country.
TAX_MODE = "calc_only"


@router.get("/billing/plans")
async def billing_plans():
    return {"plans": [
        {"id": k, "label": v["label"], "amount": v["amount"], "currency": v["currency"],
         "days": v["days"], "lookup_key": v["lookup_key"]}
        for k, v in PRO_PLANS.items()
    ]}


@router.post("/billing/checkout")
async def billing_checkout(payload: CheckoutIn, user: dict = Depends(get_current_user)):
    plan = PRO_PLANS.get(payload.plan)
    if not plan:
        raise HTTPException(400, "Plano inválido")

    # Resolve price by lookup_key so we never trust client amounts.
    prices = stripe.Price.list(lookup_keys=[plan["lookup_key"]], active=True, limit=1).data
    if not prices:
        logger.error(f"Stripe price missing for lookup_key={plan['lookup_key']}. Run setup_stripe.py.")
        raise HTTPException(500, "Preço não configurado — rode setup_stripe.py")
    price = prices[0]

    origin = payload.origin_url.rstrip("/")
    success_url = f"{origin}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/pricing"

    metadata = {
        "user_id": str(user["_id"]),
        "user_email": user["email"],
        "plan": payload.plan,
        "days": str(plan["days"]),
        "lookup_key": plan["lookup_key"],
    }

    kwargs = dict(
        line_items=[{"price": price.id, "quantity": 1}],
        mode="subscription" if price.recurring else "payment",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        # Attach the same metadata to the created subscription for downstream lookups.
        subscription_data={"metadata": metadata} if price.recurring else None,
    )
    # Strip None kwargs so Stripe doesn't reject them
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        if TAX_MODE == "full":
            try:
                session = stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
            except stripe.error.InvalidRequestError as e:
                msg = (getattr(e, "user_message", "") or "").lower()
                if "managed payments" in msg or "ineligible" in msg:
                    session = stripe.checkout.Session.create(
                        **kwargs, automatic_tax={"enabled": True}, billing_address_collection="required",
                    )
                else:
                    raise
        elif TAX_MODE == "calc_only":
            try:
                session = stripe.checkout.Session.create(
                    **kwargs, automatic_tax={"enabled": True}, billing_address_collection="required",
                )
            except stripe.error.InvalidRequestError as e:
                # Stripe Tax not enabled in the Dashboard yet — fall back to DIY so
                # the sandbox is usable end-to-end without extra clicks.
                msg = str(getattr(e, "user_message", "") or e).lower()
                if "tax" in msg:
                    logger.warning(f"Stripe Tax not enabled, falling back to DIY: {e}")
                    session = stripe.checkout.Session.create(**kwargs)
                else:
                    raise
        else:  # "diy"
            session = stripe.checkout.Session.create(**kwargs)
    except stripe.error.StripeError as e:
        logger.warning(f"stripe checkout error: {e}")
        raise HTTPException(502, f"Erro ao criar sessão de pagamento: {getattr(e, 'user_message', None) or str(e)}")

    await db.payment_transactions.insert_one({
        "session_id": session.id,
        "user_id": str(user["_id"]),
        "user_email": user["email"],
        "plan": payload.plan,
        "amount": plan["amount"],
        "currency": plan["currency"],
        "days": plan["days"],
        "metadata": metadata,
        "status": "initiated",
        "payment_status": "pending",
        "credited": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"url": session.url, "session_id": session.id}


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
async def billing_status(session_id: str, user: dict = Depends(get_current_user)):
    tx = await db.payment_transactions.find_one({"session_id": session_id, "user_id": str(user["_id"])}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Transação não encontrada")

    # Webhook-fallback: ask Stripe inline while still pending. Whichever path completes first wins.
    if tx.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as e:
            logger.warning(f"stripe status error: {e}")
            raise HTTPException(502, f"Erro ao consultar Stripe: {e}")

        new_status = s.status
        new_payment_status = s.payment_status
        update = {
            "status": new_status,
            "payment_status": new_payment_status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "amount_total": s.amount_total,
            "currency_received": s.currency,
        }
        if getattr(s, "subscription", None):
            update["stripe_subscription_id"] = s.subscription
        if getattr(s, "payment_intent", None):
            update["stripe_payment_intent_id"] = s.payment_intent

        credited = tx.get("credited", False)
        if not credited and (new_payment_status == "paid" or new_status == "complete"):
            days = int(tx.get("days") or 30)
            new_renews = await _credit_pro(tx["user_id"], days)
            update["credited"] = True
            update["credited_at"] = datetime.now(timezone.utc).isoformat()
            update["new_renews_at"] = new_renews

        # Idempotent guard — same as webhook.
        await db.payment_transactions.update_one(
            {"session_id": session_id, "payment_status": {"$ne": "paid"}},
            {"$set": update},
        )
        tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0}) or tx

    return {
        "status": tx.get("status"),
        "payment_status": tx.get("payment_status"),
        "amount_total": tx.get("amount_total"),
        "currency": tx.get("currency_received") or tx.get("currency"),
        "plan": tx.get("plan"),
        "credited": tx.get("credited", False),
        "new_renews_at": tx.get("new_renews_at"),
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
    """Self-service cancel — user keeps Pro until subscription_renews_at expires.
    Also cancels the Stripe subscription at period end so we don't double-charge.
    """
    if not await is_pro(user):
        raise HTTPException(400, "Você não tem uma assinatura Pro ativa")

    # Cancel the active Stripe subscription at period end (if we have one on file).
    tx = await db.payment_transactions.find_one(
        {"user_id": str(user["_id"]), "stripe_subscription_id": {"$exists": True, "$ne": None}},
        sort=[("created_at", -1)],
    )
    if tx and tx.get("stripe_subscription_id"):
        try:
            stripe.Subscription.modify(tx["stripe_subscription_id"], cancel_at_period_end=True)
        except stripe.error.StripeError as e:
            logger.warning(f"stripe subscription cancel failed: {e}")

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
    """Undo a pending cancel — resume auto-renew on the Stripe subscription too."""
    if not await is_pro(user):
        raise HTTPException(400, "Você não tem uma assinatura Pro ativa para reativar")

    tx = await db.payment_transactions.find_one(
        {"user_id": str(user["_id"]), "stripe_subscription_id": {"$exists": True, "$ne": None}},
        sort=[("created_at", -1)],
    )
    if tx and tx.get("stripe_subscription_id"):
        try:
            stripe.Subscription.modify(tx["stripe_subscription_id"], cancel_at_period_end=False)
        except stripe.error.StripeError as e:
            logger.warning(f"stripe subscription reactivate failed: {e}")

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"auto_renew": True}, "$unset": {"canceled_at": ""}},
    )
    return {"ok": True, "auto_renew": True}


# Flow A webhook path — Stripe is pre-registered to deliver here on deploy.
@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "invalid signature")
    except Exception as e:
        logger.warning(f"stripe webhook parse err: {e}")
        raise HTTPException(400, "invalid payload")

    obj = event["data"]["object"]
    t = event["type"]

    if t == "checkout.session.completed":
        session_id = obj["id"]
        tx = await db.payment_transactions.find_one({"session_id": session_id})
        if tx and not tx.get("credited"):
            days = int(tx.get("days") or 30)
            new_renews = await _credit_pro(tx["user_id"], days)
            update = {
                "status": "completed",
                "payment_status": obj.get("payment_status", "paid"),
                "credited": True,
                "credited_at": datetime.now(timezone.utc).isoformat(),
                "new_renews_at": new_renews,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            if obj.get("subscription"):
                update["stripe_subscription_id"] = obj.get("subscription")
            if obj.get("payment_intent"):
                update["stripe_payment_intent_id"] = obj.get("payment_intent")
            await db.payment_transactions.update_one(
                {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                {"$set": update},
            )
    elif t == "checkout.session.async_payment_succeeded":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"]},
            {"$set": {"payment_status": "paid", "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    elif t == "checkout.session.async_payment_failed":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"]},
            {"$set": {"status": "failed", "payment_status": "failed",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    elif t == "checkout.session.expired":
        await db.payment_transactions.update_one(
            {"session_id": obj["id"]},
            {"$set": {"status": "expired", "payment_status": "expired",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    elif t == "charge.refunded":
        await db.payment_transactions.update_one(
            {"stripe_payment_intent_id": obj.get("payment_intent")},
            {"$set": {"status": "refunded", "payment_status": "refunded",
                      "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    return {"received": True, "event_type": t}
