-- Jalankan HANYA di Supabase (SQL Editor) setelah schema.sql.
-- Mengaktifkan Row Level Security supaya data pengguna aman walau diakses lewat Supabase Data API.
-- Backend FastAPI terhubung sebagai pemilik DB (bypass RLS) dan SELALU memfilter user_id dari JWT terverifikasi.

alter table public.categories enable row level security;
alter table public.recipes    enable row level security;
alter table public.moods      enable row level security;
alter table public.insights   enable row level security;
alter table public.profiles   enable row level security;
alter table public.scans      enable row level security;
alter table public.favorites  enable row level security;

-- Data publik (katalog) boleh dibaca siapa saja
create policy "public read categories" on public.categories for select to anon, authenticated using (true);
create policy "public read recipes"    on public.recipes    for select to anon, authenticated using (true);
create policy "public read moods"      on public.moods      for select to anon, authenticated using (true);
create policy "public read insights"   on public.insights   for select to anon, authenticated using (true);

-- Data per pengguna: hanya pemiliknya
create policy "own profile read"   on public.profiles for select to authenticated using ((select auth.uid()) = user_id);
create policy "own profile upsert" on public.profiles for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own profile update" on public.profiles for update to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

create policy "own scans read"   on public.scans for select to authenticated using ((select auth.uid()) = user_id);
create policy "own scans insert" on public.scans for insert to authenticated with check ((select auth.uid()) = user_id);

create policy "own favorites read"   on public.favorites for select to authenticated using ((select auth.uid()) = user_id);
create policy "own favorites insert" on public.favorites for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own favorites delete" on public.favorites for delete to authenticated using ((select auth.uid()) = user_id);

-- Opsional: tautkan profil ke auth.users supaya terhapus otomatis saat akun dihapus
alter table public.profiles
  add constraint profiles_user_fk foreign key (user_id) references auth.users(id) on delete cascade;
alter table public.favorites
  add constraint favorites_user_fk foreign key (user_id) references auth.users(id) on delete cascade;

-- Mood AI (fitur "Your Mood"): log rekomendasi per pengguna (user_id null = tamu, hanya diakses backend)
alter table public.mood_logs enable row level security;
create policy "own mood logs read"   on public.mood_logs for select to authenticated using ((select auth.uid()) = user_id);
create policy "own mood logs insert" on public.mood_logs for insert to authenticated with check ((select auth.uid()) = user_id);

alter table public.ai_favorites enable row level security;
create policy "own ai favorites read"   on public.ai_favorites for select to authenticated using ((select auth.uid()) = user_id);
create policy "own ai favorites insert" on public.ai_favorites for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own ai favorites delete" on public.ai_favorites for delete to authenticated using ((select auth.uid()) = user_id);

-- Scan favorites (hasil scan web yang disimpan pengguna). Backend memakai service role
-- sehingga tetap berfungsi tanpa ini; policy ditambahkan agar konsisten bila diakses via client.
alter table public.scan_favorites enable row level security;
create policy "own scan favorites read"   on public.scan_favorites for select to authenticated using ((select auth.uid()) = user_id);
create policy "own scan favorites insert" on public.scan_favorites for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own scan favorites delete" on public.scan_favorites for delete to authenticated using ((select auth.uid()) = user_id);
