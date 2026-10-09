import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Flame, Check, Camera, LogIn } from "lucide-react";
import Layout from "@/components/Layout";
import { RecipeCard, SectionHead } from "@/components/common";
import { MoodWeekChart } from "@/components/home/MoodWeekChart";
import { getHome } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { HOME } from "@/constants/testIds";

export default function HomePage() {
  const [data, setData] = useState(null);
  const { user, stats } = useAuth();

  useEffect(() => {
    getHome().then(setData).catch(console.error);
  }, [user?.id]);

  if (!data) return <Layout><div className="p-5 text-sm" style={{ color: "var(--nv-muted)" }}>Memuat…</div></Layout>;

  const streak = stats?.streak_days ?? data.streak_days;
  const plates = stats?.plates_recognized ?? data.plates_recognized;
  const weekly = stats?.weekly_delta ?? data.weekly_delta;

  return (
    <Layout>
      <div className="px-5 pt-4 space-y-7">
        {/* hero */}
        <section className="nv-rise">
          <div className="flex items-center justify-between gap-3 mb-2">
            <p className="nv-eyebrow">{data.date} · {data.part_of_day}</p>
            <div className="shrink-0 flex items-center gap-2 pl-3 pr-3.5 py-1.5 rounded-full" data-testid={HOME.streakChip} style={{ background: "var(--nv-accent-soft)" }}>
              <Flame size={14} color="var(--nv-accent)" />
              <span className="text-xs font-bold" style={{ color: "var(--nv-accent)" }}>{streak} hari</span>
              <span className="text-[0.62rem] font-semibold" style={{ color: "var(--nv-muted)" }}>streak</span>
            </div>
          </div>
          <h1 className="font-display text-[1.75rem] leading-[1.15] font-semibold" style={{ color: "var(--nv-green-deep)" }}>
            {data.headline}
          </h1>
          <p className="mt-2.5 text-sm leading-relaxed" style={{ color: "var(--nv-muted)" }}>{data.subhead}</p>
        </section>

        {!data.authenticated && (
          <Link to="/login" data-testid={HOME.loginBanner}
            className="nv-card p-4 flex items-center justify-between gap-3 nv-rise" style={{ background: "var(--nv-green-soft)" }}>
            <div className="flex items-center gap-3">
              <span className="grid place-items-center w-10 h-10 rounded-xl shrink-0" style={{ background: "#fff" }}>
                <LogIn size={18} color="var(--nv-green)" />
              </span>
              <div>
                <p className="font-bold text-sm" style={{ color: "var(--nv-green-deep)" }}>Simpan streak &amp; piringmu</p>
                <p className="text-xs leading-snug" style={{ color: "var(--nv-muted)" }}>Masuk dengan Google agar progres tidak hilang.</p>
              </div>
            </div>
            <ArrowRight size={18} color="var(--nv-green)" className="shrink-0" />
          </Link>
        )}

        {/* feature insight */}
        <section className="nv-rise" style={{ animationDelay: "60ms" }}>
          <div className="rounded-3xl p-5 text-white relative overflow-hidden"
            style={{ background: "linear-gradient(140deg, var(--nv-green-mid), var(--nv-green-deep))" }}>
            <span className="nv-chip" style={{ background: "rgba(255,255,255,0.16)", color: "#fff", fontSize: "0.62rem", letterSpacing: "0.12em", textTransform: "uppercase" }}>
              {data.featured.badge}
            </span>
            <h2 className="font-display text-2xl font-semibold mt-3 leading-tight">{data.featured.title}</h2>
            <p className="mt-2 text-sm text-white/80 leading-relaxed">{data.featured.body}</p>
            <Link to={`/recipes/${data.featured.slug}`} data-testid={HOME.insightCta}
              className="nv-btn-accent mt-4 w-max">
              Lihat insight <ArrowRight size={16} />
            </Link>
          </div>

          <div className="nv-card mt-3 p-5 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="grid place-items-center w-7 h-7 rounded-full" style={{ background: "var(--nv-green-soft)" }}>
                  <Check size={15} color="var(--nv-green)" />
                </span>
                <span className="nv-chip" style={{ fontSize: "0.62rem" }}>+{weekly} minggu ini</span>
              </div>
              <p className="font-display text-3xl font-bold mt-2" data-testid={HOME.platesCount} style={{ color: "var(--nv-green-deep)" }}>{plates}</p>
              <p className="text-sm" style={{ color: "var(--nv-muted)" }}>piring sudah kamu kenali</p>
            </div>
            <Link to="/scan" data-testid={HOME.scanCta} className="flex items-center gap-1.5 text-sm font-bold" style={{ color: "var(--nv-accent)" }}>
              <Camera size={16} /> Scan baru
            </Link>
          </div>
        </section>

        <MoodWeekChart userId={user?.id} />

        {/* moods */}
        <section className="nv-rise" style={{ animationDelay: "120ms" }}>
          <SectionHead eyebrow="Sesuaikan dengan harimu" title="Kamu lagi merasa apa?"
            action={<Link to="/mood" data-testid={HOME.seeAllMoods} className="text-xs font-bold" style={{ color: "var(--nv-accent)" }}>lihat semua</Link>} />
          <div className="grid grid-cols-2 gap-3">
            {data.moods.map((m) => (
              <Link key={m.key} to={`/mood?selected=${m.key}`} data-testid={HOME.moodItem(m.key)}
                className="nv-card p-4 hover:shadow-md transition-shadow">
                <span className="text-2xl">{m.emoji}</span>
                <p className="mt-2 font-bold text-sm" style={{ color: "var(--nv-green-deep)" }}>{m.label}</p>
                <p className="text-xs mt-0.5 leading-snug" style={{ color: "var(--nv-muted)" }}>{m.subtitle}</p>
              </Link>
            ))}
          </div>
        </section>

        {/* picks */}
        <section className="nv-rise" style={{ animationDelay: "180ms" }}>
          <SectionHead eyebrow="Dari beta kitchen" title="Pilihan yang mungkin cocok"
            action={<Link to="/recipes" data-testid={HOME.seeAllPicks} className="text-xs font-bold" style={{ color: "var(--nv-accent)" }}>lihat semua</Link>} />
          <div className="space-y-4">
            {data.picks.map((r) => (
              <RecipeCard key={r.slug} r={r} to={`/recipes/${r.slug}`} tid={HOME.pickCard(r.slug)} />
            ))}
          </div>
        </section>
      </div>
    </Layout>
  );
}
