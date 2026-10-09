import { Link } from "react-router-dom";
import { Utensils, CupSoda, ArrowRight, Lightbulb, Sparkles, RefreshCw } from "lucide-react";
import { MOOD } from "@/constants/testIds";

const TAG = {
  lokal: { label: "Lokal", bg: "var(--nv-green-soft)", color: "var(--nv-green)" },
  asal: { label: "Rasa rumah", bg: "var(--nv-accent-soft)", color: "var(--nv-accent)" },
  umum: { label: "Umum", bg: "#eef1ea", color: "var(--nv-muted)" },
};

function Item({ it, index }) {
  const Icon = it.kind === "minuman" ? CupSoda : Utensils;
  const tag = TAG[it.origin_tag] || TAG.umum;
  const body = (
    <div className="flex gap-3 items-start">
      {it.recipe
        ? <img src={it.recipe.image} alt={it.name} className="w-14 h-14 rounded-2xl object-cover shrink-0" />
        : <span className="grid place-items-center w-14 h-14 rounded-2xl shrink-0" style={{ background: "var(--nv-green-soft)", color: "var(--nv-green)" }}><Icon size={20} /></span>}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="font-display text-base font-semibold leading-tight" style={{ color: "var(--nv-green-deep)" }}>{it.name}</h3>
          <span className="rounded-full px-2 py-0.5 text-[0.6rem] font-bold uppercase tracking-wider" style={{ background: tag.bg, color: tag.color }}>{tag.label}</span>
        </div>
        <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--nv-muted)" }}>{it.why}</p>
        {it.recipe && (
          <span className="inline-flex items-center gap-1 text-[0.7rem] font-bold mt-1.5" style={{ color: "var(--nv-accent)" }}>
            Lihat bumbu & resep <ArrowRight size={11} />
          </span>
        )}
      </div>
    </div>
  );
  const cls = "nv-card p-3.5 block nv-rise";
  const style = { animationDelay: `${index * 50}ms` };
  return it.recipe
    ? <Link to={`/recipes/${it.recipe.slug}`} data-testid={MOOD.aiItemLink(it.recipe.slug)} className={cls} style={style}><div data-testid={MOOD.aiItem(index)}>{body}</div></Link>
    : <div data-testid={MOOD.aiItem(index)} className={cls} style={style}>{body}</div>;
}

export function AiResult({ result, onRetry }) {
  return (
    <section data-testid={MOOD.aiResult} className="space-y-3">
      <div className="rounded-3xl p-5" style={{ background: "var(--nv-green-soft)" }}>
        <div className="flex items-center justify-between gap-3">
          <p className="nv-eyebrow flex items-center gap-1.5" style={{ color: "var(--nv-green)" }}>
            <Sparkles size={12} /> Rekomendasi AI {result.mood?.emoji}
          </p>
          <span data-testid={MOOD.aiSource} className="text-[0.62rem] font-bold uppercase tracking-wider" style={{ color: "var(--nv-muted)" }}>
            {result.source === "ai" ? "Gemini" : "Pilihan kurasi"}
          </span>
        </div>
        <h2 data-testid={MOOD.aiHeadline} className="font-display text-xl font-semibold mt-2 leading-tight" style={{ color: "var(--nv-green-deep)" }}>{result.headline}</h2>
        {result.summary && <p data-testid={MOOD.aiSummary} className="text-sm mt-2 leading-relaxed" style={{ color: "var(--nv-ink)" }}>{result.summary}</p>}
        {(result.current_country || result.origin_country) && (
          <p className="text-[0.7rem] mt-2" style={{ color: "var(--nv-muted)" }}>
            {result.current_country && <>Di <b>{result.current_country}</b></>}
            {result.current_country && result.origin_country && " · "}
            {result.origin_country && <>asal <b>{result.origin_country}</b></>}
          </p>
        )}
      </div>

      <div className="space-y-3">{result.items.map((it, i) => <Item key={`${it.name}-${i}`} it={it} index={i} />)}</div>

      {result.tip && (
        <div data-testid={MOOD.aiTip} className="flex gap-3 items-start rounded-2xl p-4" style={{ background: "var(--nv-accent-soft)" }}>
          <Lightbulb size={16} color="var(--nv-accent)" className="shrink-0 mt-0.5" />
          <p className="text-xs leading-relaxed" style={{ color: "var(--nv-ink)" }}>{result.tip}</p>
        </div>
      )}
      <button onClick={onRetry} data-testid={MOOD.retryBtn} className="flex items-center gap-1.5 text-xs font-bold mx-auto" style={{ color: "var(--nv-green)" }}>
        <RefreshCw size={12} /> Racik ulang
      </button>
    </section>
  );
}
