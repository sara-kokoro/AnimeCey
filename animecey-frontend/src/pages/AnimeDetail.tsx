import { useParams, Navigate, Link } from "react-router-dom";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Heart, Play, Star, ArrowUpDown, Youtube, X, Loader2 } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Badge2 } from "@/components/ui/Badge2";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { EpisodeCard } from "@/components/anime/EpisodeCard";
import { fetchAnime } from "@/api/animes";
import { fetchEpisodes } from "@/api/episodes";
import { ensureSeason, fetchSeasonLabels } from "@/api/catalog";
import type { Language } from "@/types";

export default function AnimeDetail() {
  const { id } = useParams();
  const { data: anime, isLoading: loadingAnime } = useQuery({
    queryKey: ["anime", Number(id)],
    queryFn: () => fetchAnime(Number(id)),
    enabled: !!id,
  });

  const [language, setLanguage] = useState<Language | null>(null);
  const [season, setSeason] = useState(1);
  const [reverse, setReverse] = useState(false);
  const [favorite, setFavorite] = useState(false);
  const [trailerOpen, setTrailerOpen] = useState(false);

  const lang = language ?? anime?.languages_available?.[0] ?? "VOSTFR";
  const [preparing, setPreparing] = useState(false);
  const requestedSeasons = useRef<Set<string>>(new Set());

  const { data: seasonLabels = [] } = useQuery({
    queryKey: ["season-labels", Number(id)],
    queryFn: () => fetchSeasonLabels(Number(id)),
    enabled: !!anime,
  });

  const { data: episodes = [], isLoading: loadingEps } = useQuery({
    queryKey: ["episodes", Number(id), lang, season],
    queryFn: () => fetchEpisodes(Number(id), lang, season),
    enabled: !!anime,
    refetchInterval: preparing ? 6000 : false,
  });

  // Saison pas encore récupérée : on demande sa préparation, puis la liste se rafraîchit seule.
  useEffect(() => {
    if (!anime || loadingEps) return;
    if (episodes.length > 0) {
      if (preparing) setPreparing(false);
      return;
    }
    if (seasonLabels.length === 0) return;
    const key = `${lang}-${season}`;
    if (requestedSeasons.current.has(key)) return;
    requestedSeasons.current.add(key);
    ensureSeason(Number(id), lang, season)
      .then((r) => setPreparing(r.preparing))
      .catch(() => setPreparing(false));
  }, [anime, loadingEps, episodes.length, seasonLabels.length, lang, season, id, preparing]);

  if (loadingAnime) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

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
                {anime.trailer_url && (
                  <button
                    onClick={() => setTrailerOpen(true)}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-surface border border-border text-foreground font-body font-semibold hover:border-primary/40 transition-all"
                  >
                    <Youtube className="w-4 h-4" />
                    Trailer
                  </button>
                )}
                <button
                  onClick={() => setFavorite(!favorite)}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-surface border border-border text-foreground font-body font-semibold hover:border-primary/40 transition-all"
                >
                  <Heart className={`w-4 h-4 ${favorite ? "fill-primary text-primary" : ""}`} />
                  {favorite ? "Retiré des favoris" : "Ajouter aux favoris"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-7xl px-4 md:px-6 mt-8 pb-20">
        <div className="flex flex-wrap items-center gap-4 mb-6">
          {anime.languages_available.length > 0 && (
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold mb-1.5">
                Langue
              </p>
              <ToggleGroup2
                value={lang}
                onChange={(v) => setLanguage(v as Language)}
                options={anime.languages_available.map((l) => ({ value: l, label: l }))}
              />
            </div>
          )}
          {anime.type !== "film" && (anime.seasons_count > 1 || seasonLabels.length > 1) && (
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold mb-1.5">
                Saison
              </p>
              <ToggleGroup2
                value={season}
                onChange={(v) => setSeason(Number(v))}
                options={
                  seasonLabels.length > 0
                    ? seasonLabels.map((s) => ({ value: s.number, label: s.label }))
                    : Array.from({ length: anime.seasons_count }).map((_, i) => ({
                        value: i + 1,
                        label: `${i + 1}`,
                      }))
                }
              />
            </div>
          )}
          <button
            onClick={() => setReverse((r) => !r)}
            className="ml-auto inline-flex items-center gap-1.5 text-xs font-body font-semibold text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowUpDown className="w-3.5 h-3.5" />
            {reverse ? "Plus ancien" : "Plus récent"}
          </button>
        </div>

        {loadingEps ? (
          <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
        ) : sorted.length === 0 ? (
          <p className="text-center text-muted-foreground font-body py-8">
            {preparing
              ? "Préparation des épisodes en cours, cela peut prendre une à deux minutes."
              : "Aucun épisode disponible."}
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 md:gap-4">
            {sorted.map((ep, i) => (
              <EpisodeCard key={ep.id} episode={ep} anime={anime} index={i} />
            ))}
          </div>
        )}
      </main>

      {trailerOpen && anime.trailer_url && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 z-[70] bg-black/90 backdrop-blur flex items-center justify-center p-4"
          onClick={() => setTrailerOpen(false)}
        >
          <motion.div
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            className="relative w-full max-w-4xl aspect-video"
            onClick={(e) => e.stopPropagation()}
          >
            <button onClick={() => setTrailerOpen(false)} className="absolute -top-10 right-0 text-white">
              <X className="w-6 h-6" />
            </button>
            <iframe
              src={anime.trailer_url}
              className="w-full h-full rounded-xl"
              allow="autoplay; encrypted-media"
              allowFullScreen
            />
          </motion.div>
        </motion.div>
      )}

      <Footer />
    </motion.div>
  );
}
