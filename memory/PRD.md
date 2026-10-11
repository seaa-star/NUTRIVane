# NutriVane — PRD

## Problem statement
Rebuild the NutriVane Indonesian recipe/spice (bumbu) beta app from scratch, keeping the SAME
features as the live app but redesigning the UI to match the user's Figma (deep green, rounded
"bubble" cards, 3D-emoji moods, clean margins/alignment). Measuring-spice is merged into Scan as an
optional toggle. Each menu aggregates ~5-10 recipe sources to show AVERAGE spice amounts. Balanced
AI usage. Ready for ~100 users.

## Stack
React 19 + CRA (mobile-first shell, max-width ~460px, fixed bottom nav) · FastAPI · MongoDB (motor).
AI via Emergent Universal Key (emergentintegrations).

## Design (from user's Figma)
Palette: bg #f1f5ec, green #2f5d34 / deep #1f3f23, soft #e3efdc, accent terracotta #e3824f.
Fonts: Plus Jakarta Sans (UI) + Fraunces (display). Rounded cards, pill tabs, deep-green bottom nav.

## AI (balanced)
- Insight text: Gemini 3 Flash (gemini-3-flash-preview), cached in Mongo `insights`.
- Scan photo analysis: Gemini 3.1 Pro (gemini-3.1-pro-preview) — ONLY when a real photo is uploaded.
- Spice averaging, mood matching, recommendations: pure computation, NO AI.

## Implemented (2026-10-08)
- Pages: Beranda (home), Scan, Resep (list), Resep detail, Mood.
- Scan: benchmark menu picker + "Ukur & Analisis Bumbu" toggle (optional) + optional photo upload
  → result card with AI insight + spice meter (when toggle on). Scans logged to Mongo.
- Recipe detail: Spice Meter (avg per spice with % bars), AI "Insight rasa", source list.
- Dataset: 3 benchmark menus (Rendang, Sayur sop ayam, Nasi goreng) from Bumbu Nutrivane docx,
  each with averaged spices + recipe sources (data.py).
- No authentication (single demo profile "Asha") — matches original app.
- Tested: 21/21 backend pytest pass; frontend 100% (bottom nav, toggle, spice meter, AI, filters).

## Implemented (later sessions)
- Migrated to PostgreSQL/Supabase (SQLAlchemy async + asyncpg), Google Login via Supabase (JWKS verify in
  backend), guest mode, profile page, favorites, per-user streak/plate stats. Vercel deploy (frontend+backend).
- Local dev: PostgreSQL 15 installed manually (not supervisor-managed: `service postgresql start`),
  DB `nutrivane`, backend `.env` uses `SUPABASE_JWT_MODE=legacy` + `scripts/dev_token.py` for test tokens.

## Implemented (2026-10-09) — "Your Mood" AI
- `POST /api/mood/recommend`: Gemini 3 Flash (Emergent key) → JSON {headline, summary, items[name,kind,why,
  slug→recipe card,origin_tag lokal/asal/umum], tip}; inputs mood_key + story + current_country + origin_country.
  Fallback = curated mood recipes if AI fails. Every call logged in `mood_logs` (user_id nullable).
- Countries saved to `profiles.current_country/origin_country` for logged-in users; `/api/me` returns them;
  `PUT /api/me/countries`. Frontend prefills from profile.
- MoodPage: MoodSelector + StoryForm (textarea, country datalist inputs, swap) + AiResult (items link to recipes).
- Tested: testing agent iteration_2 — 12/12 backend, all frontend flows pass.

## Implemented (2026-10-09) — Grafik mood mingguan + Bagikan WhatsApp
- `GET /api/mood/weekly` (optional auth): 7 hari (Asia/Jakarta) dari `mood_logs` → per hari count, moods, dominant;
  total, active_days, top. Guest → authenticated:false, kosong.
- Beranda: `components/home/MoodWeekChart.jsx` (bar chart 7 hari, emoji dominan di atas bar, hari ini terracotta;
  state tamu → ajak login, state kosong → ajak check-in).
- AiResult: tombol "Bagikan ke WhatsApp" (wa.me/?text=...) berisi headline, ringkasan, daftar item, tip, link /mood.
- Tested: testing agent iteration_3 — 8/8 backend, semua alur frontend lolos.

## Implemented (2026-10-11) — AI Smart Scan (web recipe search)
- `POST /api/scan/ai` {image_base64?, dish_name?}: (1) Gemini Vision identifies dish from photo;
  (2) Tavily web search (TAVILY_API_KEY, SCAN_MAX_SOURCES=5) finds recipe pages + source URLs;
  (3) Gemini Flash extracts & averages spices across sources → {spices[name,avg,unit,sources],insight};
  (4) backend adds pct, logs scan, returns {mode:web|fallback, dish, spices, insight,
  sources[name,title,url], source_count}. Fallback to nearest local benchmark when dish unidentified
  or no spices (never 500).
- Schema: `scans.benchmark_slug` nullable + FK dropped (idempotent ALTERs) + new `scans.dish_name`.
- ScanPage: "Scan pintar (AI + web)" primary (photo/upload + optional dish-name input); old benchmark
  flow in collapsible "Mode benchmark". Result shows dish + confidence/mode chips + insight + spice
  meter + clickable Sumber list. New lib/api `postScanAi`.
- DEPLOY NOTE: add `TAVILY_API_KEY` to Vercel backend Environment Variables (Prod+Preview).
- Tested: backend testing agent 6/6 pass; frontend visually verified (Nasi goreng → 8 spices + 5 sources).

## Backlog / future
- P1: Riwayat mood (list `mood_logs` di profil) — detail per entri.
- P2: Expand dataset beyond 7 menus (drinks/dessert/tea exist in source doc).
- P2: Cache invalidation / dataset version in AI insight cache key.
- P2: Streaming AI response untuk mood (saat ini ~15-20s tunggu).

## Implemented (2026-10-11) — Scan history, scan favorites, nutrition focus
- Live camera (#1) already existed (CameraCapture.jsx getUserMedia + flip + upload fallback); verified.
- #4 Cache badge: scan result card shows "⚡ instan" when result.cached (backend already returned cached flag).
- #2 Scan history: scans table gained `result jsonb` (idempotent migration); _log_scan stores full snapshot.
  Endpoints GET /api/scans/history (limit<=50) + GET /api/scans/history/{id}. Profile section "Scan makananmu"
  (components/profile/ScanHistory.jsx) links to /scan?history={id} which fetches & renders the saved result.
- #3 Scan favorites: new table scan_favorites(user_id,dish,result jsonb) unique per (user, lower(dish)).
  GET/POST/DELETE /api/scan-favorites + GET /{id}. /api/me now returns scan_favorites. Heart button on scan
  result card (AuthContext.toggleScanFavorite / isScanFavorite). Profile section "Scan favoritmu"
  (components/profile/ScanFavorites.jsx) links to /scan?favorite={id}. RLS policy added in supabase/policies.sql.
- NUTRITION FOCUS: ai_extract_average now also returns a per-serving nutrition estimate
  (_parse_nutrition -> {serving, calories, protein_g, carbs_g, fat_g, fiber_g, note}); included in payload+cache.
  ScanPage shows a "Kandungan gizi" card (energi kkal + protein/karbo/lemak/serat tiles + note) above spice meter.
- Backend tested: 22/22 pass (history, favorites, nutrition, cache, regressions). Frontend NOT yet tested.
- Dev env note: container reset wipes local Postgres — recreate: pg_ctlcluster 15 main start; set postgres pwd
  'nutrivane'; createdb nutrivane; restart backend (auto-seeds + runs schema.sql). Dev token: scripts/dev_token.py.
