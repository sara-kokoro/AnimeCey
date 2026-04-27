import { useParams, Navigate, Link } from "react-router-dom";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Heart, Play, Star, AlertCircle, Film, ArrowUpDown, Youtube, X } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Badge2 } from "@/components/ui/Badge2";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { EpisodeCard } from "@/components/anime/EpisodeCard";
import { getAnimeById, getEpisodes } from "@/data/mock";
import type { Language } from "@/types";

export default function AnimeDetail() {
  const { id } = useParams();
  const anime = getAnimeById(Number(id));

  const [language, setLanguage] = useState<Language>(
    anime?.languages_available[0] ?? "VOSTFR",
  );
  const [season, setSeason] = useState(1);
  const [reverse, setReverse] = useState(false);
  const [blur, setBlur] = useState(false);
  const [favorite, setFavorite] = useState(false);
  const [trailerOpen, setTrailerOpen] = useState(false);

  const episodes = useMemo(
    () => (anime ? getEpisodes(anime.id, language, season) : []),
    [anime, language, season],
  );

  if (!anime) return <Navigate to="/" replace />;

  const sorted = reverse ? [...episodes].reverse() : episodes;

  const statusLabel =
    anime.status === "ongoing"
      ? "En cours"
      : anime.status === "completed"
        ? "Terminé"
        : "À venir";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />

      {/* Hero */}
      <section className="relative pt-16">
        <div className="relative h-[260px] md:h-[420px] overflow-hidden">
          <img
            src={anime.banner_url}
            alt=""
            className="absolute inset-0 w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-background/60" />
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/50 to-transparent" />
        </div>

        <div className="mx-auto max-w-7xl px-4 md:px-6 -mt-32 md:-mt-40 relative z-10">
          <div className="flex flex-col md:flex-row gap-6 md:gap-8">
            <div className="shrink-0 mx-auto md:mx-0 w-[180px] md:w-[220px] aspect-[2/3] rounded-xl overflow-hidden shadow-2xl ring-1 ring-border">
              <img
                src={anime.poster_url}
                alt={anime.title}
                className="w-full h-full object-cover"
              />
            </div>

            <div className="flex-1 text-center md:text-left">
              <h1 className="font-display font-extrabold text-3xl md:text-5xl text-foreground leading-tight">
                {anime.title}
              </h1>
              {anime.title_jp && (
                <p className="text-muted-foreground font-body mt-1.5">
                  {anime.title_jp}
                </p>
              )}

              <div className="flex flex-wrap justify-center md:justify-start items-center gap-3 mt-4 text-sm font-body text-muted-foreground">
                <span className="inline-flex items-center gap-1.5 text-foreground font-semibold">
                  <Star className="w-4 h-4 fill-primary text-primary" />
                  <span className="text-lg font-display font-bold">{anime.score}</span>
                </span>
                <span>•</span>
                <span>{anime.year}</span>
                <span>•</span>
                <span>{anime.type === "film" ? "Film" : "Série"}</span>
                <span>•</span>
                <span>{statusLabel}</span>
                {anime.type !== "film" && (
                  <>
                    <span>•</span>
                    <span>{anime.seasons_count} saison{anime.seasons_count > 1 ? "s" : ""}</span>
                    <span>•</span>
                    <span>{anime.episodes_count} épisodes</span>
                  </>
                )}
              </div>

              <div className="flex flex-wrap justify-center md:justify-start gap-2 mt-4">
                {anime.genres.map((g) => (
                  <Link key={g} to={`/genre/${g.toLowerCase()}`}>
                    <Badge2 variant="genre">{g}</Badge2>
                  </Link>
                ))}
              </div>

              <p className="text-foreground/90 font-body mt-5 leading-relaxed max-w-3xl">
                {anime.synopsis}
              </p>

              <div className="flex flex-wrap justify-center md:justify-start gap-3 mt-6">
                <button
                  onClick={() => setTrailerOpen(true)}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-surface border border-border text-foreground font-body font-semibold hover:border-primary/40 transition-all"
                >
                  <Youtube className="w-4 h-4" />
                  Bande annonce
                </button>
                <button
                  aria-label="Ajouter aux favoris"
                  onClick={() => setFavorite((v) => !v)}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-surface border border-border font-body font-semibold transition-all hover:border-primary/40"
                >
                  <motion.span
                    key={String(favorite)}
                    initial={{ scale: 0.6 }}
                    animate={{ scale: 1 }}
                    transition={{ type: "spring", stiffness: 400, damping: 15 }}
                    className="inline-flex"
                  >
                    <Heart
                      className={`w-4 h-4 ${favorite ? "fill-primary text-primary" : "text-foreground"}`}
                    />
                  </motion.span>
                  <span className={favorite ? "text-primary" : "text-foreground"}>
                    {favorite ? "Favori" : "Favori"}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Selection */}
      <section className="mx-auto max-w-7xl px-4 md:px-6 mt-10 space-y-6">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-body font-semibold mb-2">
            Langue
          </p>
          <ToggleGroup2
            options={anime.languages_available.map((l) => ({ value: l, label: l }))}
            value={language}
            onChange={(v) => setLanguage(v as Language)}
            size="sm"
          />
        </div>

        {anime.type !== "film" && (
          <div>
            <p className="text-xs uppercase tracking-wider text-muted-foreground font-body font-semibold mb-2">
              Saison
            </p>
            <ToggleGroup2
              options={Array.from({ length: anime.seasons_count }).map((_, i) => ({
                value: i + 1,
                label: `Saison ${i + 1}`,
              }))}
              value={season}
              onChange={(v) => setSeason(Number(v))}
              size="sm"
            />
          </div>
        )}
      </section>

      {/* Episodes */}
      <section className="mx-auto max-w-7xl px-4 md:px-6 mt-10">
        <div className="flex items-center justify-between mb-4 gap-3">
          <h2 className="font-display font-bold text-lg md:text-xl">
            Épisodes <span className="text-muted-foreground font-normal">({sorted.length})</span>
          </h2>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setReverse((v) => !v)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-border text-xs font-body font-semibold text-muted-foreground hover:text-foreground"
              aria-label="Inverser l'ordre"
            >
              <ArrowUpDown className="w-3.5 h-3.5" />
              Ordre
            </button>
            <button
              onClick={() => setBlur((v) => !v)}
              className="inline-flex items-center gap-2 text-xs font-body font-semibold text-muted-foreground"
              aria-pressed={blur}
            >
              Flouter
              <span
                className={`relative w-10 h-5 rounded-full transition-colors ${blur ? "bg-primary" : "bg-surface-2"}`}
              >
                <span
                  className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${blur ? "translate-x-5" : "translate-x-0.5"}`}
                />
              </span>
            </button>
          </div>
        </div>

        {sorted.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Film className="w-10 h-10 text-muted-dim mb-3" />
            <p className="text-muted-foreground font-body">
              Aucun épisode disponible pour cette combinaison.
            </p>
            <AlertCircle className="hidden" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {sorted.map((ep) => (
              <EpisodeCard key={ep.id} episode={ep} blurred={blur} />
            ))}
          </div>
        )}
      </section>

      <Footer />

      {/* Trailer modal */}
      {trailerOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 z-[100] bg-black/85 backdrop-blur flex items-center justify-center p-4"
          onClick={() => setTrailerOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="relative w-full max-w-4xl aspect-video rounded-2xl overflow-hidden bg-black"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              aria-label="Fermer"
              onClick={() => setTrailerOpen(false)}
              className="absolute top-3 right-3 z-10 w-10 h-10 rounded-full bg-black/70 flex items-center justify-center text-white hover:bg-black"
            >
              <X className="w-5 h-5" />
            </button>
            <iframe
              src={anime.trailer_url}
              title="Bande annonce"
              className="w-full h-full"
              allow="autoplay; encrypted-media"
              allowFullScreen
            />
            <Play className="hidden" />
          </motion.div>
        </motion.div>
      )}
    </motion.div>
  );
}