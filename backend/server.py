from fastapi import FastAPI, APIRouter, HTTPException, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone, timedelta, date
import json
import re
import uuid
import httpx
from urllib.parse import urlsplit

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from sqlalchemy import text  # noqa: E402
from db import SessionLocal, init_db, row_dict, engine  # noqa: E402
from auth import optional_user, require_user  # noqa: E402

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')
INSIGHT_PROVIDER = os.environ.get('INSIGHT_MODEL_PROVIDER', 'gemini')
INSIGHT_MODEL = os.environ.get('INSIGHT_MODEL_NAME', 'gemini-3-flash-preview')
VISION_PROVIDER = os.environ.get('VISION_MODEL_PROVIDER', 'gemini')
VISION_MODEL = os.environ.get('VISION_MODEL_NAME', 'gemini-3.1-pro-preview')
TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY', '')
SCAN_MAX_SOURCES = int(os.environ.get('SCAN_MAX_SOURCES', '5'))
SCAN_CACHE_TTL_DAYS = int(os.environ.get('SCAN_CACHE_TTL_DAYS', '30'))
APP_TZ = ZoneInfo(os.environ.get('APP_TIMEZONE', 'Asia/Jakarta'))

app = FastAPI(title="NutriVane API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("nutrivane")


async def get_db():
    async with SessionLocal() as s:
        yield s


# ----------------------------- Models -----------------------------
class ScanRequest(BaseModel):
    benchmark_slug: str
    measure: bool = False
    image_base64: Optional[str] = None


class AiScanRequest(BaseModel):
    image_base64: Optional[str] = None
    dish_name: str = Field(default="", max_length=120)


class MoodRecommendRequest(BaseModel):
    mood_key: str
    story: str = Field(default="", max_length=1200)
    current_country: str = Field(default="", max_length=60)
    origin_country: str = Field(default="", max_length=60)


class CountriesRequest(BaseModel):
    current_country: str = Field(default="", max_length=60)
    origin_country: str = Field(default="", max_length=60)


class AiFavoriteRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = Field(default="makanan", max_length=20)
    why: str = Field(default="", max_length=400)
    origin_tag: str = Field(default="umum", max_length=20)
    mood_key: Optional[str] = Field(default=None, max_length=40)


class ScanFavoriteRequest(BaseModel):
    dish: str = Field(min_length=1, max_length=120)
    result: dict


# ----------------------------- AI helpers -----------------------------
async def generate_insight_text(recipe: dict) -> str:
    """Simple, cost-efficient AI (standard model) for a short flavor insight."""
    spice_line = ", ".join(f"{s['name']} {s['avg']}{s['unit']}" for s in recipe["spices"][:5])
    fallback = (
        f"Profil rasa {recipe['name'].lower()} didominasi {recipe['spices'][0]['name'].lower()} "
        f"(rata-rata {recipe['spices'][0]['avg']}{recipe['spices'][0]['unit']} dari {len(recipe['sources'])} sumber resep). "
        f"Gunakan angka ini sebagai panduan, bukan takaran mutlak."
    )
    if not EMERGENT_LLM_KEY:
        return fallback
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"insight-{recipe['slug']}",
            system_message=(
                "Kamu asisten kuliner NutriVane. Jawab dalam Bahasa Indonesia yang hangat dan singkat "
                "(maksimal 2 kalimat). Jelaskan karakter rasa dari rata-rata bumbu, tanpa menyuruh atau menghakimi."
            ),
        ).with_model(INSIGHT_PROVIDER, INSIGHT_MODEL)
        prompt = (
            f"Menu: {recipe['name']}. Catatan rasa: {recipe['flavor_note']}. "
            f"Rata-rata bumbu dominan dari {len(recipe['sources'])} sumber resep: {spice_line}. "
            f"Tulis 2 kalimat insight singkat soal profil rasanya."
        )
        resp = await chat.send_message(UserMessage(text=prompt))
        text_ = (resp or "").strip()
        return text_ or fallback
    except Exception as e:
        logger.warning(f"insight AI failed, using fallback: {e}")
        return fallback


async def analyze_food_image(image_base64: str) -> str:
    """Stronger AI (vision model) only when the user actually sends a photo."""
    if not EMERGENT_LLM_KEY:
        return "Analisis foto butuh koneksi AI. Untuk beta, pilih menu benchmark di bawah."
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id="scan-vision",
            system_message=(
                "Kamu asisten NutriVane. Lihat foto makanan dan jawab Bahasa Indonesia singkat (2 kalimat): "
                "sebutkan kemungkinan nama hidangannya dan bumbu/rempah yang kemungkinan dominan. "
                "Jika tidak yakin, katakan dengan jujur."
            ),
        ).with_model(VISION_PROVIDER, VISION_MODEL)
        clean = image_base64.split(",", 1)[-1] if image_base64.startswith("data:") else image_base64
        msg = UserMessage(
            text="Makanan apa ini dan bumbu apa yang mungkin dominan?",
            file_contents=[ImageContent(image_base64=clean)],
        )
        resp = await chat.send_message(msg)
        return (resp or "").strip() or "Belum bisa mengenali makanan ini dengan yakin."
    except Exception as e:
        logger.warning(f"vision AI failed: {e}")
        return "Belum bisa menganalisis foto saat ini. Coba lagi atau pilih menu benchmark."


def _parse_json_block(raw: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.M).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    return json.loads(cleaned[start:end + 1])


def _domain_name(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or url).lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return url


async def identify_food_name(image_base64: str) -> dict:
    """Vision AI → nama hidangan terstruktur {name, confidence, note}."""
    if not EMERGENT_LLM_KEY:
        return {"name": "", "confidence": "rendah", "note": "AI vision belum aktif."}
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"identify-{uuid.uuid4()}",
            system_message=(
                "Kamu ahli kuliner. Lihat foto makanan/minuman dan tentukan nama hidangannya. "
                "Keluarkan HANYA JSON valid tanpa teks lain: "
                '{"name": str (nama hidangan paling mungkin dalam Bahasa Indonesia), '
                '"confidence": "tinggi"|"sedang"|"rendah", "note": str (1 kalimat singkat alasan)}. '
                "Jika gambar bukan makanan/minuman, isi name dengan string kosong dan confidence 'rendah'."
            ),
        ).with_model(VISION_PROVIDER, VISION_MODEL)
        clean = image_base64.split(",", 1)[-1] if image_base64.startswith("data:") else image_base64
        msg = UserMessage(text="Makanan atau minuman apa ini? Jawab dalam JSON.",
                          file_contents=[ImageContent(image_base64=clean)])
        resp = await chat.send_message(msg)
        data = _parse_json_block(resp)
        conf = data.get("confidence")
        return {"name": str(data.get("name") or "").strip(),
                "confidence": conf if conf in ("tinggi", "sedang", "rendah") else "sedang",
                "note": str(data.get("note") or "")}
    except Exception as e:
        logger.warning(f"identify food failed: {e}")
        return {"name": "", "confidence": "rendah", "note": ""}


async def tavily_recipe_search(dish: str, max_results: int = 5) -> list:
    """Cari resep di web via Tavily → list {name, title, url, content}."""
    if not TAVILY_API_KEY:
        return []
    try:
        body = {"query": f"resep {dish} bahan dan bumbu lengkap takaran",
                "search_depth": "basic", "max_results": max_results,
                "include_answer": False, "include_raw_content": True}
        headers = {"Authorization": f"Bearer {TAVILY_API_KEY}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=25) as c:
            r = await c.post("https://api.tavily.com/search", json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
        out, seen = [], set()
        for x in data.get("results", []):
            url = x.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            content = (x.get("raw_content") or x.get("content") or "")[:2200]
            if not content:
                continue
            out.append({"name": _domain_name(url), "title": (x.get("title") or dish)[:140],
                        "url": url, "content": content})
        return out
    except Exception as e:
        logger.warning(f"tavily search failed: {e}")
        return []


def _parse_nutrition(raw) -> Optional[dict]:
    """Normalisasi estimasi gizi dari LLM menjadi angka non-negatif; None bila tidak ada data."""
    if not isinstance(raw, dict):
        return None

    def num(v):
        try:
            n = float(v)
            return round(n, 1) if n >= 0 else 0.0
        except (TypeError, ValueError):
            return 0.0

    nutr = {
        "serving": str(raw.get("serving") or "per porsi").strip()[:40],
        "calories": num(raw.get("calories")),
        "protein_g": num(raw.get("protein_g")),
        "carbs_g": num(raw.get("carbs_g")),
        "fat_g": num(raw.get("fat_g")),
        "fiber_g": num(raw.get("fiber_g")),
        "note": str(raw.get("note") or "").strip()[:240],
    }
    if nutr["calories"] <= 0 and nutr["protein_g"] <= 0 and nutr["carbs_g"] <= 0 and nutr["fat_g"] <= 0:
        return None
    return nutr


async def ai_extract_average(dish: str, sources: list) -> Optional[dict]:
    """Gemini ekstrak + rata-ratakan bumbu dari banyak kutipan resep → JSON."""
    if not EMERGENT_LLM_KEY or not sources:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"extract-{uuid.uuid4()}",
            system_message=(
                "Kamu ahli kuliner & gizi NutriVane. Kamu diberi beberapa kutipan resep dari berbagai sumber web untuk satu hidangan. "
                "Tugasmu: (1) ekstrak bumbu/rempah utama beserta takarannya dari tiap sumber lalu hitung RATA-RATA takaran, "
                "dan (2) perkirakan KANDUNGAN GIZI per satu porsi sajian. Jawab dalam Bahasa Indonesia. "
                "Keluarkan HANYA JSON valid tanpa teks lain: "
                '{"dish": str, "spices": [{"name": str, "avg": number (>0), '
                '"unit": str (mis. "siung","gr","sdm","sdt","butir","ml","buah","lembar","cm"), '
                '"sources": int (jumlah sumber yang mencantumkannya)}], '
                '"insight": str (1-2 kalimat profil rasa yang hangat, tanpa menghakimi), '
                '"nutrition": {"serving": str (mis. "per porsi"), "calories": number (kkal), '
                '"protein_g": number, "carbs_g": number, "fat_g": number, "fiber_g": number, '
                '"note": str (1 kalimat ramah soal gizi, tanpa menghakimi/medis)}}. '
                "Aturan bumbu: maksimal 8 bumbu paling dominan, urut dari yang paling sering/banyak dipakai. "
                "Fokus pada bumbu & rempah (bawang, cabai, kemiri, ketumbar, lengkuas, jahe, kunyit, serai, daun, dsb.); "
                "jangan masukkan bahan utama non-bumbu seperti daging, nasi, air, tepung. "
                "Jangan mengarang takaran; jika takaran suatu bumbu tidak jelas di sebuah sumber, jangan hitung sumber itu untuk bumbu tsb. "
                "Jika satuan berbeda antar sumber, pilih satuan yang paling umum dan konversikan sewajarnya. "
                "Aturan gizi: berikan ESTIMASI wajar per porsi sajian normal (bukan seluruh panci) berdasarkan bahan khas hidangan. "
                "Semua angka gizi harus bilangan non-negatif; jika sangat tidak yakin untuk satu nilai, isi 0. Hindari klaim medis."
            ),
        ).with_model(INSIGHT_PROVIDER, INSIGHT_MODEL)
        blocks = [f"[Sumber {i}: {s['name']}]\n{s['content']}" for i, s in enumerate(sources, 1)]
        prompt = (f"Hidangan: {dish}\n\nKutipan {len(sources)} sumber resep:\n\n"
                  + "\n\n".join(blocks) + "\n\nEkstrak & rata-ratakan bumbunya, lalu perkirakan kandungan gizi per porsi, sesuai skema JSON.")
        resp = await chat.send_message(UserMessage(text=prompt))
        data = _parse_json_block(resp)
        spices = []
        for sp in (data.get("spices") or [])[:8]:
            try:
                avg = float(sp.get("avg"))
            except (TypeError, ValueError):
                continue
            if avg <= 0 or not sp.get("name"):
                continue
            spices.append({"name": str(sp["name"]).strip(), "avg": round(avg, 1),
                           "unit": str(sp.get("unit") or "").strip(),
                           "sources": int(sp.get("sources") or 1)})
        if not spices:
            return None
        return {"dish": str(data.get("dish") or dish), "spices": spices,
                "insight": str(data.get("insight") or ""),
                "nutrition": _parse_nutrition(data.get("nutrition"))}
    except Exception as e:
        logger.warning(f"ai extract failed: {e}")
        return None


def mood_fallback(mood: dict, recipes: list, current_country: str, origin_country: str) -> dict:
    where = f" di {current_country}" if current_country else ""
    items = [{
        "name": r["name"], "kind": "minuman" if r["category"] in ("minuman", "teh") else "makanan",
        "why": r["tagline"], "slug": r["slug"], "origin_tag": "lokal",
    } for r in recipes[:3]]
    return {
        "headline": f"Pilihan {mood['label'].lower()} untukmu",
        "summary": f"Kami pilihkan menu yang biasanya cocok saat kamu ingin merasa {mood['label'].lower()}{where}.",
        "items": items,
        "tip": "Mulai dari porsi kecil dan nikmati pelan-pelan — tubuhmu yang paling tahu.",
    }


async def recommend_mood_ai(mood: dict, story: str, current_country: str, origin_country: str, catalog: list) -> Optional[dict]:
    if not EMERGENT_LLM_KEY:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"mood-{uuid.uuid4()}",
            system_message=(
                "Kamu asisten kuliner NutriVane yang hangat, empatik, dan tidak menghakimi. "
                "Selalu jawab dalam Bahasa Indonesia. Keluarkan HANYA JSON valid tanpa teks lain, dengan skema: "
                '{"headline": str (maks 8 kata), "summary": str (1-2 kalimat yang merespons cerita/mood pengguna), '
                '"items": [{"name": str, "kind": "makanan"|"minuman", "why": str (1 kalimat), '
                '"slug": str|null (isi hanya jika sama persis dengan menu di katalog, selain itu null), '
                '"origin_tag": "lokal"|"asal"|"umum"}], "tip": str (1 kalimat)}. '
                "Berikan 4-5 items: campuran makanan dan minimal 1 minuman. "
                "'lokal' = hidangan yang mudah ditemukan di negara tempat tinggal saat ini; "
                "'asal' = comfort food dari negara asal pengguna; 'umum' = saran umum. "
                "Jika negara asal berbeda dengan negara saat ini, sertakan minimal 1 item 'asal' dan 1 item 'lokal'. "
                "Jika negara tidak diisi, anggap pengguna berada di Indonesia. Hindari saran medis."
            ),
        ).with_model(INSIGHT_PROVIDER, INSIGHT_MODEL)
        catalog_line = "; ".join(f"{r['slug']} = {r['name']} ({r['category_label']}: {r['tagline']})" for r in catalog)
        prompt = (
            f"Mood yang dipilih: {mood['label']} {mood['emoji']} — {mood['subtitle']}.\n"
            f"Cerita pengguna: {story.strip() or '(tidak ada cerita, gunakan mood saja)'}\n"
            f"Negara tempat tinggal saat ini: {current_country or '(tidak diisi)'}\n"
            f"Negara asal: {origin_country or '(tidak diisi)'}\n"
            f"Katalog menu NutriVane (slug = nama): {catalog_line}\n"
            "Buat rekomendasi makanan & minuman yang paling pas untuk perasaan dan konteks ini."
        )
        resp = await chat.send_message(UserMessage(text=prompt))
        data = _parse_json_block(resp)
        valid_slugs = {r["slug"] for r in catalog}
        items = []
        for it in (data.get("items") or [])[:5]:
            if not it.get("name"):
                continue
            slug = it.get("slug")
            items.append({
                "name": str(it["name"]), "kind": "minuman" if it.get("kind") == "minuman" else "makanan",
                "why": str(it.get("why") or ""), "slug": slug if slug in valid_slugs else None,
                "origin_tag": it.get("origin_tag") if it.get("origin_tag") in ("lokal", "asal", "umum") else "umum",
            })
        if not items:
            return None
        return {
            "headline": str(data.get("headline") or f"Pilihan {mood['label'].lower()} untukmu"),
            "summary": str(data.get("summary") or ""), "items": items, "tip": str(data.get("tip") or ""),
        }
    except Exception as e:
        logger.warning(f"mood AI failed, using fallback: {e}")
        return None


# ----------------------------- Data helpers -----------------------------
RECIPE_COLS = "slug,name,category,category_label,porsi,image,tagline,flavor_note,spices,sources"


def recipe_card(r: dict) -> dict:
    return {
        "slug": r["slug"], "name": r["name"], "category": r["category"],
        "category_label": r["category_label"], "porsi": r["porsi"], "image": r["image"],
        "tagline": r["tagline"], "source_count": len(r["sources"]),
    }


def with_pct(spices: list) -> list:
    max_avg = max(s["avg"] for s in spices) or 1
    return [{**s, "pct": round(s["avg"] / max_avg * 100)} for s in spices]


async def fetch_recipe(db, slug: str) -> dict:
    row = (await db.execute(text(f"select {RECIPE_COLS} from recipes where slug=:slug"), {"slug": slug})).first()
    if not row:
        raise HTTPException(status_code=404, detail="Menu tidak ditemukan")
    return row_dict(row)


async def fetch_recipes(db, slugs: Optional[list] = None, category: Optional[str] = None, q: Optional[str] = None) -> list:
    sql = f"select {RECIPE_COLS} from recipes where 1=1"
    params = {}
    if slugs is not None:
        if not slugs:
            return []
        sql += " and slug = any(:slugs)"
        params["slugs"] = slugs
    if category and category != "semua":
        sql += " and category=:category"
        params["category"] = category
    if q:
        sql += " and (name ilike :q or tagline ilike :q)"
        params["q"] = f"%{q}%"
    sql += " order by sort_order"
    return [row_dict(r) for r in (await db.execute(text(sql), params)).all()]


async def get_or_create_insight(db, recipe: dict) -> tuple:
    row = (await db.execute(text("select text from insights where slug=:slug"), {"slug": recipe["slug"]})).first()
    if row and row[0]:
        return row[0], True
    text_ = await generate_insight_text(recipe)
    await db.execute(text(
        "insert into insights(slug,text,updated_at) values(:slug,:text,now()) "
        "on conflict (slug) do update set text=excluded.text, updated_at=now()"
    ), {"slug": recipe["slug"], "text": text_})
    await db.commit()
    return text_, False


def compute_streak(days: list, today: date) -> int:
    s = set(days)
    cur = today if today in s else (today - timedelta(days=1) if (today - timedelta(days=1)) in s else None)
    n = 0
    while cur and cur in s:
        n += 1
        cur -= timedelta(days=1)
    return n


async def user_stats(db, user_id: Optional[str]) -> dict:
    if not user_id:
        return {"streak_days": 0, "plates_recognized": 0, "weekly_delta": 0}
    rows = (await db.execute(text(
        "select (created_at at time zone :tz)::date as d, count(*) as n from scans "
        "where user_id=cast(:uid as uuid) group by d order by d desc"
    ), {"uid": user_id, "tz": APP_TZ.key})).all()
    today = datetime.now(APP_TZ).date()
    plates = sum(r.n for r in rows)
    weekly = sum(r.n for r in rows if r.d >= today - timedelta(days=6))
    return {"streak_days": compute_streak([r.d for r in rows], today), "plates_recognized": plates, "weekly_delta": weekly}


async def upsert_profile(db, user: dict):
    await db.execute(text(
        "insert into profiles(user_id,email,display_name,avatar_url,last_seen_at) "
        "values(cast(:id as uuid),:email,:name,:avatar_url,now()) "
        "on conflict (user_id) do update set email=excluded.email, display_name=excluded.display_name, "
        "avatar_url=excluded.avatar_url, last_seen_at=now()"
    ), user)
    await db.commit()


async def favorite_slugs(db, user_id: str) -> list:
    rows = (await db.execute(text(
        "select slug from favorites where user_id=cast(:uid as uuid) order by created_at desc"), {"uid": user_id})).all()
    return [r[0] for r in rows]


async def ai_favorites(db, user_id: str) -> list:
    rows = (await db.execute(text(
        "select id,name,kind,why,origin_tag,mood_key,created_at from ai_favorites "
        "where user_id=cast(:uid as uuid) order by created_at desc"), {"uid": user_id})).all()
    return [{**row_dict(r), "created_at": r.created_at.isoformat()} for r in rows]


def _as_dict(v) -> dict:
    if isinstance(v, dict):
        return v
    try:
        return json.loads(v) if v else {}
    except Exception:
        return {}


async def scan_history_list(db, user_id: str, limit: int = 20) -> list:
    rows = (await db.execute(text(
        "select id, dish_name, benchmark_slug, had_image, result, created_at from scans "
        "where user_id=cast(:uid as uuid) and result is not null "
        "order by created_at desc limit :lim"
    ), {"uid": user_id, "lim": limit})).all()
    out = []
    for r in rows:
        res = _as_dict(r.result)
        out.append({
            "id": r.id,
            "dish": res.get("dish") or res.get("menu_name") or r.dish_name,
            "mode": res.get("mode"),
            "cached": bool(res.get("cached")),
            "source_count": res.get("source_count", 0),
            "spice_count": len(res.get("spices") or []),
            "confidence": res.get("confidence"),
            "had_image": r.had_image,
            "benchmark_slug": res.get("benchmark_slug"),
            "created_at": r.created_at.isoformat(),
        })
    return out


async def scan_favorites_list(db, user_id: str) -> list:
    rows = (await db.execute(text(
        "select id, dish, result, created_at from scan_favorites "
        "where user_id=cast(:uid as uuid) order by created_at desc"), {"uid": user_id})).all()
    out = []
    for r in rows:
        res = _as_dict(r.result)
        out.append({
            "id": r.id, "dish": r.dish,
            "source_count": res.get("source_count", 0),
            "spice_count": len(res.get("spices") or []),
            "created_at": r.created_at.isoformat(),
        })
    return out


async def moods_map(db) -> dict:
    return {r.key: {"key": r.key, "label": r.label, "emoji": r.emoji}
            for r in (await db.execute(text("select key,label,emoji from moods"))).all()}


def _json(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


# ----------------------------- Endpoints -----------------------------
@api_router.get("/")
async def root():
    return {"app": "NutriVane", "status": "ok"}


@api_router.get("/health")
async def health(db=Depends(get_db)):
    await db.execute(text("select 1"))
    return {"ok": True}


@api_router.get("/home")
async def home(user=Depends(optional_user), db=Depends(get_db)):
    now = datetime.now(APP_TZ)
    hour = now.hour
    part = "pagi" if hour < 11 else ("siang" if hour < 15 else ("sore" if hour < 19 else "malam"))
    stats = await user_stats(db, user["id"] if user else None)
    name = user["name"].split(" ")[0] if user else "teman"
    moods = [row_dict(r) for r in (await db.execute(text("select key,label,emoji,subtitle from moods order by sort_order"))).all()]
    picks = await fetch_recipes(db)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "part_of_day": part,
        "authenticated": bool(user),
        "greeting_name": name,
        "headline": "Makan lebih paham, mulai dari satu piring.",
        "subhead": (f"Selamat datang kembali, {name}. Yuk kenali isi piringmu {part} ini."
                    if user else f"Halo! Yuk kenali isi piringmu {part} ini. Masuk untuk menyimpan streak dan piringmu."),
        **stats,
        "featured": {
            "badge": "Beta insight",
            "title": "Apa yang ada di balik rasa rendangmu?",
            "body": "Bandingkan bumbu dari banyak resep, lalu pilih dengan lebih yakin.",
            "slug": "rendang",
        },
        "moods": moods,
        "picks": [recipe_card(r) for r in picks],
    }


@api_router.get("/categories")
async def categories(db=Depends(get_db)):
    return [row_dict(r) for r in (await db.execute(text("select key,label from categories order by sort_order"))).all()]


@api_router.get("/recipes")
async def list_recipes(category: Optional[str] = None, q: Optional[str] = None, db=Depends(get_db)):
    return [recipe_card(r) for r in await fetch_recipes(db, category=category, q=q)]


@api_router.get("/recipes/{slug}")
async def recipe_detail(slug: str, db=Depends(get_db)):
    r = await fetch_recipe(db, slug)
    return {**{k: r[k] for k in ("slug", "name", "category", "category_label", "porsi", "image", "tagline", "flavor_note")},
            "source_count": len(r["sources"]), "sources": r["sources"], "spices": with_pct(r["spices"])}


@api_router.get("/moods")
async def list_moods(db=Depends(get_db)):
    return [row_dict(r) for r in (await db.execute(text(
        "select key,label,emoji,subtitle,question,helper from moods order by sort_order"))).all()]


@api_router.get("/moods/{key}")
async def mood_detail(key: str, db=Depends(get_db)):
    row = (await db.execute(text(
        "select key,label,emoji,question,helper,recipe_slugs from moods where key=:key"), {"key": key})).first()
    if not row:
        raise HTTPException(status_code=404, detail="Mood tidak ditemukan")
    m = row_dict(row)
    recs = await fetch_recipes(db, slugs=m.pop("recipe_slugs"))
    return {**m, "recipes": [recipe_card(r) for r in recs]}


@api_router.post("/mood/recommend")
async def mood_recommend(req: MoodRecommendRequest, user=Depends(optional_user), db=Depends(get_db)):
    row = (await db.execute(text(
        "select key,label,emoji,subtitle,recipe_slugs from moods where key=:key"), {"key": req.mood_key})).first()
    if not row:
        raise HTTPException(status_code=404, detail="Mood tidak ditemukan")
    mood = row_dict(row)
    current_country, origin_country = req.current_country.strip(), req.origin_country.strip()
    catalog = await fetch_recipes(db)
    recipes_by_slug = {r["slug"]: r for r in catalog}

    rec = await recommend_mood_ai(mood, req.story, current_country, origin_country, catalog)
    source = "ai" if rec else "fallback"
    if not rec:
        rec = mood_fallback(mood, [recipes_by_slug[s] for s in mood["recipe_slugs"] if s in recipes_by_slug],
                            current_country, origin_country)
    for it in rec["items"]:
        it["recipe"] = recipe_card(recipes_by_slug[it["slug"]]) if it.get("slug") else None

    await db.execute(text(
        "insert into mood_logs(user_id,mood_key,story,current_country,origin_country,recommendation) "
        "values(cast(:uid as uuid),:key,:story,:cur,:org,cast(:rec as jsonb))"
    ), {"uid": user["id"] if user else None, "key": mood["key"], "story": req.story.strip(),
        "cur": current_country or None, "org": origin_country or None, "rec": json.dumps(rec)})
    if user and (current_country or origin_country):
        await upsert_profile(db, user)
        await db.execute(text(
            "update profiles set current_country=:cur, origin_country=:org where user_id=cast(:uid as uuid)"
        ), {"cur": current_country or None, "org": origin_country or None, "uid": user["id"]})
    await db.commit()
    return {**rec, "mood": {k: mood[k] for k in ("key", "label", "emoji")}, "source": source,
            "date": datetime.now(APP_TZ).date().isoformat(),
            "current_country": current_country, "origin_country": origin_country, "saved_to_account": bool(user)}


@api_router.get("/mood/history")
async def mood_history(limit: int = 20, user=Depends(require_user), db=Depends(get_db)):
    moods = await moods_map(db)
    rows = (await db.execute(text(
        "select id,mood_key,story,current_country,origin_country,recommendation,created_at from mood_logs "
        "where user_id=cast(:uid as uuid) order by created_at desc limit :limit"
    ), {"uid": user["id"], "limit": max(1, min(limit, 50))})).all()
    out = []
    for r in rows:
        rec = _json(r.recommendation)
        out.append({
            "id": r.id, "mood": moods.get(r.mood_key, {"key": r.mood_key, "label": r.mood_key, "emoji": ""}),
            "story": r.story, "current_country": r.current_country or "", "origin_country": r.origin_country or "",
            "headline": rec.get("headline", ""), "item_names": [it.get("name") for it in rec.get("items", [])][:5],
            "created_at": r.created_at.isoformat(),
        })
    return out


@api_router.get("/mood/history/{log_id}")
async def mood_history_detail(log_id: int, user=Depends(require_user), db=Depends(get_db)):
    row = (await db.execute(text(
        "select id,mood_key,story,current_country,origin_country,recommendation,created_at from mood_logs "
        "where id=:id and user_id=cast(:uid as uuid)"), {"id": log_id, "uid": user["id"]})).first()
    if not row:
        raise HTTPException(status_code=404, detail="Riwayat tidak ditemukan")
    moods = await moods_map(db)
    rec = _json(row.recommendation)
    return {**rec, "id": row.id, "mood": moods.get(row.mood_key, {"key": row.mood_key, "label": row.mood_key, "emoji": ""}),
            "story": row.story, "current_country": row.current_country or "", "origin_country": row.origin_country or "",
            "source": "riwayat", "created_at": row.created_at.isoformat()}


@api_router.get("/ai-favorites")
async def list_ai_favorites(user=Depends(require_user), db=Depends(get_db)):
    return await ai_favorites(db, user["id"])


@api_router.post("/ai-favorites")
async def add_ai_favorite(req: AiFavoriteRequest, user=Depends(require_user), db=Depends(get_db)):
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="Nama saran tidak boleh kosong")
    await db.execute(text(
        "insert into ai_favorites(user_id,name,kind,why,origin_tag,mood_key) "
        "values(cast(:uid as uuid),:name,:kind,:why,:tag,:mood) "
        "on conflict (user_id, lower(name)) do update set why=excluded.why, kind=excluded.kind, origin_tag=excluded.origin_tag"
    ), {"uid": user["id"], "name": req.name.strip(), "kind": "minuman" if req.kind == "minuman" else "makanan",
        "why": req.why.strip(), "tag": req.origin_tag if req.origin_tag in ("lokal", "asal", "umum") else "umum",
        "mood": req.mood_key})
    await db.commit()
    return await ai_favorites(db, user["id"])


@api_router.delete("/ai-favorites/{fav_id}")
async def remove_ai_favorite(fav_id: int, user=Depends(require_user), db=Depends(get_db)):
    await db.execute(text("delete from ai_favorites where id=:id and user_id=cast(:uid as uuid)"),
                     {"id": fav_id, "uid": user["id"]})
    await db.commit()
    return await ai_favorites(db, user["id"])


# ----------------------------- Scan history & scan favorites (auth required) -----------------------------
@api_router.get("/scans/history")
async def get_scan_history(limit: int = 20, user=Depends(require_user), db=Depends(get_db)):
    return await scan_history_list(db, user["id"], min(max(limit, 1), 50))


@api_router.get("/scans/history/{scan_id}")
async def get_scan_history_detail(scan_id: int, user=Depends(require_user), db=Depends(get_db)):
    row = (await db.execute(text(
        "select id, had_image, result, created_at from scans "
        "where id=:id and user_id=cast(:uid as uuid)"), {"id": scan_id, "uid": user["id"]})).first()
    if not row or not row.result:
        raise HTTPException(status_code=404, detail="Riwayat scan tidak ditemukan")
    res = _as_dict(row.result)
    return {**res, "id": row.id, "from_history": True, "created_at": row.created_at.isoformat()}


@api_router.get("/scan-favorites")
async def list_scan_favorites(user=Depends(require_user), db=Depends(get_db)):
    return await scan_favorites_list(db, user["id"])


@api_router.post("/scan-favorites")
async def add_scan_favorite(req: ScanFavoriteRequest, user=Depends(require_user), db=Depends(get_db)):
    dish = req.dish.strip()
    if not dish:
        raise HTTPException(status_code=422, detail="Nama makanan tidak boleh kosong")
    snapshot = {k: v for k, v in (req.result or {}).items() if k != "stats"}
    await db.execute(text(
        "insert into scan_favorites(user_id,dish,result) "
        "values(cast(:uid as uuid),:dish,cast(:result as jsonb)) "
        "on conflict (user_id, lower(dish)) do update set result=excluded.result, created_at=now()"
    ), {"uid": user["id"], "dish": dish, "result": json.dumps(snapshot)})
    await db.commit()
    return await scan_favorites_list(db, user["id"])


@api_router.get("/scan-favorites/{fav_id}")
async def get_scan_favorite_detail(fav_id: int, user=Depends(require_user), db=Depends(get_db)):
    row = (await db.execute(text(
        "select id, dish, result, created_at from scan_favorites "
        "where id=:id and user_id=cast(:uid as uuid)"), {"id": fav_id, "uid": user["id"]})).first()
    if not row:
        raise HTTPException(status_code=404, detail="Favorit scan tidak ditemukan")
    res = _as_dict(row.result)
    return {**res, "id": row.id, "from_favorite": True, "created_at": row.created_at.isoformat()}


@api_router.delete("/scan-favorites/{fav_id}")
async def remove_scan_favorite(fav_id: int, user=Depends(require_user), db=Depends(get_db)):
    await db.execute(text("delete from scan_favorites where id=:id and user_id=cast(:uid as uuid)"),
                     {"id": fav_id, "uid": user["id"]})
    await db.commit()
    return await scan_favorites_list(db, user["id"])


DAY_LABELS = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


@api_router.get("/mood/weekly")
async def mood_weekly(user=Depends(optional_user), db=Depends(get_db)):
    today = datetime.now(APP_TZ).date()
    start = today - timedelta(days=6)
    moods = {r.key: r for r in (await db.execute(text("select key,label,emoji from moods"))).all()}
    per_day = {start + timedelta(days=i): {} for i in range(7)}
    if user:
        rows = (await db.execute(text(
            "select (created_at at time zone :tz)::date as d, mood_key, count(*) as n from mood_logs "
            "where user_id=cast(:uid as uuid) and created_at >= cast(:start as timestamptz) "
            "group by d, mood_key"
        ), {"uid": user["id"], "tz": APP_TZ.key, "start": datetime.combine(start - timedelta(days=1), datetime.min.time(), APP_TZ)})).all()
        for r in rows:
            if r.d in per_day and r.mood_key in moods:
                per_day[r.d][r.mood_key] = r.n
    totals = {}
    days = []
    for d, counts in per_day.items():
        dom = max(counts, key=counts.get) if counts else None
        for k, n in counts.items():
            totals[k] = totals.get(k, 0) + n
        days.append({
            "date": d.isoformat(), "label": DAY_LABELS[d.weekday()], "is_today": d == today,
            "count": sum(counts.values()), "moods": counts,
            "dominant": {"key": dom, "label": moods[dom].label, "emoji": moods[dom].emoji} if dom else None,
        })
    top_key = max(totals, key=totals.get) if totals else None
    return {
        "authenticated": bool(user), "days": days, "total": sum(totals.values()),
        "active_days": sum(1 for d in days if d["count"]),
        "top": {"key": top_key, "label": moods[top_key].label, "emoji": moods[top_key].emoji, "count": totals[top_key]} if top_key else None,
    }


@api_router.get("/insight/{slug}")
async def get_insight(slug: str, db=Depends(get_db)):
    r = await fetch_recipe(db, slug)
    text_, cached = await get_or_create_insight(db, r)
    return {"slug": slug, "text": text_, "cached": cached}


@api_router.post("/scan")
async def scan(req: ScanRequest, user=Depends(optional_user), db=Depends(get_db)):
    row = (await db.execute(text(f"select {RECIPE_COLS} from recipes where slug=:slug"), {"slug": req.benchmark_slug})).first()
    if not row:
        raise HTTPException(status_code=404, detail="Menu benchmark tidak ditemukan")
    r = row_dict(row)

    result = {
        "benchmark_slug": r["slug"], "menu_name": r["name"], "category_label": r["category_label"],
        "image": r["image"], "measure_enabled": req.measure, "source_count": len(r["sources"]),
        "saved_to_account": bool(user),
    }

    # Vision AI only runs when a real photo is attached (balanced AI usage).
    if req.image_base64:
        result["vision_note"] = await analyze_food_image(req.image_base64)
    else:
        result["vision_note"] = f"Mode beta: menggunakan benchmark {r['name']}. Ambil foto dari kamera untuk analisis AI."

    # Spice meter (pure computation — no AI) only when the measure toggle is on.
    if req.measure:
        result["spices"] = with_pct(r["spices"])

    result["insight"], _ = await get_or_create_insight(db, r)

    await db.execute(text(
        "insert into scans(user_id,benchmark_slug,measure,had_image,result) "
        "values(cast(:uid as uuid),:slug,:measure,:had_image,cast(:result as jsonb))"
    ), {"uid": user["id"] if user else None, "slug": r["slug"], "measure": req.measure,
        "had_image": bool(req.image_base64), "result": json.dumps({**result, "mode": "benchmark"})})
    await db.commit()
    if user:
        result["stats"] = await user_stats(db, user["id"])
    return result


@api_router.get("/stats")
async def stats(user=Depends(optional_user), db=Depends(get_db)):
    return {"authenticated": bool(user), **(await user_stats(db, user["id"] if user else None))}


async def _log_scan(db, user, benchmark_slug, dish_name: str, had_image: bool, result: dict = None):
    await db.execute(text(
        "insert into scans(user_id,benchmark_slug,dish_name,measure,had_image,result) "
        "values(cast(:uid as uuid),:slug,:dish,:measure,:had_image,cast(:result as jsonb))"
    ), {"uid": user["id"] if user else None, "slug": benchmark_slug, "dish": dish_name,
        "measure": True, "had_image": had_image,
        "result": json.dumps(result) if result else None})
    await db.commit()


def _norm_dish(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


async def get_scan_cache(db, dish: str) -> Optional[dict]:
    key = _norm_dish(dish)
    if not key:
        return None
    try:
        row = (await db.execute(text(
            "select payload from scan_cache where dish_key=:k "
            "and updated_at > now() - make_interval(days => :days)"
        ), {"k": key, "days": SCAN_CACHE_TTL_DAYS})).first()
        if not row:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    except Exception as e:
        logger.warning(f"scan cache read failed: {e}")
        return None


async def set_scan_cache(db, dish: str, payload: dict):
    key = _norm_dish(dish)
    if not key:
        return
    try:
        await db.execute(text(
            "insert into scan_cache(dish_key,dish,payload,updated_at) "
            "values(:k,:dish,cast(:p as jsonb),now()) "
            "on conflict (dish_key) do update set dish=excluded.dish, payload=excluded.payload, updated_at=now()"
        ), {"k": key, "dish": dish, "p": json.dumps(payload)})
        await db.commit()
    except Exception as e:
        logger.warning(f"scan cache write failed: {e}")


async def scan_ai_fallback(db, user, had_image: bool, dish: str = "", confidence: str = "rendah",
                           vision_note: str = "", identified: bool = False, reason: str = "") -> dict:
    """Jatuh ke menu benchmark lokal terdekat agar hasil tidak pernah kosong."""
    row = None
    if dish:
        row = (await db.execute(text(f"select {RECIPE_COLS} from recipes where name ilike :q limit 1"),
                                {"q": f"%{dish}%"})).first()
    if not row:
        row = (await db.execute(text(f"select {RECIPE_COLS} from recipes order by sort_order limit 1"))).first()
    r = row_dict(row)
    insight, _ = await get_or_create_insight(db, r)
    result = {
        "mode": "fallback", "dish": dish or r["name"], "menu_name": r["name"],
        "identified": identified, "confidence": confidence,
        "vision_note": vision_note, "fallback_reason": reason or "Menampilkan data benchmark terdekat.",
        "category_label": r["category_label"], "image": r["image"], "benchmark_slug": r["slug"],
        "spices": with_pct(r["spices"]), "insight": insight,
        "sources": [{"name": s.get("name", "Sumber resep"), "title": s.get("name", ""), "url": s.get("url")}
                    for s in r["sources"] if isinstance(s, dict)],
        "source_count": len(r["sources"]), "saved_to_account": bool(user),
    }
    await _log_scan(db, user, r["slug"], dish or r["name"], had_image, result=result)
    if user:
        result["stats"] = await user_stats(db, user["id"])
    return result


@api_router.post("/scan/ai")
async def scan_ai(req: AiScanRequest, user=Depends(optional_user), db=Depends(get_db)):
    """Foto → kenali makanan → cari resep di web → rata-ratakan bumbu → sebutkan sumber."""
    had_image = bool(req.image_base64)
    dish = req.dish_name.strip()
    identified, confidence, vision_note = bool(dish), ("tinggi" if dish else "sedang"), ""

    if req.image_base64 and not dish:
        info = await identify_food_name(req.image_base64)
        dish, confidence, vision_note = info["name"], info["confidence"], info["note"]
        identified = bool(dish)

    if not dish:
        return await scan_ai_fallback(db, user, had_image, confidence="rendah", vision_note=vision_note,
                                      reason="Makanan belum bisa dikenali. Coba foto lebih jelas atau ketik nama makanannya.")

    # Cache: makanan yang sama tidak perlu panggil Tavily+Gemini lagi (hemat kuota gratis + instan).
    cached = await get_scan_cache(db, dish)
    if cached:
        result = {
            "mode": "web", "cached": True, "dish": cached["dish"], "menu_name": cached["dish"],
            "identified": identified, "confidence": confidence, "vision_note": vision_note,
            "category_label": "Hasil pencarian web", "image": None,
            "spices": cached["spices"], "insight": cached["insight"],
            "nutrition": cached.get("nutrition"),
            "sources": cached["sources"], "source_count": cached["source_count"],
            "saved_to_account": bool(user),
        }
        await _log_scan(db, user, None, dish, had_image, result=result)
        if user:
            result["stats"] = await user_stats(db, user["id"])
        return result

    sources = await tavily_recipe_search(dish, SCAN_MAX_SOURCES)
    extracted = await ai_extract_average(dish, sources) if sources else None

    if not extracted:
        return await scan_ai_fallback(db, user, had_image, dish=dish, confidence=confidence,
                                      vision_note=vision_note, identified=identified,
                                      reason="Belum menemukan cukup data resep online untuk hidangan ini.")

    payload = {
        "dish": extracted["dish"], "spices": with_pct(extracted["spices"]),
        "insight": extracted["insight"], "nutrition": extracted.get("nutrition"),
        "sources": [{"name": s["name"], "title": s["title"], "url": s["url"]} for s in sources],
        "source_count": len(sources),
    }
    await set_scan_cache(db, dish, payload)
    result = {
        "mode": "web", "cached": False, "menu_name": payload["dish"],
        "identified": identified, "confidence": confidence, "vision_note": vision_note,
        "category_label": "Hasil pencarian web", "image": None, "saved_to_account": bool(user),
        **payload,
    }
    await _log_scan(db, user, None, dish, had_image, result=result)
    if user:
        result["stats"] = await user_stats(db, user["id"])
    return result


# ----------------------------- Account endpoints (auth required) -----------------------------
async def profile_countries(db, user_id: str) -> dict:
    row = (await db.execute(text(
        "select current_country, origin_country from profiles where user_id=cast(:uid as uuid)"), {"uid": user_id})).first()
    return {"current_country": (row and row[0]) or "", "origin_country": (row and row[1]) or ""}


@api_router.get("/me")
async def me(user=Depends(require_user), db=Depends(get_db)):
    await upsert_profile(db, user)
    return {"user": {**user, **(await profile_countries(db, user["id"]))},
            "stats": await user_stats(db, user["id"]), "favorites": await favorite_slugs(db, user["id"]),
            "ai_favorites": await ai_favorites(db, user["id"]),
            "scan_favorites": await scan_favorites_list(db, user["id"])}


@api_router.put("/me/countries")
async def set_countries(req: CountriesRequest, user=Depends(require_user), db=Depends(get_db)):
    await upsert_profile(db, user)
    await db.execute(text(
        "update profiles set current_country=:cur, origin_country=:org where user_id=cast(:uid as uuid)"
    ), {"cur": req.current_country.strip() or None, "org": req.origin_country.strip() or None, "uid": user["id"]})
    await db.commit()
    return await profile_countries(db, user["id"])


@api_router.get("/favorites")
async def list_favorites(user=Depends(require_user), db=Depends(get_db)):
    slugs = await favorite_slugs(db, user["id"])
    recs = {r["slug"]: r for r in await fetch_recipes(db, slugs=slugs)}
    return [recipe_card(recs[s]) for s in slugs if s in recs]


@api_router.put("/favorites/{slug}")
async def add_favorite(slug: str, user=Depends(require_user), db=Depends(get_db)):
    await fetch_recipe(db, slug)
    await db.execute(text(
        "insert into favorites(user_id,slug) values(cast(:uid as uuid),:slug) on conflict do nothing"),
        {"uid": user["id"], "slug": slug})
    await db.commit()
    return {"slug": slug, "favorite": True, "favorites": await favorite_slugs(db, user["id"])}


@api_router.delete("/favorites/{slug}")
async def remove_favorite(slug: str, user=Depends(require_user), db=Depends(get_db)):
    await db.execute(text("delete from favorites where user_id=cast(:uid as uuid) and slug=:slug"),
                     {"uid": user["id"], "slug": slug})
    await db.commit()
    return {"slug": slug, "favorite": False, "favorites": await favorite_slugs(db, user["id"])}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    try:
        await init_db()
        logger.info("NutriVane API ready (Postgres)")
    except Exception as e:
        logger.error(f"DB init gagal: {e}")


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()
