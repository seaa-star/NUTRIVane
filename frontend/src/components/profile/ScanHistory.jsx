import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ScanLine, ChevronRight, Camera, Zap, Globe } from "lucide-react";
import { SectionHead } from "@/components/common";
import { getScanHistory } from "@/lib/api";
import { PROFILE } from "@/constants/testIds";

const fmt = (iso) => new Date(iso).toLocaleString("id-ID", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export function ScanHistory() {
  const [items, setItems] = useState(null);
  useEffect(() => { getScanHistory(20).then(setItems).catch(() => setItems([])); }, []);
  if (!items) return null;

  return (
    <section className="nv-rise" style={{ animationDelay: "150ms" }}>
      <SectionHead eyebrow="Riwayat" title="Scan makananmu"
        action={<span className="nv-chip" style={{ fontSize: "0.62rem" }}>{items.length} scan</span>} />
      {items.length === 0 ? (
        <div className="nv-card p-6 text-center" data-testid={PROFILE.scanHistoryEmpty}>
          <ScanLine size={22} className="mx-auto" color="var(--nv-green)" />
          <p className="mt-2 text-sm font-semibold" style={{ color: "var(--nv-green-deep)" }}>Belum ada scan</p>
          <p className="text-xs mt-1" style={{ color: "var(--nv-muted)" }}>Foto atau ketik makananmu di halaman Scan, hasilnya tersimpan di sini.</p>
          <Link to="/scan" className="nv-btn-accent mt-4 w-max mx-auto"><Camera size={14} /> Scan sekarang</Link>
        </div>
      ) : (
        <div className="nv-card divide-y" data-testid={PROFILE.scanHistoryList} style={{ borderColor: "var(--nv-line)" }}>
          {items.map((h) => (
            <Link key={h.id} to={`/scan?history=${h.id}`} data-testid={PROFILE.scanHistoryItem(h.id)}
              className="flex items-center gap-3 p-4 transition-colors hover:bg-[var(--nv-bg)]">
              <span className="grid place-items-center w-11 h-11 rounded-2xl shrink-0" style={{ background: "var(--nv-green-soft)" }}>
                {h.had_image ? <Camera size={18} color="var(--nv-green)" /> : <Globe size={18} color="var(--nv-green)" />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[0.65rem] font-bold uppercase tracking-wider" style={{ color: "var(--nv-muted)" }}>{fmt(h.created_at)}</p>
                <p className="font-display text-sm font-semibold leading-tight mt-0.5 truncate" style={{ color: "var(--nv-green-deep)" }}>{h.dish || "Hasil scan"}</p>
                <p className="flex items-center gap-1.5 text-xs mt-0.5 truncate" style={{ color: "var(--nv-muted)" }}>
                  {h.spice_count > 0 && <span>{h.spice_count} bumbu</span>}
                  {h.source_count > 0 && <span>· {h.source_count} sumber</span>}
                  {h.cached && <span className="inline-flex items-center gap-0.5" style={{ color: "#b4791f" }}><Zap size={10} fill="#b4791f" /> instan</span>}
                </p>
              </div>
              <ChevronRight size={16} color="var(--nv-muted)" className="shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
