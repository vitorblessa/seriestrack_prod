"""Auth: register / login / logout / me / Google OAuth."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Response, Depends
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from core import (
    db, logger, hash_password, verify_password, create_token,
    set_auth_cookies, clear_auth_cookies, serialize_user, get_current_user,
    ensure_owner_pro, GOOGLE_CLIENT_ID,
)
from core.models import RegisterIn, LoginIn, GoogleCallbackIn

router = APIRouter()


@router.post("/auth/register")
async def register(payload: RegisterIn, response: Response):
    email = payload.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already registered")
    doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip(),
        "avatar_url": None,
        "created_at": datetime.now(timezone.utc),
    }
    res = await db.users.insert_one(doc)
    user_id = str(res.inserted_id)
    # Auto-grant Pro if this email is in PRO_OWNERS env var
    await ensure_owner_pro(email)
    # Reload to get the updated tier in the response
    doc = await db.users.find_one({"_id": res.inserted_id}) or doc
    access = create_token(user_id, email, "access")
    refresh = create_token(user_id, email, "refresh")
    set_auth_cookies(response, access, refresh)
    return {"user": serialize_user(doc), "access_token": access}


@router.post("/auth/login")
async def login(payload: LoginIn, response: Response):
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


@router.post("/auth/logout")
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"ok": True}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return serialize_user(user)


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
