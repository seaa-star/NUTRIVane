import { useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, X, ArrowRight } from "lucide-react";
import { HOME } from "@/constants/testIds";

export function CheckinReminder({ weekly, partOfDay }) {
  const today = weekly?.days?.[weekly.days.length - 1];
  const [dismissed, setDismissed] = useState(() => localStorage.getItem("nv_reminder_dismissed"));
  if (!today || dismissed === today.date) return null;

  const done = weekly.authenticated ? today.count > 0 : localStorage.getItem("nv_mood_last_checkin") === today.date;
  if (done) return null;

  return (
    <div data-testid={HOME.reminder} className="nv-card p-4 flex items-center gap-3 nv-rise" style={{ background: "var(--nv-accent-soft)", border: "none" }}>
      <span className="grid place-items-center w-10 h-10 rounded-xl shrink-0" style={{ background: "#fff" }}>
        <Sparkles size={18} color="var(--nv-accent)" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-bold text-sm" style={{ color: "var(--nv-green-deep)" }}>Belum check-in mood hari ini</p>
        <p className="text-xs leading-snug" style={{ color: "var(--nv-muted)" }}>Lagi merasa apa {partOfDay} ini? 10 detik saja, AI bantu pilihkan menu.</p>
      </div>
      <Link to="/mood" data-testid={HOME.reminderCta} aria-label="Check-in mood"
        className="grid place-items-center w-9 h-9 rounded-full shrink-0 text-white" style={{ background: "var(--nv-accent)" }}>
        <ArrowRight size={16} />
      </Link>
      <button onClick={() => { localStorage.setItem("nv_reminder_dismissed", today.date); setDismissed(today.date); }}
        data-testid={HOME.reminderDismiss} aria-label="Tutup pengingat"
        className="grid place-items-center w-7 h-7 rounded-full shrink-0" style={{ color: "var(--nv-muted)" }}>
        <X size={14} />
      </button>
    </div>
  );
}
