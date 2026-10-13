"""Account data export — LGPD Art. 18, IX (portabilidade de dados).

GET /account/export             -> JSON file with everything: profile,
                                    library, episode progress, reviews,
                                    notifications and payment history.
GET /account/export?format=csv  -> CSV of just the library (status +
                                    dates) — opens directly in Excel/Sheets,
                                    for people who just want a spreadsheet.

Account deletion (the other LGPD Art. 18 right) already exists as
DELETE /auth/me (routes/auth.py) — this is the read-only counterpart.
"""
import csv
import io
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from core import db, get_current_user, serialize_user

router = APIRouter()


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


@router.get("/account/export")
async def export_account_data(format: str = "json", user: dict = Depends(get_current_user)):
    user_id = str(user["_id"])
    today = datetime.now(timezone.utc).date().isoformat()

    if format == "csv":
        items = await db.library.find({"user_id": user_id}, {"_id": 0}).sort("updated_at", -1).to_list(2000)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["tmdb_id", "nome", "status", "adicionada_em", "atualizada_em"])
        for it in items:
            writer.writerow([
                it.get("tmdb_id"), it.get("name"), it.get("status"),
                _iso(it.get("added_at")), _iso(it.get("updated_at")),
            ])
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="seriestrack-biblioteca-{today}.csv"'},
        )

    library = await db.library.find({"user_id": user_id}, {"_id": 0}).sort("updated_at", -1).to_list(2000)
    progress = await db.progress.find({"user_id": user_id}, {"_id": 0}).to_list(20000)
    reviews = await db.reviews.find({"user_id": user_id}, {"_id": 0}).sort("updated_at", -1).to_list(2000)
    notifications = await db.notifications.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
    # Only the fields relevant to the user — no Stripe/internal ids, and
    # Stripe never hands us card numbers in the first place.
    payments = await db.payment_transactions.find(
        {"user_id": user_id},
        {"_id": 0, "plan": 1, "amount": 1, "currency": 1, "status": 1, "payment_status": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(500)

    data = {
        "exportado_em": datetime.now(timezone.utc).isoformat(),
        "perfil": serialize_user(user),
        "biblioteca": library,
        "progresso_episodios": progress,
        "resenhas": reviews,
        "notificacoes": notifications,
        "pagamentos": payments,
    }
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="seriestrack-dados-{today}.json"'},
    )
