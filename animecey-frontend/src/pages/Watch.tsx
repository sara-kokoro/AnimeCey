import { useParams, Navigate, Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Heart, Loader2 } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { EpisodeCard } from "@/components/anime/EpisodeCard";
import { CommentSection } from "@/components/comments/CommentSection";
import { fetchEpisode, fetchEpisodes, getStreamUrl } from "@/api/episodes";
import { fetchAnime } from "@/api/animes";
import { fetchAutoStream, fetchEpisodeServers, fetchSeasonLabels } from "@/api/catalog";
import type { Language } from "@/types";

export default function Watch() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [serverKey, setServerKey] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language | null>(null);
  const [liked, setLiked] = useState(false);
  const [loading, setLoading] = useState(true);

  const { data: episode, isLoading: loadingEp } = useQuery({
    queryKey: ["episode", Number(id)],
    queryFn: () => fetchEpisode(Number(id)),
    enabled: !!id,
  });

  const animeId = episode?.anime_id;
  const { data: anime } = useQuery({
    queryKey: ["anime", animeId],
    queryFn: () => fetchAnime(animeId!),
    enabled: !!animeId,
  });

  const lang = (language ?? episode?.language ?? "VOSTFR") as Language;
  const seasonNum = episode?.season_number ?? 1;

  const { data: episodes = [] } = useQuery({
    queryKey: ["episodes", animeId, lang, seasonNum],
    queryFn: () => fetchEpisodes(animeId!, lang, seasonNum),
    enabled: !!animeId,
  });

  const { data: servers = [], isLoading: loadingServers } = useQuery({
    queryKey: ["episode-servers", Number(id)],
    queryFn: () => fetchEpisodeServers(Number(id)),
    enabled: !!id,
  });

  const { data: seasonLabels = [] } = useQuery({
    queryKey: ["season-labels", animeId],
    queryFn: () => fetchSeasonLabels(animeId!),
    enabled: !!animeId,
  });

  // Tous les serveurs TMCooper de l'épisode, puis les anciens ServCey s'ils existent.
  const serverOptions: { value: string; label: string }[] = [
    ...servers.map((s) => ({ value: `srv:${s.id}`, label: s.label })),
    ...(episode?.servcey1_available ? [{ value: "servcey1", label: "ServCey 1" }] : []),
    ...(episode?.servcey2_available ? [{ value: "servcey2", label: "ServCey 2" }] : []),
  ];
  if (!loadingServers && serverOptions.length === 0) {
    serverOptions.push({ value: "auto", label: "Serveur 1" });
  }
  const selectedKey = serverOptions.some((o) => o.value === serverKey)
    ? (serverKey as string)
    : (serverOptions[0]?.value ?? "");
  const selectedServer = servers.find((s) => `srv:${s.id}` === selectedKey);
  const isLegacy = selectedKey === "servcey1" || selectedKey === "servcey2";

  const {
    data: legacyStream,
    isFetched: legacyFetched,
    isError: legacyError,
  } = useQuery({
    queryKey: ["stream", Number(id), selectedKey],
    queryFn: () =>
      isLegacy
        ? getStreamUrl(Number(id), selectedKey as "servcey1" | "servcey2")
        : fetchAutoStream(Number(id)),
    enabled: !!id && !loadingServers && !selectedServer && selectedKey !== "",
    retry: false,
  });

  const playerUrl = selectedServer?.url ?? legacyStream?.url;
  const noSource = !loadingServers && !playerUrl && !selectedServer && (legacyFetched || legacyError);

  if (loadingEp) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!episode) return <Navigate to="/" replace />;

  const seasonLabel =
    seasonLabels.find((s) => s.number === episode.season_number)?.label ?? `Saison ${episode.season_number}`;

  const currentIndex = episodes.findIndex((e) => e.id === episode.id);
  const prev = currentIndex > 0 ? episodes[currentIndex - 1] : null;
  const next = currentIndex >= 0 && currentIndex < episodes.length - 1 ? episodes[currentIndex + 1] : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />

      <div className="pt-16 mx-auto max-w-[1500px] px-0 md:px-6 grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6">
        <div className="min-w-0">
          <div className="relative w-full aspect-video bg-black md:rounded-2xl overflow-hidden">
            {loading && !noSource && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="w-10 h-10 text-primary animate-spin" />
              </div>
            )}
            {playerUrl ? (
              <motion.iframe
                key={`${episode.id}-${selectedKey}-${lang}`}
                src={playerUrl}
                title={`${anime?.title ?? "Anime"} - ${episode.title ?? `Épisode ${episode.episode_number}`}`}
                className="w-full h-full"
                allow="autoplay; encrypted-media; fullscreen"
                allowFullScreen
                onLoad={() => setLoading(false)}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4 }}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-muted-foreground font-body text-sm">
                {noSource ? "Source non disponible pour ce serveur." : ""}
              </div>
            )}
          </div>

          <div className="px-4 md:px-0 mt-4 flex flex-col md:flex-row gap-4 md:items-end md:justify-between">
            <div className="flex flex-wrap gap-5">
              <div>
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold mb-1.5">
                  Serveur
                </p>
                <ToggleGroup2
                  size="sm"
                  value={selectedKey}
                  onChange={(v) => { setServerKey(String(v)); setLoading(true); }}
                  options={serverOptions}
                />
              </div>
              {anime?.languages_available && anime.languages_available.length > 0 && (
                <div>
                  <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold mb-1.5">
                    Langue
                  </p>
                  <ToggleGroup2
                    size="sm"
                    value={lang}
                    onChange={(v) => setLanguage(v as Language)}
                    options={anime.languages_available.map((l) => ({ value: l, label: l }))}
                  />
                </div>
              )}
            </div>

            <div className="flex gap-2">
              <button
                disabled={!prev}
                onClick={() => prev && navigate(`/watch/${prev.id}`)}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:border-primary/40 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
                Précédent
              </button>
              <button
                disabled={!next}
                onClick={() => next && navigate(`/watch/${next.id}`)}
                className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:border-primary/40 transition-colors"
              >
                Suivant
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="px-4 md:px-0 mt-6 flex items-start gap-4">
            <div className="flex-1 min-w-0">
              <h1 className="font-display font-extrabold text-xl md:text-2xl">
                {anime?.title ?? "Anime"}
              </h1>
              <p className="text-muted-foreground font-body mt-1">
                {seasonLabel} — Épisode {episode.episode_number}
                {episode.title ? ` : ${episode.title}` : ""}
              </p>
            </div>
            <button
              onClick={() => setLiked(!liked)}
              className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface border border-border text-sm font-body font-semibold hover:border-primary/40 transition-colors"
            >
              <Heart className={`w-4 h-4 ${liked ? "fill-primary text-primary" : ""}`} />
              {episode.likes_count + (liked ? 1 : 0)}
            </button>
          </div>

          <div className="px-4 md:px-0 mt-8">
            <CommentSection episodeId={episode.id} />
          </div>
        </div>

        <aside className="hidden lg:block">
          <div className="sticky top-20">
            <h3 className="font-display font-bold text-sm mb-3">
              Épisodes — {seasonLabel}
            </h3>
            <div className="space-y-2 max-h-[calc(100vh-6rem)] overflow-y-auto pr-1">
              {episodes.map((ep, i) => (
                <EpisodeCard key={ep.id} episode={ep} anime={anime ?? undefined} index={i} compact />
              ))}
            </div>
          </div>
        </aside>
      </div>

      <Footer />
    </motion.div>
  );
}
