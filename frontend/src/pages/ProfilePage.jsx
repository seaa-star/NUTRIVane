import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Flame, Utensils, CalendarCheck, LogOut, Heart, ArrowLeft } from "lucide-react";
import Layout from "@/components/Layout";
import { RecipeCard, SectionHead } from "@/components/common";
import { MoodHistory } from "@/components/profile/MoodHistory";
import { AiFavorites } from "@/components/profile/AiFavorites";
import { useAuth } from "@/context/AuthContext";
import { getFavorites } from "@/lib/api";
import { PROFILE } from "@/constants/testIds";

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user, stats, favorites, loading, signOut } = useAuth();
  const [favItems, setFavItems] = useState([]);

  useEffect(() => { if (!loading && !user) navigate("/login", { replace: true }); }, [user, loading, navigate]);
  useEffect(() => { if (user) getFavorites().then(setFavItems).catch(() => setFavItems([])); }, [user, favorites]);

  if (!user) return <Layout><div className="p-5 text-sm" style={{ color: "var(--nv-muted)" }}>Memuat…</div></Layout>;

  const initial = (user.name || "?").charAt(0).toUpperCase();
  const statCards = [
    { icon: Flame, label: "hari streak", value: stats?.streak_days ?? 0, tid: PROFILE.streak, accent: true },
    { icon: Utensils, label: "piring dikenali", value: stats?.plates_recognized ?? 0, tid: PROFILE.plates },
    { icon: CalendarCheck, label: "scan minggu ini", value: stats?.weekly_delta ?? 0, tid: PROFILE.weekly },
  ];

  return (
    <Layout>
      <div className="px-5 pt-4 space-y-6" data-testid={PROFILE.page}>
        <button onClick={() => navigate("/")} data-testid={PROFILE.back}
          className="flex items-center gap-1.5 text-sm font-semibold" style={{ color: "var(--nv-muted)" }}>
          <ArrowLeft size={16} /> kembali ke beranda
        </button>

        <div className="rounded-3xl p-5 text-white nv-rise" style={{ background: "linear-gradient(140deg, var(--nv-green-mid), var(--nv-green-deep))" }}>
          <div className="flex items-center gap-4">
            {user.avatar_url
              ? <img src={user.avatar_url} alt={user.name} className="w-14 h-14 rounded-full object-cover border-2 border-white/40" referrerPolicy="no-referrer" />
              : <span className="grid place-items-center w-14 h-14 rounded-full font-display text-2xl font-bold" style={{ background: "var(--nv-accent)" }}>{initial}</span>}
            <div className="min-w-0">
              <p className="nv-eyebrow" style={{ color: "rgba(255,255,255,0.65)" }}>Akun kamu</p>
              <h1 className="font-display text-2xl font-semibold leading-tight truncate" data-testid={PROFILE.name}>{user.name}</h1>
              <p className="text-xs text-white/70 truncate" data-testid={PROFILE.email}>{user.email}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3 nv-rise" style={{ animationDelay: "60ms" }}>
          {statCards.map(({ icon: Icon, label, value, tid, accent }) => (
            <div key={label} className="nv-card p-3.5" data-testid={tid}>
              <Icon size={16} color={accent ? "var(--nv-accent)" : "var(--nv-green)"} />
              <p className="font-display text-2xl font-bold mt-2" style={{ color: "var(--nv-green-deep)" }}>{value}</p>
              <p className="text-[0.68rem] leading-snug" style={{ color: "var(--nv-muted)" }}>{label}</p>
            </div>
          ))}
        </div>

        <section className="nv-rise" style={{ animationDelay: "120ms" }}>
          <SectionHead eyebrow="Tersimpan" title="Menu favoritmu"
            action={<span className="nv-chip" style={{ fontSize: "0.62rem" }} data-testid={PROFILE.favCount}>{favItems.length} menu</span>} />
          {favItems.length === 0 ? (
            <div className="nv-card p-6 text-center" data-testid={PROFILE.favEmpty}>
              <Heart size={22} className="mx-auto" color="var(--nv-accent)" />
              <p className="mt-2 text-sm font-semibold" style={{ color: "var(--nv-green-deep)" }}>Belum ada favorit</p>
              <p className="text-xs mt-1" style={{ color: "var(--nv-muted)" }}>Ketuk ikon hati di halaman resep untuk menyimpannya di sini.</p>
              <Link to="/recipes" className="nv-btn-accent mt-4 w-max mx-auto">Jelajahi resep</Link>
            </div>
          ) : (
            <div className="space-y-4">
              {favItems.map((r) => <RecipeCard key={r.slug} r={r} to={`/recipes/${r.slug}`} tid={PROFILE.favCard(r.slug)} />)}
            </div>
          )}
        </section>

        <AiFavorites />
        <MoodHistory />

        <button onClick={async () => { await signOut(); navigate("/login"); }} data-testid={PROFILE.logoutBtn}
          className="nv-btn-primary w-full" style={{ background: "#fff", color: "var(--nv-accent)", border: "1px solid var(--nv-line)" }}>
          <LogOut size={16} /> Keluar
        </button>
      </div>
    </Layout>
  );
}
