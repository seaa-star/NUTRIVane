import { Link } from "react-router-dom";
import { Utensils, CupSoda, X, Sparkles } from "lucide-react";
import { SectionHead } from "@/components/common";
import { useAuth } from "@/context/AuthContext";
import { PROFILE } from "@/constants/testIds";

const TAG = { lokal: "Lokal", asal: "Rasa rumah", umum: "Umum" };

export function AiFavorites() {
  const { aiFavorites, toggleAiFavorite } = useAuth();
  return (
    <section className="nv-rise" style={{ animationDelay: "135ms" }}>
      <SectionHead eyebrow="Dari AI" title="Saran AI tersimpan"
        action={<span className="nv-chip" style={{ fontSize: "0.62rem" }}>{aiFavorites.length} saran</span>} />
      {aiFavorites.length === 0 ? (
        <div className="nv-card p-5 flex items-center gap-3" data-testid={PROFILE.aiFavEmpty}>
          <span className="grid place-items-center w-10 h-10 rounded-2xl shrink-0" style={{ background: "var(--nv-accent-soft)" }}>
            <Sparkles size={16} color="var(--nv-accent)" />
          </span>
          <p className="text-xs leading-snug" style={{ color: "var(--nv-muted)" }}>
            Ketuk ikon hati pada saran AI di halaman <Link to="/mood" className="font-bold" style={{ color: "var(--nv-accent)" }}>Mood</Link> untuk menyimpannya — termasuk menu yang belum ada di katalog resep.
          </p>
        </div>
      ) : (
        <div className="space-y-2.5" data-testid={PROFILE.aiFavList}>
          {aiFavorites.map((f) => {
            const Icon = f.kind === "minuman" ? CupSoda : Utensils;
            return (
              <div key={f.id} data-testid={PROFILE.aiFavItem(f.id)} className="nv-card p-3.5 flex items-start gap-3">
                <span className="grid place-items-center w-10 h-10 rounded-2xl shrink-0" style={{ background: "var(--nv-green-soft)", color: "var(--nv-green)" }}><Icon size={16} /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <p className="font-display text-sm font-semibold leading-tight" style={{ color: "var(--nv-green-deep)" }}>{f.name}</p>
                    <span className="rounded-full px-2 py-0.5 text-[0.58rem] font-bold uppercase tracking-wider" style={{ background: "var(--nv-bg)", color: "var(--nv-muted)" }}>{TAG[f.origin_tag] || "Umum"}</span>
                  </div>
                  {f.why && <p className="text-xs mt-1 leading-snug" style={{ color: "var(--nv-muted)" }}>{f.why}</p>}
                </div>
                <button onClick={() => toggleAiFavorite(f)} data-testid={PROFILE.aiFavRemove(f.id)} aria-label="Hapus saran"
                  className="grid place-items-center w-8 h-8 rounded-full shrink-0 transition-colors hover:bg-[var(--nv-accent-soft)]" style={{ color: "var(--nv-muted)" }}>
                  <X size={14} />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
