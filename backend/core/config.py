"""Environment-driven configuration. All required vars must be set in /app/backend/.env."""
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# Optional integrations — import-guarded so missing libs don't crash startup
try:
    from pywebpush import webpush, WebPushException  # noqa: F401
    PUSH_AVAILABLE = True
except Exception:
    PUSH_AVAILABLE = False

try:
    # Emergentintegrations Stripe is kept as a soft flag for legacy paths /
    # tests that guard on STRIPE_AVAILABLE. Flow A (raw stripe SDK) is now the
    # canonical implementation — see routes/billing.py.
    from emergentintegrations.payments.stripe.checkout import (  # noqa: F401
        StripeCheckout, CheckoutSessionRequest,
    )
    STRIPE_AVAILABLE = True
except Exception:
    STRIPE_AVAILABLE = True  # raw `stripe` SDK is a hard requirement, always available

try:
    import google.genai  # noqa: F401
    _GENAI_SDK_AVAILABLE = True
except Exception:
    _GENAI_SDK_AVAILABLE = False
LLM_AVAILABLE = _GENAI_SDK_AVAILABLE and bool(os.environ.get('GEMINI_API_KEY'))

try:
    import sentry_sdk  # noqa: F401
    _SENTRY_SDK_AVAILABLE = True
except Exception:
    _SENTRY_SDK_AVAILABLE = False

try:
    import firebase_admin  # noqa: F401
    _FIREBASE_SDK_AVAILABLE = True
except Exception:
    _FIREBASE_SDK_AVAILABLE = False

# JWT
JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = "HS256"

# TMDB
TMDB_TOKEN = os.environ['TMDB_READ_TOKEN']
TMDB_REGION = os.environ.get('TMDB_REGION', 'US')
TMDB_LANG = os.environ.get('TMDB_LANG', 'en-US')
TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"

# Web Push (VAPID)
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_PEM_PATH = os.environ.get('VAPID_PRIVATE_PEM_PATH', '')
VAPID_SUBJECT = os.environ.get('VAPID_SUBJECT', 'mailto:admin@example.com')
# pywebpush wants the PATH to the PEM (not the file contents) — passing contents
# triggers ASN.1 parse errors on the EC curve. We expose the PATH and keep
# VAPID_PRIVATE_PEM as a flag (boolean-ish) for backward compatibility.
VAPID_PRIVATE_PEM = ''
if VAPID_PRIVATE_PEM_PATH and os.path.exists(VAPID_PRIVATE_PEM_PATH):
    # Just read once to validate readability; the real send_push uses the PATH.
    try:
        with open(VAPID_PRIVATE_PEM_PATH, 'r') as f:
            VAPID_PRIVATE_PEM = f.read()
    except Exception as e:
        logger = logging.getLogger("seriestrack")
        logger.warning(f"VAPID private key unreadable: {e}")

# Firebase Cloud Messaging — native Android push (web stays on VAPID/Web Push
# above; this is only for the installed Android app via @capacitor/push-notifications).
# The whole service account JSON goes in one env var (simplest for Render — no
# file to mount), not a path, unlike VAPID_PRIVATE_PEM_PATH above.
FIREBASE_SERVICE_ACCOUNT_JSON = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON', '')
FCM_AVAILABLE = _FIREBASE_SDK_AVAILABLE and bool(FIREBASE_SERVICE_ACCOUNT_JSON)

# Google OAuth via Emergent (legacy — kept only so the var doesn't error if still set;
# no longer used now that /auth/google verifies Google ID tokens directly, see routes/auth.py)
EMERGENT_OAUTH_SESSION_ENDPOINT = os.environ.get(
    'EMERGENT_OAUTH_SESSION_ENDPOINT',
    'https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data',
)

# Google OAuth Client ID (from Google Cloud Console). Required for "Continuar com
# Google" — the frontend uses it to get an ID token, and this backend verifies that
# token's audience matches it.
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')

# Google Calendar sync (separate consent from login — needs the offline/refresh-token
# authorization-code flow, so it needs the OAuth client's secret too). See
# core/google_calendar.py and routes/calendar_routes.py.
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_CALENDAR_REDIRECT_URI = os.environ.get('GOOGLE_CALENDAR_REDIRECT_URI', '')


# Stripe + Emergent LLM key
# Emergent-managed claimable sandbox (Flow A). STRIPE_SECRET_KEY is provisioned per-run;
# STRIPE_API_KEY kept for legacy BYOK fallback and to satisfy tests that mock it.
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY') or STRIPE_API_KEY
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
STRIPE_MODE = os.environ.get('STRIPE_MODE', 'test')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')  # legacy, no longer used (see GEMINI_API_KEY)
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.8-flash')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Transactional email (password reset). Uses Resend's HTTP API — see
# core/email.py. Soft-fails (logs, doesn't raise) if RESEND_API_KEY is unset,
# so local dev without it keeps working.
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'SeriesTrack <onboarding@resend.dev>')

# Base URL of the deployed frontend — used to build the link inside the
# password-reset email. No trailing slash.
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://www.series-track.com').rstrip('/')

# Error monitoring (Sentry). Soft — disabled unless both the SDK is installed
# and a DSN is set, so local dev / forks without a Sentry project keep working.
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
SENTRY_AVAILABLE = _SENTRY_SDK_AVAILABLE and bool(SENTRY_DSN)

# Shared secret that lets the external keepalive pinger opportunistically
# trigger the daily push sweep (POST /push/cron/ping) without a user login.
# Safety net for Render free-tier: if the process happened to be asleep or
# mid-restart at the scheduled 12:00 UTC APScheduler trigger, this catches it
# on the next ping instead of silently skipping that day's notifications.
CRON_SECRET = os.environ.get('CRON_SECRET', '')

# Free-tier limits
FREE_LIBRARY_CAP = 50

# Server-side fixed pricing (NEVER trust client-supplied amounts).
# `lookup_key` matches the Stripe Price lookup_key created by setup_stripe.py.
PRO_PLANS = {
    "pro_monthly": {"amount": 10.90, "currency": "brl", "days": 30, "label": "Pro Mensal", "lookup_key": "pro_monthly"},
    "pro_yearly": {"amount": 89.00, "currency": "brl", "days": 365, "label": "Pro Anual", "lookup_key": "pro_yearly"},
}

# Shared logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("seriestrack")
