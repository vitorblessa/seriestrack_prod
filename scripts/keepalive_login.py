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

Env vars:
  BACKEND_URL        e.g. https://seriestrack-backend-zfla.onrender.com
  KEEPALIVE_EMAIL    test account email (auto-registered on first run
                      if it doesn't exist yet)
  KEEPALIVE_PASSWORD test account password
"""
import os
import sys
import time

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "").rstrip("/")
EMAIL = os.environ.get("KEEPALIVE_EMAIL", "")
PASSWORD = os.environ.get("KEEPALIVE_PASSWORD", "")
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


if __name__ == "__main__":
    main()
