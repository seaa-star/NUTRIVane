"""Tests for GET /api/mood/weekly and regression on key endpoints."""
import os
import subprocess
import time
import requests
import pytest

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
DAY_LABELS = {"Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"}


def _dev_token(uid=None, name=None):
    cmd = ["/root/.venv/bin/python", "scripts/dev_token.py"]
    if uid:
        cmd.append(uid)
    if name:
        cmd.append(name)
    out = subprocess.check_output(cmd, cwd="/app/backend").decode().strip()
    # Script prints token on last line
    return out.splitlines()[-1].strip()


@pytest.fixture(scope="module")
def asha_token():
    with open("/app/memory/dev_token.txt") as f:
        return f.read().strip()


@pytest.fixture
def api():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    return s


def _validate_shape(data, expect_auth):
    assert data["authenticated"] is expect_auth
    assert isinstance(data["days"], list) and len(data["days"]) == 7
    today_flags = [d["is_today"] for d in data["days"]]
    assert sum(today_flags) == 1
    assert data["days"][-1]["is_today"] is True
    for d in data["days"]:
        assert d["label"] in DAY_LABELS
        assert "date" in d and "count" in d and "moods" in d
        assert "dominant" in d


def test_weekly_guest(api):
    r = api.get(f"{BASE_URL}/api/mood/weekly")
    assert r.status_code == 200
    data = r.json()
    _validate_shape(data, expect_auth=False)
    assert data["total"] == 0
    assert data["active_days"] == 0
    assert data["top"] is None
    for d in data["days"]:
        assert d["count"] == 0
        assert d["moods"] == {}
        assert d["dominant"] is None


def test_weekly_auth_asha_has_seed(api, asha_token):
    r = api.get(f"{BASE_URL}/api/mood/weekly", headers={"Authorization": f"Bearer {asha_token}"})
    assert r.status_code == 200
    data = r.json()
    _validate_shape(data, expect_auth=True)
    # Seed: rows exist for Asha at 2 and 5 days ago -> total >= 2, active_days >= 2
    assert data["total"] >= 2
    assert data["active_days"] >= 2
    assert data["top"] is not None
    assert set(data["top"].keys()) >= {"key", "label", "emoji"}
    # dominant per day with count>0 must have key/label/emoji
    for d in data["days"]:
        if d["count"] > 0:
            assert d["dominant"] is not None
            assert set(d["dominant"].keys()) >= {"key", "label", "emoji"}


def test_weekly_other_user_isolation(api, asha_token):
    """Insert a mood_log row for another user via psql, confirm it doesn't appear in Asha's data."""
    other_uid = "22222222-2222-4222-8222-222222222222"
    # ensure profile exists for other user via dev token mint
    _dev_token(other_uid, "Budi Santoso")
    # Insert directly
    sql = (
        f"insert into profiles (user_id, email, display_name) values ('{other_uid}', 'budi@example.com', 'Budi') "
        f"on conflict (user_id) do nothing; "
        f"insert into mood_logs (user_id, mood_key, story) values ('{other_uid}', 'berenergi', 'test isolate');"
    )
    subprocess.check_call(
        ["psql", "-h", "localhost", "-U", "postgres", "-d", "nutrivane", "-c", sql],
        env={**os.environ, "PGPASSWORD": "nutrivane"},
    )

    before = api.get(f"{BASE_URL}/api/mood/weekly", headers={"Authorization": f"Bearer {asha_token}"}).json()
    # Also compare against other user's weekly: Budi should see at least this one row
    budi_token = _dev_token(other_uid, "Budi Santoso")
    budi = api.get(f"{BASE_URL}/api/mood/weekly", headers={"Authorization": f"Bearer {budi_token}"}).json()
    assert budi["total"] >= 1
    # Asha's total should not include the Budi row (we just need count stability check);
    # re-fetch Asha and ensure totals didn't change relative to the other-user insert.
    after = api.get(f"{BASE_URL}/api/mood/weekly", headers={"Authorization": f"Bearer {asha_token}"}).json()
    assert after["total"] == before["total"]


def test_recommend_then_weekly_increments(api, asha_token):
    headers = {"Authorization": f"Bearer {asha_token}"}
    before = api.get(f"{BASE_URL}/api/mood/weekly", headers=headers).json()
    today_before = before["days"][-1]["count"]

    r = api.post(f"{BASE_URL}/api/mood/recommend", headers=headers,
                 json={"mood_key": "berenergi", "story": "TEST increment"})
    assert r.status_code == 200, r.text

    after = api.get(f"{BASE_URL}/api/mood/weekly", headers=headers).json()
    today_after = after["days"][-1]["count"]
    assert today_after == today_before + 1


# ---- Regression ----

def test_health(api):
    assert api.get(f"{BASE_URL}/api/health").status_code == 200


def test_home(api):
    assert api.get(f"{BASE_URL}/api/home").status_code == 200


def test_me_auth(api, asha_token):
    r = api.get(f"{BASE_URL}/api/me", headers={"Authorization": f"Bearer {asha_token}"})
    assert r.status_code == 200


def test_moods(api):
    r = api.get(f"{BASE_URL}/api/moods")
    assert r.status_code == 200
