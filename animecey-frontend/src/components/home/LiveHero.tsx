import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Info, Play, Star } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge2 } from "@/components/ui/Badge2";
import type { Anime } from "@/types";

const DURATION = 9000;

/** Grand bandeau « Films & Séries » : 6 titres qui changent chaque jour. */
export function LiveHero({ items }: { items: Anime[] }) {
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || items.length < 2) return;
    const t = setTimeout(() => setIdx((i) => (i + 1) % items.length), DURATION);
    return () => clearTimeout(t);
  }, [idx, paused, items.length]);

  if (items.length === 0) return null;
  const a = items[idx % items.length];
  const image = a.banner_url || a.poster_url;
  const go = (d: number) => setIdx((i) => (i + d + items.length) % items.length);

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-border-subtle bg-surface h-[360px] md:h-[460px]"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <AnimatePresence mode="wait">
        <motion.div
          key={a.id}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5 }}
          className="absolute inset-0"
        >
          {image && (
            <img
              src={image}
              alt=""
              className="absolute inset-0 w-full h-full object-cover scale-105"
              loading="lazy"
            />
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/60 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-r from-background/90 via-background/40 to-transparent" />

          <div className="relative z-10 h-full flex flex-col justify-end p-5 md:p-10 max-w-2xl">
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <Badge2 variant={a.type === "film" ? "film" : "serie"}>{a.type === "film" ? "Film" : "Série"}</Badge2>
              {a.year ? <span className="text-sm text-muted-foreground font-body">{a.year}</span> : null}
              {a.score > 0 && (
                <span className="inline-flex items-center gap-1 text-sm font-body font-semibold text-foreground">
                  <Star className="w-4 h-4 fill-primary text-primary" />
                  {a.score.toFixed(1)}
                </span>
              )}
              {a.languages_available?.map((l) => (
                <Badge2 key={l} variant={l === "VF" ? "vf" : "vostfr"}>{l}</Badge2>
              ))}
            </div>
            <h2 className="font-display font-extrabold text-3xl md:text-5xl text-foreground leading-[1.05]">
              {a.title}
            </h2>
            {a.genres?.length > 0 && (
              <p className="mt-2 text-sm text-muted-foreground font-body">{a.genres.slice(0, 3).join(" · ")}</p>
            )}
            {a.synopsis && (
              <p className="mt-3 text-sm md:text-base text-foreground/80 font-body line-clamp-3">{a.synopsis}</p>
            )}
            <div className="mt-5 flex flex-wrap gap-3">
              <Link
                to={`/anime/${a.id}`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-primary text-primary-foreground font-body font-semibold hover:bg-primary-dim transition-colors"
              >
                <Play className="w-4 h-4 fill-current" />
                Regarder
              </Link>
              <Link
                to={`/anime/${a.id}`}
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-surface/70 backdrop-blur border border-border-subtle text-foreground font-body font-semibold hover:bg-surface transition-colors"
              >
                <Info className="w-4 h-4" />
                Détails
              </Link>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>

      {items.length > 1 && (
        <>
          <button
            onClick={() => go(-1)}
            aria-label="Précédent"
            className="absolute left-3 top-1/2 -translate-y-1/2 z-20 hidden md:flex w-10 h-10 rounded-full bg-background/60 backdrop-blur items-center justify-center text-foreground hover:bg-background/90"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            onClick={() => go(1)}
            aria-label="Suivant"
            className="absolute right-3 top-1/2 -translate-y-1/2 z-20 hidden md:flex w-10 h-10 rounded-full bg-background/60 backdrop-blur items-center justify-center text-foreground hover:bg-background/90"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
          <div className="absolute bottom-4 right-5 z-20 flex gap-1.5">
            {items.map((_, i) => (
              <button
                key={i}
                onClick={() => setIdx(i)}
                aria-label={`Titre ${i + 1}`}
                className={`h-1.5 rounded-full transition-all ${i === idx % items.length ? "w-6 bg-primary" : "w-1.5 bg-foreground/40"}`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
