import { Link } from "react-router-dom";
import { Heart, ChevronRight, X, Flame } from "lucide-react";
import { SectionHead } from "@/components/common";
import { useAuth } from "@/context/AuthContext";
import { PROFILE } from "@/constants/testIds";

export function ScanFavorites() {
  const { scanFavorites, toggleScanFavorite } = useAuth();
  const items = scanFavorites || [];

  return (
    <section className="nv-rise" style={{ animationDelay: "130ms" }}>
      <SectionHead eyebrow="Tersimpan" title="Scan favoritmu"
        action={<span className="nv-chip" style={{ fontSize: "0.62rem" }}>{items.length} hasil</span>} />
      {items.length === 0 ? (
        <div className="nv-card p-6 text-center" data-testid={PROFILE.scanFavEmpty}>
          <Heart size={22} className="mx-auto" color="var(--nv-accent)" />
          <p className="mt-2 text-sm font-semibold" style={{ color: "var(--nv-green-deep)" }}>Belum ada scan favorit</p>
          <p className="text-xs mt-1" style={{ color: "var(--nv-muted)" }}>Ketuk ikon hati pada hasil scan untuk menyimpannya di sini.</p>
          <Link to="/scan" className="nv-btn-accent mt-4 w-max mx-auto">Mulai scan</Link>
        </div>
      ) : (
        <div className="nv-card divide-y" data-testid={PROFILE.scanFavList} style={{ borderColor: "var(--nv-line)" }}>
          {items.map((f) => (
            <div key={f.id} data-testid={PROFILE.scanFavItem(f.id)} className="flex items-center gap-3 p-4">
              <Link to={`/scan?favorite=${f.id}`} className="flex items-center gap-3 min-w-0 flex-1">
                <span className="grid place-items-center w-11 h-11 rounded-2xl shrink-0" style={{ background: "var(--nv-accent-soft)" }}>
                  <Flame size={18} color="var(--nv-accent)" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="font-display text-sm font-semibold leading-tight truncate" style={{ color: "var(--nv-green-deep)" }}>{f.dish}</p>
                  <p className="text-xs mt-0.5 truncate" style={{ color: "var(--nv-muted)" }}>
                    {f.spice_count > 0 && `${f.spice_count} bumbu`}{f.source_count > 0 && ` · ${f.source_count} sumber`}
                  </p>
                </div>
                <ChevronRight size={16} color="var(--nv-muted)" className="shrink-0" />
              </Link>
              <button onClick={() => toggleScanFavorite(f.dish)} data-testid={PROFILE.scanFavRemove(f.id)}
                aria-label="Hapus dari favorit" className="grid place-items-center w-8 h-8 rounded-full shrink-0"
                style={{ background: "var(--nv-bg)" }}>
                <X size={15} color="var(--nv-muted)" />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
