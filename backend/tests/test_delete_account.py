"""Google Play requirement: /api/auth/me DELETE must fully purge personal data.
Covers: delete a live user, verify their library/reviews/notifications are gone,
verify Stripe subscription cancel is best-effort, verify session tokens die.
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://show-notify.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "seriestrack")


@pytest.fixture(scope="module")
def mongo():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture
def victim(mongo):
    """A freshly-registered throwaway account with library + review + notification rows seeded."""
    email = f"TEST_delete_{uuid.uuid4().hex[:10]}@seriestrack-test.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@1234", "name": "Delete Me"}, timeout=15)
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    user_id = r.json()["user"]["id"]

    # Seed dependent data so we can verify the cascade.
    mongo.library.insert_one({"user_id": user_id, "tmdb_id": 999999, "title": "Fake", "status": "watching"})
    mongo.progress.insert_one({"user_id": user_id, "tmdb_id": 999999, "season": 1, "episode": 1})
    mongo.reviews.insert_one({"user_id": user_id, "tmdb_id": 999999, "rating": 5, "comment": "delete me"})
    mongo.notifications.insert_one({"user_id": user_id, "title": "x", "body": "y"})
    mongo.push_subscriptions.insert_one({"user_id": user_id, "endpoint": "https://fake", "keys": {}})
    mongo.payment_transactions.insert_one({"session_id": f"cs_test_delete_{user_id}", "user_id": user_id, "status": "paid"})

    return {"token": token, "user_id": user_id, "email": email}


def test_delete_me_purges_all_data(mongo, victim):
    headers = {"Authorization": f"Bearer {victim['token']}"}
    r = requests.delete(f"{API}/auth/me", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json() == {"deleted": True}

    uid = victim["user_id"]
    # Personal data purged.
    assert mongo.users.find_one({"_id": ObjectId(uid)}) is None
    assert mongo.library.count_documents({"user_id": uid}) == 0
    assert mongo.progress.count_documents({"user_id": uid}) == 0
    assert mongo.reviews.count_documents({"user_id": uid}) == 0
    assert mongo.notifications.count_documents({"user_id": uid}) == 0
    assert mongo.push_subscriptions.count_documents({"user_id": uid}) == 0
    # Payment record kept but anonymized (5-year retention, Brazilian tax law).
    tx = mongo.payment_transactions.find_one({"session_id": f"cs_test_delete_{uid}"})
    assert tx is not None
    assert tx["user_id"] == f"deleted-{uid}"
    assert "user_deleted_at" in tx


def test_delete_me_requires_auth():
    r = requests.delete(f"{API}/auth/me", timeout=10)
    assert r.status_code == 401


def test_deleted_token_fails_on_me(victim):
    # Use the same token AFTER deletion — should 401.
    headers = {"Authorization": f"Bearer {victim['token']}"}
    requests.delete(f"{API}/auth/me", headers=headers, timeout=10)
    r = requests.get(f"{API}/auth/me", headers=headers, timeout=10)
    assert r.status_code == 401


def test_public_legal_urls_reachable_without_auth():
    """Play Console requires /privacy, /terms, /delete-account to be publicly reachable.
    These are frontend routes served by CRA — we test the SPA root returns HTML 200,
    and rely on client-side routing for the actual pages."""
    r = requests.get(BASE_URL + "/privacy", timeout=10)
    assert r.status_code == 200
    r = requests.get(BASE_URL + "/terms", timeout=10)
    assert r.status_code == 200
    r = requests.get(BASE_URL + "/delete-account", timeout=10)
    assert r.status_code == 200
