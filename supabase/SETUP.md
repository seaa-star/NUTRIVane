# NutriVane — Panduan Setup Supabase + Vercel

## 1. Buat project Supabase
1. Buka https://supabase.com/dashboard → **New project**. Simpan **database password**.
2. **SQL Editor** → jalankan `supabase/schema.sql`, lalu `supabase/policies.sql`.
   (Backend juga otomatis membuat tabel & mengisi dataset menu saat pertama kali start, jadi `schema.sql` opsional — `policies.sql` tetap WAJIB dijalankan manual.)
3. **Authentication → Providers → Google** → aktifkan. Isi Client ID & Secret dari Google Cloud Console
   (OAuth Web client, *Authorized redirect URI* = `https://<PROJECT_REF>.supabase.co/auth/v1/callback`).
4. **Authentication → URL Configuration** → tambahkan Redirect URLs:
   - `http://localhost:3000/auth/callback`
   - `https://<DOMAIN-VERCEL>.vercel.app/auth/callback`
5. Ambil kredensial:
   - **Project Settings → API**: `Project URL` dan **Publishable key** (`sb_publishable_...`) → untuk frontend.
   - **Connect → Database**: connection string (pakai *Session pooler* jika host hanya IPv4) → untuk backend `DATABASE_URL`.

## 2. Environment variables

### Frontend (Vercel → Settings → Environment Variables)
```
REACT_APP_BACKEND_URL=https://<domain-backend-fastapi>
REACT_APP_SUPABASE_URL=https://<PROJECT_REF>.supabase.co
REACT_APP_SUPABASE_PUBLISHABLE_KEY=sb_publishable_xxx
```
Jika dua variabel Supabase kosong, app berjalan dalam **mode tamu** (login Google nonaktif).

### Backend (host FastAPI)
```
DATABASE_URL=postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres?sslmode=require
SUPABASE_URL=https://<PROJECT_REF>.supabase.co
SUPABASE_JWT_MODE=jwks            # verifikasi token lewat JWKS (direkomendasikan)
# SUPABASE_JWT_MODE=legacy + SUPABASE_JWT_SECRET=... hanya jika project masih memakai JWT secret lama
CORS_ORIGINS=https://<DOMAIN-VERCEL>.vercel.app
APP_TIMEZONE=Asia/Jakarta
EMERGENT_LLM_KEY=...              # AI insight & analisis foto (Gemini via Emergent)
INSIGHT_MODEL_PROVIDER=gemini
INSIGHT_MODEL_NAME=gemini-3-flash-preview
VISION_MODEL_PROVIDER=gemini
VISION_MODEL_NAME=gemini-3.1-pro-preview
```

## 3. Deploy
- **Frontend**: import repo ke Vercel, *Root Directory* = `frontend`, framework Create React App. `frontend/vercel.json` sudah berisi rewrite SPA.
- **Backend**: deploy folder `backend` ke host Python (Railway/Render/Fly) atau Vercel Python (`backend/vercel.json` tersedia).
  Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`.
- Setelah deploy, isi `REACT_APP_BACKEND_URL` dengan domain backend lalu **redeploy** frontend.

## 4. Cara kerja auth
Frontend login lewat `supabase.auth.signInWithOAuth({ provider: "google" })` → Supabase mengembalikan session →
setiap request ke FastAPI membawa `Authorization: Bearer <access_token>` → backend memverifikasi JWT (JWKS)
dan selalu memfilter data dengan `user_id` dari token. Tabel per-pengguna: `profiles`, `scans`, `favorites`, `mood_logs`.

## 4b. Fitur "Your Mood" AI (update)
- Endpoint `POST /api/mood/recommend` (tamu & login) → Gemini (`INSIGHT_MODEL_NAME`) via `EMERGENT_LLM_KEY`.
  Input: `mood_key`, `story` (cerita hari, opsional), `current_country`, `origin_country`.
- Kolom baru `profiles.current_country` & `profiles.origin_country` + tabel `mood_logs` dibuat otomatis oleh backend
  saat start (idempotent). Jika ingin manual: jalankan ulang `schema.sql`, lalu bagian `mood_logs` di `policies.sql`.
- Negara tersimpan ke profil pengguna yang login, lalu terisi otomatis di kunjungan berikutnya.

## 5. Uji lokal tanpa Supabase (dev)
Backend `.env` memakai `SUPABASE_JWT_MODE=legacy` + secret dev, sehingga token uji bisa dibuat:
```
python backend/scripts/dev_token.py            # cetak JWT uji (user Asha)
```
Di browser (hanya saat Supabase belum dikonfigurasi): `localStorage.setItem("nv_dev_token", "<token>")` lalu reload.
