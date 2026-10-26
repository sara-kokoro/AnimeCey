import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Calendar, Check, Film, Info, Play, Plus, Star, Tv } from "lucide-react";
import { Link, useNavigate } from "@/lib/router";
import { Badge2 } from "@/components/ui/Badge2";
import { fetchFeatured } from "@/api/animes";
import { addToWatchlist, fetchWatchlist, removeFromWatchlist } from "@/api/users";
import { useAuthStore } from "@/stores/auth";
import type { Anime } from "@/types";

const DURATION = 15000;

export function HeroCarousel() {
  const { data: featured = [], isLoading } = useQuery<Anime[]>({ queryKey: ["featured"], queryFn: fetchFeatured });
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || featured.length === 0) return;
    const t = setTimeout(() => setIdx((i) => (i + 1) % featured.length), DURATION);
    return () => clearTimeout(t);
  }, [idx, paused, featured.length]);

  // Watchlist : connexion requise ; un clic ajoute, un second clic retire.
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((st) => st.isAuthenticated);
  const [listed, setListed] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!isAuthenticated) { setListed(new Set()); return; }
    fetchWatchlist()
      .then((rows: { anime: { id: number } }[]) => setListed(new Set(rows.map((r) => r.anime.id))))
      .catch(() => undefined);
  }, [isAuthenticated]);
  const anime = featured.length > 0 ? featured[idx % featured.length] : undefined;
  const inList = anime ? listed.has(anime.id) : false;

  const toggleWatchlist = async () => {
    if (!anime) return;
    if (!isAuthenticated) { navigate("/auth"); return; }
    if (busy) return;
    setBusy(true);
    try {
      if (inList) await removeFromWatchlist(anime.id);
      else await addToWatchlist(anime.id, "planned");
      setListed((cur) => {
        const next = new Set(cur);
        if (inList) next.delete(anime.id); else next.add(anime.id);
        return next;
      });
    } catch {
      /* échec réseau : l'état reste inchangé */
    } finally {
      setBusy(false);
    }
  };

  if (!anime) {
    // Chargement : bloc animé discret. Rien à afficher : bandeau de bienvenue.
    return (
      <section className="relative w-full h-[56svh] md:h-[70vh] min-h-[380px] overflow-hidden bg-background flex items-end">
        <div className="absolute inset-0 bg-gradient-to-br from-surface via-background to-background" />
        <div className="absolute -top-24 -right-24 w-[420px] h-[420px] rounded-full bg-primary/10 blur-3xl" />
        <div className={"relative z-10 mx-auto w-full max-w-7xl px-4 md:px-6 pb-14 md:pb-20 " + (isLoading ? "animate-pulse" : "")}>
          <p className="font-display font-extrabold text-4xl md:text-6xl text-foreground leading-[1.05]">
            Magi-<span className="text-primary">Stream</span>
          </p>
          <p className="mt-3 max-w-xl text-muted-foreground font-body md:text-lg">
            {isLoading ? "Chargement des animés…" : "Tes animés en VF et VOSTFR, sans pub."}
          </p>
          {!isLoading && (
            <Link
              to="/catalogue"
              className="mt-6 inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground font-body font-semibold hover:bg-primary-dim transition-colors"
            >
              <Play className="w-4 h-4 fill-current" />
              Explorer le catalogue
            </Link>
          )}
        </div>
      </section>
    );
  }

  const bg = (anime.banner_url || anime.poster_url || "/placeholder.svg").replace(/^http:\/\//, "https://");
  const poster = (anime.poster_url || "/placeholder.svg").replace(/^http:\/\//, "https://");
  const langs = anime.languages_available ?? [];

  return (
    <section
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className="relative w-full min-h-[640px] md:min-h-[92vh] overflow-hidden bg-background"
      aria-label="Animés en vedette"
    >
      <AnimatePresence mode="sync">
        <motion.div
          key={anime.id}
          initial={{ opacity: 0, scale: 1.05 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.9 }}
          className="absolute inset-0"
        >
          <img
            src={bg}
            alt=""
            referrerPolicy="no-referrer"
            onError={(e) => { e.currentTarget.onerror = null; e.currentTarget.src = "/placeholder.svg"; }}
            className={"w-full h-full object-cover " + (anime.banner_url ? "opacity-70" : "scale-110 blur-xl opacity-60")}
            fetchPriority="high"
          />
          <div className="absolute inset-0 bg-gradient-hero" />
          <div className="absolute inset-0 bg-background/30" />
        </motion.div>
      </AnimatePresence>

      <div className="relative z-10 mx-auto max-w-5xl px-4 pt-24 md:pt-32 pb-12 flex flex-col items-center text-center">
        <AnimatePresence mode="wait">
          <motion.div
            key={anime.id}
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col items-center"
          >
            <Link
              to={`/anime/${anime.id}`}
              className="block w-[170px] md:w-[220px] aspect-[2/3] rounded-2xl overflow-hidden shadow-card ring-1 ring-foreground/10"
            >
              <img
                src={poster}
                alt={`Affiche de ${anime.title}`}
                referrerPolicy="no-referrer"
                className="w-full h-full object-cover"
              />
            </Link>

            <h2 className="mt-6 font-display font-black text-3xl sm:text-4xl md:text-6xl text-foreground leading-[1.05] max-w-3xl line-clamp-2">
              {anime.title}
            </h2>

            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary/15 text-primary border border-primary/30 text-[11px] font-bold">
                <Star className="w-3.5 h-3.5 fill-current" />
                {anime.score}
              </span>
              {anime.year ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-foreground/10 border border-foreground/15 text-[11px] font-semibold">
                  <Calendar className="w-3.5 h-3.5" />
                  {anime.year}
                </span>
              ) : null}
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-foreground/10 border border-foreground/15 text-[11px] font-semibold">
                {anime.type === "film" ? <Film className="w-3.5 h-3.5" /> : <Tv className="w-3.5 h-3.5" />}
                {anime.type === "film" ? "Film" : `${anime.episodes_count} ép.`}
              </span>
              {langs.map((l) => (
                <span key={l} className="px-2.5 py-1 rounded-full bg-foreground/10 border border-foreground/15 text-[11px] font-semibold">
                  {l}
                </span>
              ))}
              {(anime.genres ?? []).slice(0, 2).map((g) => (
                <Badge2 key={g} variant="genre">{g}</Badge2>
              ))}
            </div>

            <p className="hidden md:block mt-4 text-muted-foreground max-w-2xl line-clamp-2">{anime.synopsis}</p>

            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Link
                to={`/anime/${anime.id}`}
                className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-primary text-primary-foreground font-semibold hover:bg-primary-dim transition-all hover:scale-[1.03] shadow-glow"
              >
                <Play className="w-4 h-4 fill-current" />
                Regarder
              </Link>
              <Link
                to={`/anime/${anime.id}`}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-foreground/10 border border-foreground/20 backdrop-blur font-semibold hover:bg-foreground/15 transition-colors"
              >
                <Info className="w-4 h-4" />
                Plus d'infos
              </Link>
              <button
                onClick={toggleWatchlist}
                disabled={busy}
                aria-label={inList ? "Retirer de ma liste" : "Ajouter à ma liste"}
                className="inline-flex items-center gap-2 px-5 py-3 rounded-full bg-foreground/10 border border-foreground/20 backdrop-blur font-semibold hover:bg-foreground/15 transition-colors disabled:opacity-60"
              >
                {inList ? <Check className="w-4 h-4 text-primary" /> : <Plus className="w-4 h-4" />}
                {inList ? "Ajouté" : "Ajouter"}
              </button>
            </div>
          </motion.div>
        </AnimatePresence>

        <div className="flex items-center gap-2 mt-8">
          {featured.map((a, i) => (
            <button
              key={a.id}
              aria-label={`Slide ${i + 1}`}
              onClick={() => setIdx(i)}
              className="relative h-1.5 rounded-full overflow-hidden bg-foreground/25 transition-all"
              style={{ width: i === idx ? 40 : 10 }}
            >
              {i === idx && !paused && (
                <motion.span
                  key={`bar-${idx}`}
                  initial={{ width: 0 }}
                  animate={{ width: "100%" }}
                  transition={{ duration: DURATION / 1000, ease: "linear" }}
                  className="absolute inset-y-0 left-0 bg-primary"
                />
              )}
              {i === idx && paused && <span className="absolute inset-0 bg-primary" />}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
