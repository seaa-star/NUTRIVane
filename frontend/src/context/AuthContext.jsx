import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { supabase, authEnabled, getDevToken } from "@/lib/supabase";
import { getMe, addFavorite, removeFavorite, addAiFavorite, removeAiFavorite, addScanFavorite, removeScanFavorite } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [stats, setStats] = useState(null);
  const [favorites, setFavorites] = useState([]);
  const [aiFavorites, setAiFavorites] = useState([]);
  const [scanFavorites, setScanFavorites] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me.user);
      setStats(me.stats);
      setFavorites(me.favorites);
      setAiFavorites(me.ai_favorites || []);
      setScanFavorites(me.scan_favorites || []);
    } catch (e) {
      setUser(null);
      setStats(null);
      setFavorites([]);
      setAiFavorites([]);
      setScanFavorites([]);
      if (!supabase) localStorage.removeItem("nv_dev_token");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!supabase) {
      if (getDevToken()) loadMe(); else setLoading(false);
      return;
    }
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) loadMe(); else setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session) loadMe();
      else { setUser(null); setStats(null); setFavorites([]); setAiFavorites([]); setScanFavorites([]); setLoading(false); }
    });
    return () => sub.subscription.unsubscribe();
  }, [loadMe]);

  const signInWithGoogle = useCallback(async () => {
    if (!supabase) { toast.error("Login Google belum dikonfigurasi (REACT_APP_SUPABASE_URL)."); return; }
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) toast.error(error.message);
  }, []);

  const signOut = useCallback(async () => {
    if (supabase) await supabase.auth.signOut();
    localStorage.removeItem("nv_dev_token");
    setUser(null); setStats(null); setFavorites([]); setAiFavorites([]); setScanFavorites([]);
  }, []);

  const toggleFavorite = useCallback(async (slug) => {
    const isFav = favorites.includes(slug);
    setFavorites((f) => (isFav ? f.filter((s) => s !== slug) : [slug, ...f]));
    try {
      const res = isFav ? await removeFavorite(slug) : await addFavorite(slug);
      setFavorites(res.favorites);
      toast.success(isFav ? "Dihapus dari favorit" : "Disimpan ke favorit");
    } catch (e) {
      setFavorites((f) => (isFav ? [slug, ...f] : f.filter((s) => s !== slug)));
      toast.error("Gagal menyimpan favorit");
    }
  }, [favorites]);

  const findAiFavorite = useCallback((name) => aiFavorites.find((f) => f.name.toLowerCase() === (name || "").toLowerCase()), [aiFavorites]);

  const toggleAiFavorite = useCallback(async (item, moodKey) => {
    if (!user) { toast.error("Masuk dulu untuk menyimpan saran AI ke favorit."); return; }
    const existing = findAiFavorite(item.name);
    try {
      const list = existing
        ? await removeAiFavorite(existing.id)
        : await addAiFavorite({ name: item.name, kind: item.kind, why: item.why, origin_tag: item.origin_tag, mood_key: moodKey });
      setAiFavorites(list);
      toast.success(existing ? "Dihapus dari favorit" : "Saran AI disimpan ke favorit");
    } catch (e) {
      toast.error("Gagal menyimpan favorit");
    }
  }, [user, findAiFavorite]);

  const findScanFavorite = useCallback(
    (dish) => scanFavorites.find((f) => f.dish.toLowerCase() === (dish || "").trim().toLowerCase()),
    [scanFavorites]
  );

  const toggleScanFavorite = useCallback(async (dish, result) => {
    if (!user) { toast.error("Masuk dulu untuk menyimpan hasil scan ke favorit."); return; }
    const name = (dish || "").trim();
    if (!name) return;
    const existing = findScanFavorite(name);
    try {
      const list = existing
        ? await removeScanFavorite(existing.id)
        : await addScanFavorite({ dish: name, result });
      setScanFavorites(list);
      toast.success(existing ? "Dihapus dari favorit scan" : "Hasil scan disimpan ke favorit");
    } catch (e) {
      toast.error("Gagal menyimpan favorit");
    }
  }, [user, findScanFavorite]);

  const value = useMemo(() => ({
    user, stats, favorites, aiFavorites, scanFavorites, loading, authEnabled,
    isFavorite: (slug) => favorites.includes(slug),
    isAiFavorite: (name) => Boolean(findAiFavorite(name)),
    isScanFavorite: (dish) => Boolean(findScanFavorite(dish)),
    toggleFavorite, toggleAiFavorite, toggleScanFavorite, signInWithGoogle, signOut, refresh: loadMe, setStats,
  }), [user, stats, favorites, aiFavorites, scanFavorites, loading, toggleFavorite, toggleAiFavorite, toggleScanFavorite, findAiFavorite, findScanFavorite, signInWithGoogle, signOut, loadMe]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
