"""Transactional email via Resend's HTTP API (https://resend.com).

Soft-fails — logs and returns False instead of raising — if RESEND_API_KEY
isn't set, so local dev and any environment without it keeps working.
/auth/forgot_password already treats delivery as fire-and-forget (it never
reveals whether the send succeeded, to avoid leaking account existence).
"""
import httpx

from .config import RESEND_API_KEY, EMAIL_FROM, logger

RESEND_API = "https://api.resend.com/emails"


async def send_email(to: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        logger.warning(f"[email] RESEND_API_KEY not set — skipping send to {to} ({subject!r})")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                RESEND_API,
                headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
                json={"from": EMAIL_FROM, "to": [to], "subject": subject, "html": html},
            )
        if r.status_code >= 300:
            logger.error(f"[email] Resend send to {to} failed ({r.status_code}): {r.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"[email] Resend send to {to} raised: {e}")
        return False


def password_reset_html(reset_link: str) -> str:
    return f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;margin:0 auto;padding:32px 24px;background:#0A0A0C;color:#ffffff;border-radius:16px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:24px">
        <div style="width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#FF2A54,#7c1531);display:flex;align-items:center;justify-content:center;font-size:18px">📺</div>
        <span style="font-weight:900;font-size:20px">SeriesTrack</span>
      </div>
      <h1 style="font-size:22px;margin:0 0 12px">Redefinir sua senha</h1>
      <p style="color:rgba(255,255,255,.6);line-height:1.6">
        Recebemos um pedido para redefinir a senha da sua conta. Clique no botão abaixo
        para escolher uma nova senha. Este link expira em 1 hora.
      </p>
      <a href="{reset_link}" style="display:inline-block;margin-top:20px;padding:14px 28px;border-radius:999px;background:linear-gradient(135deg,#FF2A54,#7c1531);color:#ffffff;text-decoration:none;font-weight:700">
        Redefinir senha
      </a>
      <p style="color:rgba(255,255,255,.35);font-size:12px;margin-top:28px;line-height:1.6">
        Se você não pediu essa redefinição, pode ignorar este e-mail com segurança —
        sua senha continua a mesma.<br/>
        Se o botão não funcionar, copie e cole este link no navegador:<br/>
        <span style="word-break:break-all">{reset_link}</span>
      </p>
    </div>
    """
