import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import Layout from "@/components/Layout";
import { RecipeCard } from "@/components/common";
import { MoodSelector } from "@/components/mood/MoodSelector";
import { StoryForm } from "@/components/mood/StoryForm";
import { AiResult } from "@/components/mood/AiResult";
import { useAuth } from "@/context/AuthContext";
import { getMoods, getMood, postMoodRecommend } from "@/lib/api";
import { MOOD } from "@/constants/testIds";

export default function MoodPage() {
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const [moods, setMoods] = useState([]);
  const [selected, setSelected] = useState(params.get("selected") || "berenergi");
  const [detail, setDetail] = useState(null);
  const [story, setStory] = useState("");
  const [current, setCurrent] = useState("");
  const [origin, setOrigin] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const resultRef = useRef(null);

  useEffect(() => { getMoods().then(setMoods); }, []);
  useEffect(() => {
    getMood(selected).then(setDetail).catch(() => {});
    setParams({ selected }, { replace: true });
    setResult(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);
  useEffect(() => {
    if (user?.current_country) setCurrent((c) => c || user.current_country);
    if (user?.origin_country) setOrigin((o) => o || user.origin_country);
  }, [user]);

  const current_mood = moods.find((m) => m.key === selected);

  const ask = async () => {
    setLoading(true); setError("");
    try {
      const res = await postMoodRecommend({ mood_key: selected, story, current_country: current, origin_country: origin });
      setResult(res);
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (e) {
      setError("Rekomendasi belum bisa dibuat. Coba lagi sebentar ya.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="px-5 pt-4 space-y-6">
        <div>
          <p className="nv-eyebrow mb-1" style={{ color: "var(--nv-accent)" }}>Mood check-in</p>
          <h1 className="font-display text-[1.7rem] font-semibold leading-tight" style={{ color: "var(--nv-green-deep)" }}>
            Makan sesuai kebutuhan harimu.
          </h1>
          <p className="mt-2 text-sm leading-relaxed" style={{ color: "var(--nv-muted)" }}>
            Pilih perasaanmu, ceritakan harimu. NutriVane bantu memulai dari pilihan sederhana, bukan menghakimi.
          </p>
        </div>

        <MoodSelector moods={moods} selected={selected} onSelect={setSelected} />

        <StoryForm story={story} setStory={setStory} current={current} setCurrent={setCurrent}
          origin={origin} setOrigin={setOrigin} onSubmit={ask} loading={loading} moodLabel={current_mood?.label} />

        {loading && (
          <div data-testid={MOOD.aiLoading} className="nv-card p-5 space-y-3 animate-pulse">
            <div className="h-3 w-1/3 rounded-full" style={{ background: "var(--nv-green-soft)" }} />
            <div className="h-5 w-3/4 rounded-full" style={{ background: "var(--nv-green-soft)" }} />
            <div className="h-3 w-full rounded-full" style={{ background: "var(--nv-line)" }} />
            <div className="h-3 w-5/6 rounded-full" style={{ background: "var(--nv-line)" }} />
          </div>
        )}
        {error && (
          <p data-testid={MOOD.aiError} className="text-xs rounded-2xl px-4 py-3" style={{ background: "var(--nv-accent-soft)", color: "var(--nv-accent)" }}>{error}</p>
        )}
        <div ref={resultRef} style={{ scrollMarginTop: "72px" }}>
          {result && !loading && <AiResult result={result} onRetry={ask} />}
        </div>

        <section className="nv-rise" style={{ animationDelay: "80ms" }}>
          <div className="flex items-end justify-between mb-3.5">
            <div>
              <p className="nv-eyebrow mb-1">Curated for you</p>
              <h2 className="font-display text-xl font-semibold" style={{ color: "var(--nv-green-deep)" }}>
                Pilihan {current_mood?.label?.toLowerCase()}
              </h2>
            </div>
            <Link to="/recipes" data-testid={MOOD.seeAll} className="flex items-center gap-1 text-xs font-bold" style={{ color: "var(--nv-accent)" }}>
              semua resep <ArrowRight size={13} />
            </Link>
          </div>
          <div className="space-y-4">
            {detail?.recipes?.map((r) => (
              <RecipeCard key={r.slug} r={r} to={`/recipes/${r.slug}`} tid={MOOD.recipe(r.slug)} />
            ))}
          </div>
        </section>
      </div>
    </Layout>
  );
}
