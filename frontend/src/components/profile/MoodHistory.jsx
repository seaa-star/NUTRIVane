import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { History, ChevronRight, Sparkles } from "lucide-react";
import { SectionHead } from "@/components/common";
import { getMoodHistory } from "@/lib/api";
import { PROFILE } from "@/constants/testIds";

const fmt = (iso) => new Date(iso).toLocaleString("id-ID", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export function MoodHistory() {
  const [items, setItems] = useState(null);
  useEffect(() => { getMoodHistory().then(setItems).catch(() => setItems([])); }, []);
  if (!items) return null;

  return (
    <section className="nv-rise" style={{ animationDelay: "150ms" }}>
      <SectionHead eyebrow="Riwayat" title="Check-in mood kamu"
        action={<span className="nv-chip" style={{ fontSize: "0.62rem" }}>{items.length} kali</span>} />
      {items.length === 0 ? (
        <div className="nv-card p-6 text-center" data-testid={PROFILE.historyEmpty}>
          <History size={22} className="mx-auto" color="var(--nv-green)" />
          <p className="mt-2 text-sm font-semibold" style={{ color: "var(--nv-green-deep)" }}>Belum ada check-in</p>
          <p className="text-xs mt-1" style={{ color: "var(--nv-muted)" }}>Pilih mood & minta rekomendasi AI, riwayatnya tersimpan di sini.</p>
          <Link to="/mood" className="nv-btn-accent mt-4 w-max mx-auto"><Sparkles size={14} /> Check-in sekarang</Link>
        </div>
      ) : (
        <div className="nv-card divide-y" data-testid={PROFILE.historyList} style={{ borderColor: "var(--nv-line)" }}>
          {items.map((h) => (
            <Link key={h.id} to={`/mood?selected=${h.mood.key}&log=${h.id}`} data-testid={PROFILE.historyItem(h.id)}
              className="flex items-center gap-3 p-4 transition-colors hover:bg-[var(--nv-bg)]">
              <span className="grid place-items-center w-11 h-11 rounded-2xl text-xl shrink-0" style={{ background: "var(--nv-green-soft)" }}>{h.mood.emoji}</span>
              <div className="min-w-0 flex-1">
                <p className="text-[0.65rem] font-bold uppercase tracking-wider" style={{ color: "var(--nv-muted)" }}>{h.mood.label} · {fmt(h.created_at)}</p>
                <p className="font-display text-sm font-semibold leading-tight mt-0.5 truncate" style={{ color: "var(--nv-green-deep)" }}>{h.headline || "Rekomendasi tersimpan"}</p>
                <p className="text-xs mt-0.5 truncate" style={{ color: "var(--nv-muted)" }}>{h.item_names.join(" · ")}</p>
              </div>
              <ChevronRight size={16} color="var(--nv-muted)" className="shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
