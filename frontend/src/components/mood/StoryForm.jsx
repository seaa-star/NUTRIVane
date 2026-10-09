import { MapPin, Home, ArrowLeftRight, Wand2, Loader2 } from "lucide-react";
import { COUNTRIES } from "@/constants/countries";
import { MOOD } from "@/constants/testIds";

const inputStyle = { background: "var(--nv-bg)", border: "1px solid var(--nv-line)", color: "var(--nv-ink)" };

function CountryField({ icon: Icon, label, value, onChange, tid, placeholder }) {
  return (
    <label className="block">
      <span className="flex items-center gap-1.5 text-[0.7rem] font-bold uppercase tracking-wider mb-1.5" style={{ color: "var(--nv-muted)" }}>
        <Icon size={12} /> {label}
      </span>
      <input list="nv-countries" value={value} onChange={(e) => onChange(e.target.value)} data-testid={tid}
        placeholder={placeholder} autoComplete="off" maxLength={60}
        className="w-full rounded-2xl px-3.5 py-2.5 text-sm outline-none focus:ring-2" style={inputStyle} />
    </label>
  );
}

export function StoryForm({ story, setStory, current, setCurrent, origin, setOrigin, onSubmit, loading, moodLabel }) {
  return (
    <form className="nv-card p-5 space-y-4 nv-rise" style={{ animationDelay: "60ms" }}
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <div>
        <p className="nv-eyebrow mb-1">Cerita harimu</p>
        <h2 className="font-display text-xl font-semibold" style={{ color: "var(--nv-green-deep)" }}>
          Apa yang kamu rasakan hari ini?
        </h2>
        <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--nv-muted)" }}>
          Opsional. Ceritakan singkat — AI NutriVane akan memilihkan makanan & minuman yang pas dengan mood <b>{moodLabel?.toLowerCase()}</b>mu.
        </p>
      </div>

      <textarea value={story} onChange={(e) => setStory(e.target.value)} data-testid={MOOD.storyInput} maxLength={1200} rows={3}
        placeholder="Contoh: Seharian meeting, kepala agak pusing, pengen yang hangat tapi nggak berat…"
        className="w-full rounded-2xl px-3.5 py-3 text-sm leading-relaxed outline-none resize-none focus:ring-2" style={inputStyle} />

      <div className="grid grid-cols-[1fr_auto_1fr] items-end gap-2">
        <CountryField icon={MapPin} label="Negara saat ini" value={current} onChange={setCurrent} tid={MOOD.currentCountry} placeholder="Indonesia" />
        <button type="button" data-testid={MOOD.swapCountries} aria-label="Tukar negara"
          onClick={() => { setCurrent(origin); setOrigin(current); }}
          className="grid place-items-center w-9 h-9 mb-0.5 rounded-full transition-transform active:rotate-180"
          style={{ background: "var(--nv-green-soft)", color: "var(--nv-green)" }}>
          <ArrowLeftRight size={14} />
        </button>
        <CountryField icon={Home} label="Negara asal" value={origin} onChange={setOrigin} tid={MOOD.originCountry} placeholder="Indonesia" />
      </div>
      <datalist id="nv-countries">{COUNTRIES.map((c) => <option key={c} value={c} />)}</datalist>

      <button type="submit" disabled={loading} data-testid={MOOD.askAiBtn} className="nv-btn-accent w-full disabled:opacity-70">
        {loading ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
        {loading ? "Meracik rekomendasi…" : "Minta rekomendasi AI"}
      </button>
    </form>
  );
}
