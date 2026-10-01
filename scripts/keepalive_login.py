#!/usr/bin/env python3
"""
Keep-alive ping for the SeriesTrack backend (Render free tier).

Render's free plan spins the service down after ~15 minutes with no
requests, and the next request then pays a ~30-50s cold-start penalty.
This script does a *real* login → authenticated request → logout cycle
against a dedicated test account every time it runs, which:
  - keeps the backend process warm (no cold start for real users), and
  - exercises the actual auth flow end-to-end (not just "is it up"),
    so a broken login would show up as a failed run in GitHub Actions.

It is meant to run on a schedule (see .github/workflows/keepalive.yml,
every 10 minutes) — this file has no scheduling logic of its own.

After the login cycle, it also pings POST /push/cron/ping (guarded by a
shared secret, CRON_SECRET) — a safety net for the daily episode-release
push notifications. Those are normally fired by an in-process scheduler at
12:00 UTC, which only works if the backend happens to be alive at that
exact moment; this ping lets the backend opportunistically catch up if it
was asleep or restarting right then. It's a no-op on every call except (at
most) once per day, so calling it every 10 minutes is cheap and safe.

Env vars:
  BACKEND_URL        e.g. https://seriestrack-backend-zfla.onrender.com
  KEEPALIVE_EMAIL    test account email (auto-registered on first run
                      if it doesn't exist yet)
  KEEPALIVE_PASSWORD test account password
  CRON_SECRET        shared secret for POST /push/cron/ping (optional —
                      if unset, that step is just skipped with a log line)
"""
import os
import sys
import time

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "").rstrip("/")
EMAIL = os.environ.get("KEEPALIVE_EMAIL", "")
PASSWORD = os.environ.get("KEEPALIVE_PASSWORD", "")
CRON_SECRET = os.environ.get("CRON_SECRET", "")
NAME = "Keepalive Bot"

# Render free-tier cold start can take ~30-50s if the service was asleep.
# Generous timeout + one retry covers that without failing the run.
TIMEOUT = 60
RETRY_WAIT = 15


def log(msg: str) -> None:
    print(f"[keepalive] {msg}", flush=True)


def request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """One retry after a short wait — covers the cold-start case where
    the very first request of the day wakes up a sleeping instance."""
    try:
        return requests.request(method, url, timeout=TIMEOUT, **kwargs)
    except requests.exceptions.RequestException as e:
        log(f"first attempt to {url} failed ({e}); retrying in {RETRY_WAIT}s "
            f"in case the service was cold-starting")
        time.sleep(RETRY_WAIT)
        return requests.request(method, url, timeout=TIMEOUT, **kwargs)


def register(session: requests.Session) -> None:
    log(f"account not found — registering {EMAIL}")
    r = request_with_retry(
        "POST", f"{BACKEND_URL}/api/auth/register",
        json={"email": EMAIL, "password": PASSWORD, "name": NAME},
    )
    if r.status_code >= 300:
        log(f"register failed: {r.status_code} {r.text[:300]}")
        sys.exit(1)
    log("account registered")


def main() -> None:
    if not BACKEND_URL or not EMAIL or not PASSWORD:
        log("missing BACKEND_URL / KEEPALIVE_EMAIL / KEEPALIVE_PASSWORD env vars")
        sys.exit(1)

    session = requests.Session()

    # 1. Login
    r = request_with_retry(
        "POST", f"{BACKEND_URL}/api/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
    )
    if r.status_code == 401:
        # First run ever: the test account doesn't exist yet. Create it
        # once, then log in normally.
        register(session)
        r = request_with_retry(
            "POST", f"{BACKEND_URL}/api/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )

    if r.status_code >= 300:
        log(f"login failed: {r.status_code} {r.text[:300]}")
        sys.exit(1)

    token = r.json().get("access_token")
    if not token:
        log("login response had no access_token")
        sys.exit(1)
    log("login ok")

    # 2. One authenticated request — proves the token + DB round trip work,
    # not just that the process is alive.
    r = request_with_retry(
        "GET", f"{BACKEND_URL}/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code >= 300:
        log(f"/auth/me failed: {r.status_code} {r.text[:300]}")
        sys.exit(1)
    log("authenticated request ok")

    # 3. Logout
    r = request_with_retry(
        "POST", f"{BACKEND_URL}/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code >= 300:
        log(f"logout failed: {r.status_code} {r.text[:300]}")
        sys.exit(1)
    log("logout ok — cycle complete")

    # 4. Opportunistic daily-push safety net (no-op most of the time — see
    # module docstring). Not fatal if it fails: the login cycle above already
    # did its job of keeping the backend warm.
    if CRON_SECRET:
        try:
            r = requests.post(
                f"{BACKEND_URL}/api/push/cron/ping",
                headers={"X-Cron-Secret": CRON_SECRET},
                timeout=TIMEOUT,
            )
            if r.status_code < 300:
                log(f"cron ping: {r.json()}")
            else:
                log(f"cron ping failed (non-fatal): {r.status_code} {r.text[:300]}")
        except requests.exceptions.RequestException as e:
            log(f"cron ping failed (non-fatal): {e}")
    else:
        log("CRON_SECRET not set — skipping daily-push safety net ping")


if __name__ == "__main__":
    main()
