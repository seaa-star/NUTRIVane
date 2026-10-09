import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, LogIn, ArrowRight } from "lucide-react";
import { SectionHead } from "@/components/common";
import { getMoodWeekly } from "@/lib/api";
import { HOME } from "@/constants/testIds";

function Bar({ d, max }) {
  const pct = d.count ? Math.max(18, Math.round((d.count / max) * 100)) : 0;
  return (
    <div className="flex flex-col items-center gap-1.5 flex-1 min-w-0" data-testid={HOME.moodChartBar(d.date)}>
      <span className="text-base leading-none h-5" aria-label={d.dominant?.label || "kosong"}>{d.dominant?.emoji || ""}</span>
      <div className="w-full h-24 flex items-end rounded-xl" style={{ background: "var(--nv-bg)" }}>
        <div className="w-full rounded-xl transition-[height] duration-700"
          style={{ height: `${pct}%`, background: d.is_today ? "var(--nv-accent)" : "var(--nv-green)", opacity: d.count ? 1 : 0 }} />
      </div>
      <span className="text-[0.62rem] font-bold uppercase tracking-wider" style={{ color: d.is_today ? "var(--nv-accent)" : "var(--nv-muted)" }}>{d.label}</span>
    </div>
  );
}

export function MoodWeekChart({ userId }) {
  const [data, setData] = useState(null);
  useEffect(() => { getMoodWeekly().then(setData).catch(() => setData(null)); }, [userId]);
  if (!data) return null;

  const max = Math.max(1, ...data.days.map((d) => d.count));
  return (
    <section className="nv-rise" style={{ animationDelay: "90ms" }} data-testid={HOME.moodChart}>
      <SectionHead eyebrow="7 hari terakhir" title="Grafik mood mingguan"
        action={<Link to="/mood" data-testid={HOME.moodChartCta} className="text-xs font-bold" style={{ color: "var(--nv-accent)" }}>check-in</Link>} />
      <div className="nv-card p-5">
        {data.authenticated && data.total > 0 ? (
          <>
            <div className="flex items-center justify-between gap-3 mb-4" data-testid={HOME.moodChartTop}>
              <div>
                <p className="text-xs" style={{ color: "var(--nv-muted)" }}>Mood dominan</p>
                <p className="font-display text-lg font-semibold leading-tight" style={{ color: "var(--nv-green-deep)" }}>
                  {data.top.emoji} {data.top.label}
                </p>
              </div>
              <div className="text-right">
                <p className="font-display text-2xl font-bold" style={{ color: "var(--nv-green-deep)" }}>{data.active_days}<span className="text-sm font-semibold" style={{ color: "var(--nv-muted)" }}>/7</span></p>
                <p className="text-[0.68rem]" style={{ color: "var(--nv-muted)" }}>hari check-in · {data.total} kali</p>
              </div>
            </div>
            <div className="flex gap-2">{data.days.map((d) => <Bar key={d.date} d={d} max={max} />)}</div>
          </>
        ) : (
          <div className="flex items-center gap-3" data-testid={data.authenticated ? HOME.moodChartEmpty : HOME.moodChartGuest}>
            <span className="grid place-items-center w-11 h-11 rounded-2xl shrink-0" style={{ background: "var(--nv-green-soft)" }}>
              {data.authenticated ? <Sparkles size={18} color="var(--nv-green)" /> : <LogIn size={18} color="var(--nv-green)" />}
            </span>
            <div className="flex-1 min-w-0">
              <p className="font-bold text-sm" style={{ color: "var(--nv-green-deep)" }}>
                {data.authenticated ? "Belum ada check-in minggu ini" : "Masuk untuk melihat grafik mood"}
              </p>
              <p className="text-xs leading-snug" style={{ color: "var(--nv-muted)" }}>
                {data.authenticated ? "Pilih mood & minta rekomendasi AI, grafiknya muncul di sini." : "Riwayat mood 7 hari tersimpan per akun."}
              </p>
            </div>
            <Link to={data.authenticated ? "/mood" : "/login"} aria-label="Lanjut"><ArrowRight size={18} color="var(--nv-green)" /></Link>
          </div>
        )}
      </div>
    </section>
  );
}
