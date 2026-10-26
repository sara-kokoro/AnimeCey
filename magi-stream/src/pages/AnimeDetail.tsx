import { useParams, Navigate, Link, useNavigate } from "@/lib/router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Calendar, Check, Film, Play, Plus, Star, Tv, ArrowUpDown, Youtube, X, Loader2 } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { Badge2 } from "@/components/ui/Badge2";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { EpisodeCard } from "@/components/anime/EpisodeCard";
import { AnimeGrid } from "@/components/anime/AnimeGrid";
import { fetchAnime, fetchAnimes } from "@/api/animes";
import { fetchEpisodes } from "@/api/episodes";
import { ensureSeason, fetchSeasonLabels } from "@/api/catalog";
import { addFavorite, fetchFavorites, removeFavorite } from "@/api/users";
import { useAuthStore } from "@/stores/auth";
import { ReportButton } from "@/components/report/ReportButton";
import { BannerAd } from "@/components/ads/BannerAd";
import { SocialBarAd } from "@/components/ads/SocialBarAd";
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
  const isAuthenticated = useAuthStore((st) => st.isAuthenticated);
  const navigate = useNavigate();
  useEffect(() => {
    if (!isAuthenticated || !id) { setFavorite(false); return; }
    fetchFavorites()
      .then((rows: { anime: { id: number } }[]) => setFavorite(rows.some((r) => r.anime.id === Number(id))))
      .catch(() => undefined);
  }, [isAuthenticated, id]);
  const toggleFavorite = async () => {
    if (!isAuthenticated) { navigate("/auth"); return; }
    const next = !favorite;
    setFavorite(next);
    try {
      if (next) await addFavorite(Number(id)); else await removeFavorite(Number(id));
    } catch {
      setFavorite(!next);
    }
  };
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

  const [tab, setTab] = useState<"overview" | "episodes" | "related">("overview");
  const relatedGenre = anime?.genres?.[0];
  const { data: related } = useQuery({
    queryKey: ["related", relatedGenre, anime?.type],
    queryFn: () => fetchAnimes({ genre: relatedGenre, limit: 13, sort: "score" }),
    enabled: !!relatedGenre,
    staleTime: 5 * 60_000,
  });
  const relatedList = (related?.items ?? []).filter((a) => a.id !== anime?.id).slice(0, 12);


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

  const firstEpisode = episodes[0];
  const tabBtn = (t: typeof tab, label: string) => (
    <button
      key={t}
      onClick={() => setTab(t)}
      className={`shrink-0 px-5 py-2 rounded-full text-sm font-semibold transition-colors ${
        tab === t ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />

      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <img
            src={anime.banner_url || anime.poster_url}
            alt=""
            className={`w-full h-full object-cover ${anime.banner_url ? "opacity-50" : "blur-2xl scale-110 opacity-40"}`}
          />
          <div className="absolute inset-0 bg-gradient-hero" />
        </div>

        <div className="relative z-10 mx-auto max-w-4xl px-4 pt-24 md:pt-32 pb-8 flex flex-col items-center text-center">
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="w-[180px] md:w-[230px] aspect-[2/3] rounded-2xl overflow-hidden shadow-card ring-1 ring-foreground/10 -rotate-1 hover:rotate-0 transition-transform"
          >
            <img src={anime.poster_url} alt={anime.title} className="w-full h-full object-cover" />
          </motion.div>

          <h1 className="mt-6 font-display font-black text-3xl md:text-5xl leading-tight">{anime.title}</h1>
          {anime.title_jp && <p className="text-muted-foreground mt-1.5 text-sm">{anime.title_jp}</p>}

          <div className="mt-4 flex flex-wrap justify-center gap-2 text-[11px] font-semibold">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary/15 text-primary border border-primary/30">
              <Star className="w-3.5 h-3.5 fill-current" /> {anime.score}
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-foreground/10 border border-foreground/15">
              <Calendar className="w-3.5 h-3.5" /> {anime.year}
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-foreground/10 border border-foreground/15">
              {anime.type === "film" ? <Film className="w-3.5 h-3.5" /> : <Tv className="w-3.5 h-3.5" />}
              {anime.type === "film" ? "Film" : "Série"}
            </span>
            <span
              className={`px-2.5 py-1 rounded-full border ${
                anime.status === "ongoing" ? "bg-highlight/15 text-highlight border-highlight/30" : "bg-foreground/10 border-foreground/15"
              }`}
            >
              {statusLabel}
            </span>
            {anime.type !== "film" && (
              <span className="px-2.5 py-1 rounded-full bg-foreground/10 border border-foreground/15">
                {anime.seasons_count} saison{anime.seasons_count > 1 ? "s" : ""} · {anime.episodes_count} ép.
              </span>
            )}
            {anime.languages_available.map((l) => (
              <span key={l} className="px-2.5 py-1 rounded-full bg-foreground/10 border border-foreground/15">{l}</span>
            ))}
          </div>

          <div className="mt-6 flex flex-wrap justify-center gap-3">
            {firstEpisode ? (
              <Link
                to={`/watch/${firstEpisode.id}`}
                className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-primary text-primary-foreground font-semibold hover:bg-primary-dim transition-all hover:scale-[1.03] shadow-glow"
              >
                <Play className="w-4 h-4 fill-current" /> Regarder
              </Link>
            ) : (
              <button
                onClick={() => setTab("episodes")}
                className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-primary text-primary-foreground font-semibold shadow-glow"
              >
                <Play className="w-4 h-4 fill-current" /> Regarder
              </button>
            )}
            <button
              onClick={toggleFavorite}
              className="inline-flex items-center gap-2 px-5 py-3 rounded-full bg-foreground/10 border border-foreground/20 backdrop-blur font-semibold hover:bg-foreground/15 transition-colors"
            >
              {favorite ? <Check className="w-4 h-4 text-primary" /> : <Plus className="w-4 h-4" />}
              {favorite ? "Dans mes favoris" : "Ajouter"}
            </button>
            {anime.trailer_url ? (
              <button
                onClick={() => setTrailerOpen(true)}
                className="inline-flex items-center gap-2 px-5 py-3 rounded-full bg-foreground/10 border border-foreground/20 backdrop-blur font-semibold hover:bg-foreground/15 transition-colors"
              >
                <Youtube className="w-4 h-4" /> Bande-annonce
              </button>
            ) : (
              <ReportButton animeId={Number(id)} className="px-5 py-3 rounded-full" />
            )}
          </div>
        </div>
      </section>

      <main className="mx-auto max-w-5xl px-4 md:px-6 pb-20">
        <SocialBarAd />

        <div className="sticky top-16 z-30 -mx-4 px-4 py-3 bg-background/90 backdrop-blur-xl">
          <div className="flex gap-1 p-1 rounded-full bg-surface border border-border-subtle w-fit max-w-full overflow-x-auto no-scrollbar mx-auto">
            {tabBtn("overview", "Aperçu")}
            {tabBtn("episodes", "Épisodes")}
            {tabBtn("related", "Liés")}
          </div>
        </div>

        {tab === "overview" && (
          <div className="mt-4 space-y-6">
            <div>
              <h2 className="font-display font-bold text-lg mb-2">Synopsis</h2>
              <p className="text-foreground/85 leading-relaxed">{anime.synopsis}</p>
            </div>
            <div>
              <h2 className="font-display font-bold text-lg mb-2">Genres</h2>
              <div className="flex flex-wrap gap-2">
                {anime.genres.map((g) => (
                  <Link key={g} to={`/genre/${g.toLowerCase()}`}>
                    <Badge2 variant="genre">{g}</Badge2>
                  </Link>
                ))}
              </div>
            </div>
            <dl className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                ["Type", anime.type === "film" ? "Film" : "Série"],
                ["Statut", statusLabel],
                ["Année", String(anime.year)],
                ["Note", String(anime.score)],
              ].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-surface border border-border-subtle p-3">
                  <dt className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">{k}</dt>
                  <dd className="mt-1 font-display font-bold">{v}</dd>
                </div>
              ))}
            </dl>
            {anime.trailer_url && <ReportButton animeId={Number(id)} className="px-5 py-2.5 rounded-full" />}
            <BannerAd />
          </div>
        )}

        {tab === "episodes" && (
          <div className="mt-4">
            <div className="rounded-2xl bg-surface border border-border-subtle p-4 mb-4 flex flex-wrap items-end gap-4 min-w-0">
              {anime.languages_available.length > 0 && (
                <div className="min-w-0 max-w-full">
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">Langue</p>
                  <ToggleGroup2
                    size="sm"
                    value={lang}
                    onChange={(v) => setLanguage(v as Language)}
                    options={anime.languages_available.map((l) => ({ value: l, label: l }))}
                  />
                </div>
              )}
              {anime.type !== "film" && (anime.seasons_count > 1 || seasonLabels.length > 1) && (
                <div className="min-w-0 max-w-full">
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">Saison</p>
                  <ToggleGroup2
                    size="sm"
                    value={season}
                    onChange={(v) => setSeason(Number(v))}
                    options={
                      seasonLabels.length > 0
                        ? seasonLabels.map((s) => ({ value: s.number, label: s.label }))
                        : Array.from({ length: anime.seasons_count }).map((_, i) => ({ value: i + 1, label: `${i + 1}` }))
                    }
                  />
                </div>
              )}
              <button
                onClick={() => setReverse((r) => !r)}
                className="ml-auto inline-flex items-center gap-1.5 h-9 px-3 rounded-full bg-surface-2 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowUpDown className="w-3.5 h-3.5" />
                {reverse ? "Plus ancien" : "Plus récent"}
              </button>
            </div>

            {loadingEps ? (
              <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
            ) : sorted.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">
                {preparing
                  ? "Préparation des épisodes en cours, cela peut prendre une à deux minutes."
                  : "Aucun épisode disponible."}
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 min-w-0">
                {sorted.map((ep) => (
                  <EpisodeCard
                    key={ep.id}
                    episode={ep}
                    seasonLabel={seasonLabels.find((s) => s.number === ep.season_number)?.label}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "related" && (
          <div className="mt-4">
            {relatedList.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">Aucun titre lié pour le moment.</p>
            ) : (
              <AnimeGrid animes={relatedList} />
            )}
          </div>
        )}
      </main>

      {trailerOpen && anime.trailer_url && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="fixed inset-0 z-[70] bg-background/95 backdrop-blur flex items-center justify-center p-4"
          onClick={() => setTrailerOpen(false)}
        >
          <motion.div
            initial={{ scale: 0.9 }}
            animate={{ scale: 1 }}
            className="relative w-full max-w-4xl aspect-video"
            onClick={(e) => e.stopPropagation()}
          >
            <button onClick={() => setTrailerOpen(false)} aria-label="Fermer" className="absolute -top-10 right-0 text-foreground">
              <X className="w-6 h-6" />
            </button>
            <iframe src={anime.trailer_url} className="w-full h-full rounded-xl" allow="autoplay; encrypted-media" allowFullScreen />
          </motion.div>
        </motion.div>
      )}

      <Footer />
    </motion.div>
  );
}
