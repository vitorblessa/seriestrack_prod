"""LGPD Art. 18, IX (portabilidade): GET /api/account/export must return
every collection scoped to the user, and ?format=csv must return just the
library as a spreadsheet-ready CSV. Complements test_delete_account.py."""
import os
import uuid
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://show-notify.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "seriestrack")


def _register_and_seed():
    mongo = MongoClient(MONGO_URL)[DB_NAME]
    email = f"TEST_export_{uuid.uuid4().hex[:10]}@seriestrack-test.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@1234", "name": "Export Me"}, timeout=15)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    user_id = r.json()["user"]["id"]

    mongo.library.insert_one({
        "user_id": user_id, "tmdb_id": 999998, "name": "Fake Show", "status": "watching",
        "added_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-02T00:00:00+00:00",
    })
    mongo.progress.insert_one({"user_id": user_id, "tmdb_id": 999998, "season": 1, "episode": 1})
    mongo.reviews.insert_one({"user_id": user_id, "tmdb_id": 999998, "rating": 5, "comment": "export me"})
    mongo.notifications.insert_one({"user_id": user_id, "title": "x", "body": "y", "created_at": "2026-01-01T00:00:00+00:00"})

    return {"token": token, "user_id": user_id, "email": email}


def test_export_json_includes_everything():
    victim = _register_and_seed()
    headers = {"Authorization": f"Bearer {victim['token']}"}
    r = requests.get(f"{API}/account/export", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers.get("content-disposition", "")
    data = r.json()
    assert data["perfil"]["email"] == victim["email"]
    assert any(it["tmdb_id"] == 999998 for it in data["biblioteca"])
    assert any(p["tmdb_id"] == 999998 for p in data["progresso_episodios"])
    assert any(rv["tmdb_id"] == 999998 for rv in data["resenhas"])
    assert len(data["notificacoes"]) >= 1
    # No other user's data leaked in.
    assert all(it.get("user_id") in (None, victim["user_id"]) for it in data["biblioteca"])


def test_export_csv_is_library_only():
    victim = _register_and_seed()
    headers = {"Authorization": f"Bearer {victim['token']}"}
    r = requests.get(f"{API}/account/export?format=csv", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("text/csv")
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.text
    assert "tmdb_id" in body.splitlines()[0]
    assert "999998" in body
    assert "Fake Show" in body


def test_export_requires_auth():
    r = requests.get(f"{API}/account/export", timeout=10)
    assert r.status_code == 401
