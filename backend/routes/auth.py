"""Auth: register / login / logout / me / Google OAuth / forgot & reset password."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from core import (
    db, logger, hash_password, verify_password, create_token,
    set_auth_cookies, clear_auth_cookies, serialize_user, get_current_user,
    ensure_owner_pro, GOOGLE_CLIENT_ID, FRONTEND_URL,
)
from core.email import send_email, password_reset_html, verify_email_html
from core.limiter import limiter
from core.models import RegisterIn, LoginIn, GoogleCallbackIn, ForgotPasswordIn, ResetPasswordIn, VerifyEmailIn

router = APIRouter()


async def _send_verification_email(user_id, email: str):
    """Issue a fresh 24h verification token for user_id and email it. Shared
    by /auth/register and /auth/resend_verification. Best-effort — logs and
    returns on failure, never raises (verification is non-blocking)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {
            "verify_token_hash": token_hash,
            "verify_token_expires": datetime.now(timezone.utc) + timedelta(hours=24),
        }},
    )
    verify_link = f"{FRONTEND_URL}/verify-email?token={raw_token}"
    sent = await send_email(email, "Confirme seu e-mail — SeriesTrack", verify_email_html(verify_link))
    if not sent:
        logger.warning(f"verification email send failed/skipped for {email}")


@router.post("/auth/register")
@limiter.limit("5/minute")
async def register(request: Request, payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "avatar_url": None,
        "email_verified": False,
        "created_at": datetime.now(timezone.utc),
    }
    res = await db.users.insert_one(doc)
    user_id = str(res.inserted_id)
    # Auto-grant Pro if this email is in PRO_OWNERS env var
    await ensure_owner_pro(email)
    # Reload to get the updated tier in the response
    doc = await db.users.find_one({"_id": res.inserted_id}) or doc
    # Non-blocking — registration succeeds even if the email never arrives;
    # the user can retry from the "confirm your email" banner.
    await _send_verification_email(res.inserted_id, email)
    access = create_token(user_id, email, "access")
    refresh = create_token(user_id, email, "refresh")
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(doc), "access_token": access}


@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginIn, response: Response):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    user_id = str(user["_id"])
    # Auto-grant Pro if owner email (idempotent)
    if await ensure_owner_pro(email):
        user = await db.users.find_one({"_id": user["_id"]}) or user
    access = create_token(user_id, email, "access")
    refresh = create_token(user_id, email, "refresh")
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(user), "access_token": access}


@router.post("/auth/forgot_password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, payload: ForgotPasswordIn):
    """Always returns ok:true regardless of whether the email is registered —
    never leak account existence. If a matching account with a password
    (i.e. not Google-only) exists, email a reset link valid for 1 hour."""
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if user and user.get("password_hash"):
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "reset_token_hash": token_hash,
                "reset_token_expires": datetime.now(timezone.utc) + timedelta(hours=1),
            }},
        )
        reset_link = f"{FRONTEND_URL}/reset-password?token={raw_token}"
        sent = await send_email(email, "Redefinir sua senha — SeriesTrack", password_reset_html(reset_link))
        if not sent:
            logger.warning(f"forgot_password: email send failed/skipped for {email}")
    else:
        logger.info(f"forgot_password: no password-based account for {email} (not found or Google-only)")
    return {"ok": True}


@router.post("/auth/reset_password")
@limiter.limit("5/minute")
async def reset_password(request: Request, payload: ResetPasswordIn):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    user = await db.users.find_one({"reset_token_hash": token_hash})
    if not user:
        raise HTTPException(400, "Link inválido ou já utilizado")

    expires = user.get("reset_token_expires")
    expired = True
    if expires:
        try:
            exp_dt = expires if isinstance(expires, datetime) else datetime.fromisoformat(expires)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            expired = exp_dt <= datetime.now(timezone.utc)
        except Exception:
            expired = True
    if expired:
        raise HTTPException(400, "Link expirado — solicite um novo")

    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"password_hash": hash_password(payload.password)},
            "$unset": {"reset_token_hash": "", "reset_token_expires": ""},
        },
    )
    logger.info(f"reset_password: password changed for user_id={user['_id']}")
    return {"ok": True}


@router.post("/auth/verify_email")
@limiter.limit("10/minute")
async def verify_email(request: Request, payload: VerifyEmailIn):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    user = await db.users.find_one({"verify_token_hash": token_hash})
    if not user:
        raise HTTPException(400, "Link inválido ou já utilizado")

    expires = user.get("verify_token_expires")
    expired = True
    if expires:
        try:
            exp_dt = expires if isinstance(expires, datetime) else datetime.fromisoformat(expires)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            expired = exp_dt <= datetime.now(timezone.utc)
        except Exception:
            expired = True
    if expired:
        raise HTTPException(400, "Link expirado — peça um novo na sua conta")

    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"email_verified": True},
            "$unset": {"verify_token_hash": "", "verify_token_expires": ""},
        },
    )
    logger.info(f"verify_email: confirmed for user_id={user['_id']}")
    return {"ok": True}


@router.post("/auth/resend_verification")
@limiter.limit("3/minute")
async def resend_verification(request: Request, user: dict = Depends(get_current_user)):
    if user.get("email_verified", True):
        return {"ok": True, "already_verified": True}
    await _send_verification_email(user["_id"], user["email"])
    return {"ok": True, "already_verified": False}


@router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return serialize_user(user)


@router.get("/auth/admin/search_users")
async def admin_search_users(q: str, user: dict = Depends(get_current_user)):
    """Owner-only — case-insensitive partial match on email, so typos in a
    user-supplied email can be tracked down to the real registered account.
    Returns at most 20 matches with just enough info to identify the right
    one (no password hashes, no sensitive fields)."""
    if not user.get("is_owner"):
        raise HTTPException(403, "Apenas o dono pode buscar usuários")

    import re
    safe = re.escape(q.strip())
    cursor = db.users.find(
        {"email": {"$regex": safe, "$options": "i"}},
        {"email": 1, "name": 1, "created_at": 1, "subscription_tier": 1,
         "subscription_renews_at": 1, "google_linked": 1},
    ).limit(20)
    results = await cursor.to_list(20)
    for r in results:
        r["_id"] = str(r["_id"])
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        if isinstance(r.get("subscription_renews_at"), datetime):
            r["subscription_renews_at"] = r["subscription_renews_at"].isoformat()
    return {"count": len(results), "users": results}


@router.delete("/auth/me")
async def delete_account(response: Response, user: dict = Depends(get_current_user)):
    """Google Play required: permanent account deletion.
    Removes user + ALL associated data. Payment transactions are retained
    for legal/tax purposes but disassociated from the user (user_id -> deleted-<id>).
    """
    from bson import ObjectId
    user_oid = user["_id"] if isinstance(user["_id"], ObjectId) else ObjectId(user["_id"])
    user_id_str = str(user_oid)

    # Cancel any active Stripe subscription first (best-effort).
    try:
        sub_id = user.get("stripe_subscription_id")
        if sub_id:
            import stripe
            from core import STRIPE_SECRET_KEY
            stripe.api_key = STRIPE_SECRET_KEY
            try:
                stripe.Subscription.delete(sub_id)
            except Exception as se:
                logger.warning(f"stripe cancel on delete failed for {sub_id}: {se}")
    except Exception:
        pass

    # Purge personal data.
    for coll_name, filt in [
        ("library", {"user_id": user_id_str}),
        ("progress", {"user_id": user_id_str}),
        ("reviews", {"user_id": user_id_str}),
        ("notifications", {"user_id": user_id_str}),
        ("push_subscriptions", {"user_id": user_id_str}),
        ("user_preferences", {"user_id": user_id_str}),
        ("import_jobs", {"user_id": user_id_str}),
        ("ai_recommendations_cache", {"user_id": user_id_str}),
    ]:
        try:
            await db[coll_name].delete_many(filt)
        except Exception as e:
            logger.warning(f"delete_account: {coll_name} purge failed: {e}")

    # Retain payment records but anonymise (Brazilian tax law requires 5-year retention).
    try:
        await db.payment_transactions.update_many(
            {"user_id": user_id_str},
            {"$set": {"user_id": f"deleted-{user_id_str}", "user_deleted_at": datetime.now(timezone.utc).isoformat()}},
        )
    except Exception as e:
        logger.warning(f"delete_account: payment anonymise failed: {e}")

    # Finally, delete the user record itself.
    await db.users.delete_one({"_id": user_oid})
    clear_auth_cookies(response)
    logger.info(f"account deleted user_id={user_id_str}")
    return {"deleted": True}


@router.post("/auth/google")
async def auth_google(payload: GoogleCallbackIn, response: Response):
    """Verify a Google ID token (from Google Identity Services on the frontend)
    and exchange it for our app's JWT."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Login com Google não configurado no servidor.")

    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), GOOGLE_CLIENT_ID,
        )
    except ValueError as e:
        logger.warning(f"google id_token verification failed: {e}")
        raise HTTPException(401, "Sessão Google inválida ou expirada. Tente novamente.")
    except Exception as e:
        logger.error(f"google id_token unexpected error: {type(e).__name__}: {e}")
        raise HTTPException(502, "Erro inesperado ao validar login com Google")

    if not idinfo.get("email_verified", False):
        raise HTTPException(401, "E-mail do Google não verificado.")

    email = (idinfo.get("email") or "").lower().strip()
    name = idinfo.get("name") or "Usuário"
    picture = idinfo.get("picture")
    if not email:
        raise HTTPException(401, "Google não retornou email — tente novamente")

    existing = await db.users.find_one({"email": email})
    now = datetime.now(timezone.utc)
    if existing:
        await db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"name": existing.get("name") or name, "avatar_url": picture or existing.get("avatar_url"), "google_linked": True}},
        )
        user_id = str(existing["_id"])
        existing.update({"name": existing.get("name") or name, "avatar_url": picture or existing.get("avatar_url")})
        user_doc = existing
    else:
        doc = {
            "email": email,
            "name": name,
            "avatar_url": picture,
            "google_linked": True,
            "email_verified": True,  # Google already verified this address (checked above)
            "created_at": now,
        }
        res = await db.users.insert_one(doc)
        user_id = str(res.inserted_id)
        doc["_id"] = res.inserted_id
        user_doc = doc

    access = create_token(user_id, email, "access")
    refresh = create_token(user_id, email, "refresh")
    set_auth_cookies(response, access, refresh)
    # Auto-grant Pro if owner email (idempotent, runs every Google login too)
    if await ensure_owner_pro(email):
        user_doc = await db.users.find_one({"_id": user_doc["_id"]}) or user_doc
    return {"user": serialize_user(user_doc), "access_token": access}
