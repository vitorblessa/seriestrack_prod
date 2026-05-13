"""User preferences (UI theme, etc) — Pro-gated for non-default themes."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from core import db, get_current_user, is_pro

router = APIRouter()


# Themes that any user can pick. All others require Pro.
FREE_THEMES = {"default"}
PRO_THEMES = {
    "oled",            # pure-black background, minimal accents
    "netflix",         # red on near-black
    "disney_plus",     # blue
    "hbo_max",         # purple
    "prime_video",     # cyan
    "apple_tv",        # white on pure black
    "paramount_plus",  # blue gradient
    "globoplay",       # red/orange Brazilian streamer
}
ALL_THEMES = FREE_THEMES | PRO_THEMES


class PreferencesIn(BaseModel):
    ui_theme: Optional[str] = Field(None, max_length=32)


def _default_prefs() -> dict:
    return {"ui_theme": "default"}


@router.get("/me/preferences")
async def get_preferences(user: dict = Depends(get_current_user)):
    prefs = {**_default_prefs(), **(user.get("preferences") or {})}
    pro = await is_pro(user)
    return {
        "preferences": prefs,
        "available_themes": sorted(FREE_THEMES) + sorted(PRO_THEMES),
        "free_themes": sorted(FREE_THEMES),
        "pro_themes": sorted(PRO_THEMES),
        "tier": "pro" if pro else "free",
    }


@router.patch("/me/preferences")
async def update_preferences(payload: PreferencesIn, user: dict = Depends(get_current_user)):
    update: dict = {}
    if payload.ui_theme is not None:
        if payload.ui_theme not in ALL_THEMES:
            raise HTTPException(400, f"Tema desconhecido: {payload.ui_theme}")
        if payload.ui_theme in PRO_THEMES and not await is_pro(user):
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "pro_theme_required",
                    "message": f"O tema '{payload.ui_theme}' é exclusivo Pro. Faça upgrade pra desbloquear.",
                },
            )
        update["preferences.ui_theme"] = payload.ui_theme

    if not update:
        return {"ok": True, "updated": False}

    await db.users.update_one({"_id": user["_id"]}, {"$set": update})
    new_prefs = {**_default_prefs(), **(user.get("preferences") or {}), **{k.split(".")[-1]: v for k, v in update.items()}}
    return {"ok": True, "updated": True, "preferences": new_prefs}
