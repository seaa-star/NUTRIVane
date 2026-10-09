import { Sparkles } from "lucide-react";
import { MOOD } from "@/constants/testIds";

export function MoodSelector({ moods, selected, onSelect }) {
  const current = moods.find((m) => m.key === selected);
  return (
    <div className="rounded-3xl p-5 text-white relative overflow-hidden nv-rise"
      style={{ background: "linear-gradient(150deg, var(--nv-green-mid), var(--nv-green-deep))" }}>
      <div className="flex items-start justify-between">
        <span className="grid place-items-center w-11 h-11 rounded-2xl" style={{ background: "rgba(255,255,255,0.14)" }}>
          <Sparkles size={20} />
        </span>
        <span className="text-4xl leading-none">{current?.emoji}</span>
      </div>
      <h2 className="font-display text-xl font-semibold mt-4">{current?.question}</h2>
      <p className="text-sm text-white/75 mt-1.5">{current?.helper}</p>

      <div className="grid grid-cols-2 gap-2.5 mt-4">
        {moods.map((m) => {
          const on = m.key === selected;
          return (
            <button key={m.key} data-testid={MOOD.option(m.key)} onClick={() => onSelect(m.key)}
              className="rounded-2xl px-4 py-3 text-left transition-all flex items-center gap-2.5"
              style={{ background: on ? "#fff" : "rgba(255,255,255,0.1)", color: on ? "var(--nv-green-deep)" : "#fff" }}>
              <span className="text-xl">{m.emoji}</span>
              <span className="font-bold text-sm">{m.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
