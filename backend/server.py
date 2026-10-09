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


class MoodRecommendRequest(BaseModel):
    mood_key: str
    story: str = Field(default="", max_length=1200)
    current_country: str = Field(default="", max_length=60)
    origin_country: str = Field(default="", max_length=60)


class CountriesRequest(BaseModel):
    current_country: str = Field(default="", max_length=60)
    origin_country: str = Field(default="", max_length=60)


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
            "current_country": current_country, "origin_country": origin_country, "saved_to_account": bool(user)}


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
        "insert into scans(user_id,benchmark_slug,measure,had_image) "
        "values(cast(:uid as uuid),:slug,:measure,:had_image)"
    ), {"uid": user["id"] if user else None, "slug": r["slug"], "measure": req.measure, "had_image": bool(req.image_base64)})
    await db.commit()
    if user:
        result["stats"] = await user_stats(db, user["id"])
    return result


@api_router.get("/stats")
async def stats(user=Depends(optional_user), db=Depends(get_db)):
    return {"authenticated": bool(user), **(await user_stats(db, user["id"] if user else None))}


# ----------------------------- Account endpoints (auth required) -----------------------------
async def profile_countries(db, user_id: str) -> dict:
    row = (await db.execute(text(
        "select current_country, origin_country from profiles where user_id=cast(:uid as uuid)"), {"uid": user_id})).first()
    return {"current_country": (row and row[0]) or "", "origin_country": (row and row[1]) or ""}


@api_router.get("/me")
async def me(user=Depends(require_user), db=Depends(get_db)):
    await upsert_profile(db, user)
    return {"user": {**user, **(await profile_countries(db, user["id"]))},
            "stats": await user_stats(db, user["id"]), "favorites": await favorite_slugs(db, user["id"])}


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
