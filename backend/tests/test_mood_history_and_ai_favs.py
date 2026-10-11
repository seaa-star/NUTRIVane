"""Backend tests for Riwayat Mood, AI Favorites, and /me/recommend regressions."""
import os
import subprocess
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://nutri-mood-ai.preview.emergentagent.com').rstrip('/')
ASHA_UID = "11111111-1111-4111-8111-111111111111"
BUDI_UID = "22222222-2222-4222-8222-222222222222"


def _mint(uid, name):
    out = subprocess.check_output(
        ["/root/.venv/bin/python", "scripts/dev_token.py", uid, name],
        cwd="/app/backend"
    ).decode().strip().splitlines()
    return out[-1]


@pytest.fixture(scope="module")
def asha():
    return _mint(ASHA_UID, "Asha Pratiwi")


@pytest.fixture(scope="module")
def budi():
    return _mint(BUDI_UID, "Budi Santoso")


def H(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ----------------- /api/mood/history -----------------
class TestMoodHistory:
    def test_no_auth_401(self):
        r = requests.get(f"{BASE_URL}/api/mood/history")
        assert r.status_code == 401

    def test_asha_list(self, asha):
        r = requests.get(f"{BASE_URL}/api/mood/history", headers=H(asha))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) <= 20
        if data:
            item = data[0]
            for k in ("id", "mood", "story", "current_country", "origin_country", "headline", "item_names", "created_at"):
                assert k in item, f"missing {k}"
            assert set(item["mood"].keys()) >= {"key", "label", "emoji"}
            assert isinstance(item["item_names"], list)
            # newest first
            ts = [d["created_at"] for d in data]
            assert ts == sorted(ts, reverse=True)

    def test_user_isolation(self, asha, budi):
        asha_ids = {d["id"] for d in requests.get(f"{BASE_URL}/api/mood/history", headers=H(asha)).json()}
        budi_data = requests.get(f"{BASE_URL}/api/mood/history", headers=H(budi)).json()
        budi_ids = {d["id"] for d in budi_data}
        assert asha_ids.isdisjoint(budi_ids) or (not asha_ids and not budi_ids)


# ----------------- /api/mood/history/{id} -----------------
class TestMoodHistoryDetail:
    def test_no_auth_401(self):
        r = requests.get(f"{BASE_URL}/api/mood/history/1")
        assert r.status_code == 401

    def test_asha_detail(self, asha):
        lst = requests.get(f"{BASE_URL}/api/mood/history", headers=H(asha)).json()
        if not lst:
            pytest.skip("Asha has no history")
        log_id = lst[0]["id"]
        r = requests.get(f"{BASE_URL}/api/mood/history/{log_id}", headers=H(asha))
        assert r.status_code == 200
        d = r.json()
        for k in ("headline", "summary", "items", "tip", "mood", "story", "source", "created_at", "id"):
            assert k in d, f"missing {k}"
        assert d["source"] == "riwayat"
        assert d["id"] == log_id
        assert isinstance(d["items"], list) and len(d["items"]) > 0
        for it in d["items"]:
            assert "recipe" in it  # may be None or a dict

    def test_other_user_404(self, asha, budi):
        # Create a Budi log by posting a mood recommend, then try to fetch as Asha
        rec = requests.post(f"{BASE_URL}/api/mood/recommend",
                            json={"mood_key": "berenergi"}, headers=H(budi))
        assert rec.status_code == 200
        budi_hist = requests.get(f"{BASE_URL}/api/mood/history", headers=H(budi)).json()
        budi_log_id = budi_hist[0]["id"]
        r = requests.get(f"{BASE_URL}/api/mood/history/{budi_log_id}", headers=H(asha))
        assert r.status_code == 404

    def test_nonexistent_404(self, asha):
        r = requests.get(f"{BASE_URL}/api/mood/history/999999999", headers=H(asha))
        assert r.status_code == 404


# ----------------- /api/ai-favorites -----------------
class TestAiFavorites:
    def test_no_auth_401(self):
        assert requests.get(f"{BASE_URL}/api/ai-favorites").status_code == 401
        assert requests.post(f"{BASE_URL}/api/ai-favorites",
                             json={"name": "x"}).status_code == 401

    def test_create_dedupe_delete(self, asha):
        name = "TEST_Es Teh Jahe Hangat"
        # cleanup if already present
        existing = requests.get(f"{BASE_URL}/api/ai-favorites", headers=H(asha)).json()
        for f in existing:
            if f["name"].lower() == name.lower():
                requests.delete(f"{BASE_URL}/api/ai-favorites/{f['id']}", headers=H(asha))

        before = requests.get(f"{BASE_URL}/api/ai-favorites", headers=H(asha)).json()
        base_len = len(before)

        # Create
        r1 = requests.post(f"{BASE_URL}/api/ai-favorites", headers=H(asha),
                           json={"name": name, "kind": "minuman", "why": "Hangatkan tenggorokan",
                                 "origin_tag": "lokal", "mood_key": "tenang"})
        assert r1.status_code == 200
        lst1 = r1.json()
        assert len(lst1) == base_len + 1
        new = [f for f in lst1 if f["name"].lower() == name.lower()][0]
        assert new["kind"] == "minuman"
        assert new["origin_tag"] == "lokal"
        assert new["why"] == "Hangatkan tenggorokan"
        fav_id = new["id"]

        # Dedupe: same name different case, different why
        r2 = requests.post(f"{BASE_URL}/api/ai-favorites", headers=H(asha),
                           json={"name": name.upper(), "kind": "makanan",
                                 "why": "updated why", "origin_tag": "umum"})
        assert r2.status_code == 200
        lst2 = r2.json()
        assert len(lst2) == len(lst1), "duplicate should not be created"
        updated = [f for f in lst2 if f["id"] == fav_id][0]
        assert updated["why"] == "updated why"

        # GET
        got = requests.get(f"{BASE_URL}/api/ai-favorites", headers=H(asha)).json()
        assert any(f["id"] == fav_id for f in got)

        # Delete as different user → no-op
        budi_tok = _mint(BUDI_UID, "Budi Santoso")
        asha_before = requests.get(f"{BASE_URL}/api/ai-favorites", headers=H(asha)).json()
        requests.delete(f"{BASE_URL}/api/ai-favorites/{fav_id}", headers=H(budi_tok))
        asha_after = requests.get(f"{BASE_URL}/api/ai-favorites", headers=H(asha)).json()
        assert len(asha_before) == len(asha_after)
        assert any(f["id"] == fav_id for f in asha_after)

        # Delete properly
        r3 = requests.delete(f"{BASE_URL}/api/ai-favorites/{fav_id}", headers=H(asha))
        assert r3.status_code == 200
        assert not any(f["id"] == fav_id for f in r3.json())

    def test_validation(self, asha):
        # empty name → 422
        r = requests.post(f"{BASE_URL}/api/ai-favorites", headers=H(asha),
                          json={"name": "", "kind": "minuman"})
        assert r.status_code == 422

        # kind other than minuman coerces to makanan
        name = "TEST_Coerce Kind"
        requests.post(f"{BASE_URL}/api/ai-favorites", headers=H(asha),
                      json={"name": name, "kind": "weird", "origin_tag": "elsewhere"})
        lst = requests.get(f"{BASE_URL}/api/ai-favorites", headers=H(asha)).json()
        item = [f for f in lst if f["name"].lower() == name.lower()][0]
        assert item["kind"] == "makanan"
        assert item["origin_tag"] == "umum"
        requests.delete(f"{BASE_URL}/api/ai-favorites/{item['id']}", headers=H(asha))


# ----------------- /api/me includes ai_favorites, /recommend returns date -----------------
class TestMeAndRecommend:
    def test_me_has_ai_favorites(self, asha):
        r = requests.get(f"{BASE_URL}/api/me", headers=H(asha))
        assert r.status_code == 200
        d = r.json()
        assert "ai_favorites" in d
        assert isinstance(d["ai_favorites"], list)

    def test_recommend_returns_date(self, asha):
        moods = requests.get(f"{BASE_URL}/api/moods").json()
        mk = moods[0]["key"]
        r = requests.post(f"{BASE_URL}/api/mood/recommend",
                          json={"mood_key": mk}, headers=H(asha))
        assert r.status_code == 200
        d = r.json()
        assert "date" in d
        import re
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", d["date"])


# ----------------- Regression -----------------
class TestRegression:
    def test_health(self):
        assert requests.get(f"{BASE_URL}/api/health").status_code == 200

    def test_home(self):
        assert requests.get(f"{BASE_URL}/api/home").status_code == 200

    def test_mood_weekly_guest(self):
        r = requests.get(f"{BASE_URL}/api/mood/weekly")
        assert r.status_code == 200
        assert len(r.json()["days"]) == 7

    def test_favorites(self, asha):
        assert requests.get(f"{BASE_URL}/api/favorites", headers=H(asha)).status_code == 200
