import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Play, Plus, Star } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge2 } from "@/components/ui/Badge2";
import { fetchFeatured } from "@/api/animes";
import type { Anime } from "@/types";

const DURATION = 15000;

export function HeroCarousel() {
  const { data: featured = [] } = useQuery<Anime[]>({ queryKey: ["featured"], queryFn: fetchFeatured });
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || featured.length === 0) return;
    const t = setTimeout(() => setIdx((i) => (i + 1) % featured.length), DURATION);
    return () => clearTimeout(t);
  }, [idx, paused, featured.length]);

  if (featured.length === 0) {
    return (
      <section className="relative w-full h-[70vh] md:h-[88vh] min-h-[520px] bg-background flex items-center justify-center">
        <div className="animate-pulse text-muted-foreground">Chargement...</div>
      </section>
    );
  }

  const anime = featured[idx % featured.length];

  return (
    <section
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      className="relative w-full h-[70vh] md:h-[88vh] min-h-[520px] overflow-hidden bg-background"
      aria-label="Animés en vedette"
    >
      <AnimatePresence mode="sync">
        <motion.div
          key={anime.id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8 }}
          className="absolute inset-0"
        >
          <img
            src={anime.banner_url}
            alt={anime.title}
            className="w-full h-full object-cover"
            fetchPriority="high"
          />
          <div
            className="absolute inset-0"
            style={{ background: "var(--gradient-hero)" }}
          />
        </motion.div>
      </AnimatePresence>

      <div className="relative z-10 h-full mx-auto max-w-7xl px-4 md:px-6 flex flex-col justify-end pb-20 md:pb-32">
        <AnimatePresence mode="wait">
          <motion.div
            key={anime.id}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="max-w-2xl"
          >
            <div className="flex flex-wrap gap-2 mb-4">
              {anime.genres.slice(0, 3).map((g) => (
                <Badge2 key={g} variant="genre">
                  {g}
                </Badge2>
              ))}
            </div>

            <h1 className="font-display font-extrabold text-4xl md:text-6xl text-white leading-[1.05] drop-shadow-[0_2px_20px_rgba(0,0,0,0.5)]">
              {anime.title}
            </h1>

            <div className="flex items-center gap-3 mt-3 text-sm font-body">
              <span className="inline-flex items-center gap-1.5 text-primary font-semibold">
                <Star className="w-4 h-4 fill-primary" />
                {anime.score}
              </span>
              <span className="text-muted-foreground">•</span>
              <span className="text-muted-foreground">{anime.year}</span>
              <span className="text-muted-foreground">•</span>
              <span className="text-muted-foreground">
                {anime.type === "film" ? "Film" : `${anime.episodes_count} épisodes`}
              </span>
            </div>

            <p className="hidden md:block text-base text-muted-foreground font-body mt-4 line-clamp-3 max-w-xl">
              {anime.synopsis}
            </p>

            <div className="flex flex-wrap gap-3 mt-6">
              <Link
                to={`/anime/${anime.id}`}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground font-body font-semibold hover:bg-primary-dim transition-all hover:scale-[1.02] shadow-[var(--shadow-glow)]"
              >
                <Play className="w-4 h-4 fill-current" />
                Regarder
              </Link>
              <button className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white/10 text-white border border-white/20 backdrop-blur font-body font-semibold hover:bg-white/15 transition-all hover:scale-[1.02]">
                <Plus className="w-4 h-4" />
                Watchlist
              </button>
            </div>
          </motion.div>
        </AnimatePresence>

        {/* Indicators */}
        <div className="flex items-center gap-3 mt-10">
          {featured.map((a, i) => (
            <button
              key={a.id}
              aria-label={`Slide ${i + 1}`}
              onClick={() => setIdx(i)}
              className="group/dot relative h-1 rounded-full overflow-hidden bg-white/25 transition-all"
              style={{ width: i === idx ? 56 : 24 }}
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
              {i === idx && paused && (
                <span className="absolute inset-0 bg-primary" />
              )}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
