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
    from emergentintegrations.payments.stripe.checkout import (  # noqa: F401
        StripeCheckout, CheckoutSessionRequest,
    )
    STRIPE_AVAILABLE = True
except Exception:
    STRIPE_AVAILABLE = False

try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage  # noqa: F401
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False

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
VAPID_PRIVATE_PEM = ''
if VAPID_PRIVATE_PEM_PATH and os.path.exists(VAPID_PRIVATE_PEM_PATH):
    with open(VAPID_PRIVATE_PEM_PATH, 'r') as f:
        VAPID_PRIVATE_PEM = f.read()

# Google OAuth via Emergent
EMERGENT_OAUTH_SESSION_ENDPOINT = os.environ.get(
    'EMERGENT_OAUTH_SESSION_ENDPOINT',
    'https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data',
)

# Stripe + Emergent LLM key
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Free-tier limits
FREE_LIBRARY_CAP = 50

# Server-side fixed pricing (NEVER trust client-supplied amounts)
PRO_PLANS = {
    "pro_monthly": {"amount": 12.90, "currency": "brl", "days": 30, "label": "Pro Mensal"},
    "pro_yearly": {"amount": 99.00, "currency": "brl", "days": 365, "label": "Pro Anual"},
}

# Shared logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("seriestrack")
