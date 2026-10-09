"""Backend tests for NutriVane Mood AI recommendation feature."""
import os
import subprocess
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
BACKEND_DIR = Path("/app/backend")
PY = "/root/.venv/bin/python"


def _mint_token(uid=None, name=None):
    args = [PY, "scripts/dev_token.py"]
    if uid:
        args.append(uid)
    if name:
        args.append(name)
    return subprocess.check_output(args, cwd=BACKEND_DIR).decode().strip()


@pytest.fixture(scope="session")
def token_asha():
    return _mint_token()


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def auth_hdr(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _mood_log_count():
    try:
        out = subprocess.check_output(
            ["psql", "-h", "localhost", "-U", "postgres", "-d", "nutrivane",
             "-tAc", "select count(*) from mood_logs"],
            env={**os.environ, "PGPASSWORD": "nutrivane"},
        ).decode().strip()
        return int(out)
    except Exception as e:
        pytest.skip(f"psql not available: {e}")


# --- Structure validation ---
def _assert_recommend_shape(d):
    assert set(["headline", "summary", "items", "tip", "mood",
                "source", "current_country", "origin_country", "saved_to_account"]).issubset(d.keys())
    assert isinstance(d["headline"], str) and d["headline"]
    assert isinstance(d["summary"], str)
    assert isinstance(d["tip"], str)
    assert d["source"] in ("ai", "fallback")
    assert isinstance(d["mood"], dict)
    assert set(d["mood"].keys()) == {"key", "label", "emoji"}
    items = d["items"]
    assert isinstance(items, list) and 1 <= len(items) <= 5
    for it in items:
        assert isinstance(it["name"], str) and it["name"]
        assert it["kind"] in ("makanan", "minuman")
        assert isinstance(it["why"], str)
        assert it["slug"] is None or isinstance(it["slug"], str)
        assert it["origin_tag"] in ("lokal", "asal", "umum")
        assert "recipe" in it
        if it["slug"]:
            assert isinstance(it["recipe"], dict)
            for k in ("slug", "name", "image"):
                assert k in it["recipe"], f"recipe missing {k}"
            assert it["recipe"]["slug"] == it["slug"]
        else:
            assert it["recipe"] is None


def test_recommend_guest_basic(client):
    before = _mood_log_count()
    r = client.post(f"{API}/mood/recommend", json={
        "mood_key": "berenergi", "story": "", "current_country": "", "origin_country": ""
    }, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    _assert_recommend_shape(d)
    assert d["saved_to_account"] is False
    assert d["mood"]["key"] == "berenergi"
    assert d["current_country"] == "" and d["origin_country"] == ""
    assert _mood_log_count() == before + 1


def test_recommend_auth_persists_countries(client, token_asha):
    h = auth_hdr(token_asha)
    # reset first
    client.put(f"{API}/me/countries", json={"current_country": "", "origin_country": ""},
               headers=h, timeout=20)
    before = _mood_log_count()
    r = client.post(f"{API}/mood/recommend", json={
        "mood_key": "berenergi", "story": "Hari ini melelahkan tapi aku ingin tetap semangat.",
        "current_country": "Jepang", "origin_country": "Indonesia"
    }, headers=h, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    _assert_recommend_shape(d)
    assert d["saved_to_account"] is True
    assert d["current_country"] == "Jepang"
    assert d["origin_country"] == "Indonesia"
    assert _mood_log_count() == before + 1

    me = client.get(f"{API}/me", headers=h, timeout=20).json()
    assert me["user"]["current_country"] == "Jepang"
    assert me["user"]["origin_country"] == "Indonesia"


def test_recommend_unknown_mood(client):
    r = client.post(f"{API}/mood/recommend",
                    json={"mood_key": "tidak-ada-mood-xyz"}, timeout=20)
    assert r.status_code == 404


def test_recommend_missing_mood_key(client):
    r = client.post(f"{API}/mood/recommend", json={"story": "hello"}, timeout=20)
    assert r.status_code == 422


def test_recommend_story_too_long(client):
    r = client.post(f"{API}/mood/recommend",
                    json={"mood_key": "berenergi", "story": "x" * 1201}, timeout=20)
    assert r.status_code == 422


# --- /api/me/countries ---
def test_put_countries_requires_auth(client):
    r = client.put(f"{API}/me/countries",
                   json={"current_country": "Belanda", "origin_country": "Indonesia"}, timeout=20)
    assert r.status_code == 401


def test_put_countries_auth(client, token_asha):
    h = auth_hdr(token_asha)
    r = client.put(f"{API}/me/countries",
                   json={"current_country": "Belanda", "origin_country": "Indonesia"},
                   headers=h, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d["current_country"] == "Belanda"
    assert d["origin_country"] == "Indonesia"
    me = client.get(f"{API}/me", headers=h, timeout=20).json()
    assert me["user"]["current_country"] == "Belanda"
    assert me["user"]["origin_country"] == "Indonesia"


# --- Regression ---
@pytest.mark.parametrize("path", ["/health", "/moods", "/moods/berenergi", "/recipes", "/home"])
def test_regression_endpoints(client, path):
    r = client.get(f"{API}{path}", timeout=30)
    assert r.status_code == 200
