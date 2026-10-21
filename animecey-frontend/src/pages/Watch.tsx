import { useParams, Navigate, Link, useNavigate } from "@/lib/router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Heart, Languages, LayoutGrid, List, Loader2, Server, SkipBack, SkipForward } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { ServCeyPlayer } from "@/components/player/ServCeyPlayer";
import { DownloadButton } from "@/components/player/DownloadButton";
import { MultiTagAd } from "@/components/ads/MultiTagAd";
import { VastGate } from "@/components/ads/VastGate";
import { BannerAd } from "@/components/ads/BannerAd";
import { AdsterraBanner } from "@/components/ads/AdsterraBanner";
import { EpisodeCard } from "@/components/anime/EpisodeCard";
import { CommentSection } from "@/components/comments/CommentSection";
import { fetchEpisode, fetchEpisodes, fetchLikeStatus, getStreamUrl, likeEpisode, unlikeEpisode } from "@/api/episodes";
import { fetchAnime } from "@/api/animes";
import { ReportButton } from "@/components/report/ReportButton";
import { fetchAutoStream, fetchEpisodeServers, fetchSeasonLabels } from "@/api/catalog";
import type { Language } from "@/types";

export default function Watch() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [serverKey, setServerKey] = useState<string | null>(null);
  const [language, setLanguage] = useState<Language | null>(null);
  const [liked, setLiked] = useState(false);
  const [likes, setLikes] = useState(0);
  const [loading, setLoading] = useState(true);
  const [langNotice, setLangNotice] = useState<string | null>(null);
  const [view, setView] = useState<"list" | "grid">("list");

  const { data: episode, isLoading: loadingEp } = useQuery({
    queryKey: ["episode", Number(id)],
    queryFn: () => fetchEpisode(Number(id)),
    enabled: !!id,
  });

  // Le cœur : on lit l'état enregistré (compte ou adresse IP), puis on enregistre chaque clic.
  useEffect(() => {
    if (!episode) return;
    setLikes(episode.likes_count);
    setLiked(false);
    let cancelled = false;
    fetchLikeStatus(episode.id)
      .then((r) => {
        if (cancelled) return;
        setLiked(r.liked);
        setLikes(r.likes_count);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [episode?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleLike = async () => {
    if (!episode) return;
    const before = { liked, likes };
    setLiked(!liked);
    setLikes(Math.max(0, likes + (liked ? -1 : 1)));
    try {
      const r = liked ? await unlikeEpisode(episode.id) : await likeEpisode(episode.id);
      setLiked(r.liked);
      setLikes(r.likes_count);
    } catch {
      setLiked(before.liked);
      setLikes(before.likes);
    }
  };

  const animeId = episode?.anime_id;
  const { data: anime } = useQuery({
    queryKey: ["anime", animeId],
    queryFn: () => fetchAnime(animeId!),
    enabled: !!animeId,
  });

  const lang = (language ?? episode?.language ?? "VOSTFR") as Language;
  const seasonNum = episode?.season_number ?? 1;

  // Changer de langue = ouvrir le même épisode dans l'autre langue (autre ligne en base).
  const switchLanguage = async (l: Language) => {
    setLangNotice(null);
    if (!episode || !animeId || l === episode.language) {
      setLanguage(l);
      return;
    }
    try {
      const list = await fetchEpisodes(animeId, l, seasonNum);
      const match = list.find((e) => e.episode_number === episode.episode_number);
      if (match) {
        setLanguage(l);
        setLoading(true);
        navigate(`/watch/${match.id}`);
      } else {
        setLangNotice(`L'épisode ${episode.episode_number} n'est pas encore disponible en ${l}.`);
      }
    } catch {
      setLangNotice("Impossible de changer de langue pour le moment.");
    }
  };

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
    // ServCey 1 (nos fichiers, sans pub) passe en premier quand il existe.
    ...(episode?.servcey1_available ? [{ value: "servcey1", label: "ServCey 1" }] : []),
    ...servers.map((s) => ({ value: `srv:${s.id}`, label: s.label })),
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
    staleTime: 60 * 60 * 1000, // le lien signé vit 6 à 12 h : inutile de le redemander
    refetchOnWindowFocus: false,
  });

  const playerUrl = selectedServer?.url ?? legacyStream?.url;
  // Fichier direct (ServCey 1 via Telegram) : lecteur <video> natif, aucune pub.
  const isDirectVideo = !selectedServer && (legacyStream as { type?: string } | undefined)?.type === "mp4";
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

  const pillBtn =
    "inline-flex items-center justify-center gap-1.5 h-10 px-4 rounded-full bg-surface border border-border-subtle text-sm font-semibold hover:bg-surface-2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />
      <MultiTagAd />

      <div className="pt-16 mx-auto max-w-6xl md:px-6">
        <div className="relative w-full aspect-video bg-background md:rounded-2xl overflow-hidden md:mt-4 ring-1 ring-border">
          {loading && !noSource && !isDirectVideo && (
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className="w-10 h-10 text-primary animate-spin" />
            </div>
          )}
          <VastGate key={episode.id}>
          {playerUrl && isDirectVideo ? (
            <ServCeyPlayer
              key={`${episode.id}-${selectedKey}-${lang}`}
              src={playerUrl}
              title={anime?.title ?? "Anime"}
              subtitle={`${seasonLabel} — Épisode ${episode.episode_number} · ${episode.language}`}
              storageKey={String(episode.id)}
              onReady={() => setLoading(false)}
              hasNext={!!next}
              onNext={() => next && navigate(`/watch/${next.id}`)}
            />
          ) : playerUrl ? (
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
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground text-sm">
              {noSource ? "Source non disponible pour ce serveur." : ""}
            </div>
          )}
          </VastGate>
        </div>

        <div className="px-4 md:px-0">
          {/* Titre */}
          <div className="mt-5">
            {anime && (
              <Link to={`/anime/${anime.id}`} className="text-xs font-bold uppercase tracking-wider text-primary hover:text-primary-dim">
                {anime.title}
              </Link>
            )}
            <h1 className="mt-1 font-display font-extrabold text-xl md:text-3xl leading-tight">
              Épisode {episode.episode_number}
              {episode.title ? ` : ${episode.title}` : ""}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
              <span className="px-2.5 py-1 rounded-full bg-foreground/10 font-semibold">{seasonLabel}</span>
              <span className="px-2.5 py-1 rounded-full bg-primary/15 text-primary font-semibold">{episode.language}</span>
            </div>
          </div>

          {/* Commandes rapides */}
          <div className="mt-4 flex gap-2 overflow-x-auto no-scrollbar -mx-4 px-4 md:mx-0 md:px-0">
            <button disabled={!prev} onClick={() => prev && navigate(`/watch/${prev.id}`)} className={pillBtn + " shrink-0"}>
              <SkipBack className="w-4 h-4" />
              Précédent
            </button>
            <button
              disabled={!next}
              onClick={() => next && navigate(`/watch/${next.id}`)}
              className="shrink-0 inline-flex items-center justify-center gap-1.5 h-10 px-4 rounded-full bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary-dim transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Suivant
              <SkipForward className="w-4 h-4" />
            </button>
            <button onClick={toggleLike} className={pillBtn + " shrink-0"} aria-pressed={liked}>
              <Heart className={`w-4 h-4 ${liked ? "fill-highlight text-highlight" : ""}`} />
              {likes}
            </button>
            <div className="shrink-0">
              <DownloadButton episodeId={episode.id} />
            </div>
            <div className="shrink-0">
              <ReportButton episodeId={episode.id} animeId={anime?.id} label="Signaler" />
            </div>
          </div>

          {/* Langues + serveurs */}
          <div className="mt-5 rounded-2xl bg-surface border border-border-subtle p-4 space-y-4">
            {anime?.languages_available && anime.languages_available.length > 0 && (
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2 inline-flex items-center gap-1.5">
                  <Languages className="w-3.5 h-3.5" /> Langue
                </p>
                <ToggleGroup2
                  size="sm"
                  value={lang}
                  onChange={(v) => switchLanguage(v as Language)}
                  options={anime.languages_available.map((l) => ({ value: l, label: l }))}
                />
                {langNotice && <p className="text-xs text-muted-foreground mt-1.5">{langNotice}</p>}
              </div>
            )}
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2 inline-flex items-center gap-1.5">
                <Server className="w-3.5 h-3.5" /> Serveur
              </p>
              <ToggleGroup2
                size="sm"
                value={selectedKey}
                onChange={(v) => { setServerKey(String(v)); setLoading(true); }}
                options={serverOptions}
              />
            </div>
          </div>

          {/* Épisodes */}
          <section className="mt-8">
            <div className="flex items-center justify-between gap-3 mb-3">
              <h2 className="font-display font-bold text-lg">
                Épisodes <span className="text-muted-foreground font-normal text-sm">· {seasonLabel}</span>
              </h2>
              <div className="flex rounded-full bg-surface border border-border-subtle p-1">
                <button
                  onClick={() => setView("list")}
                  aria-label="Mode liste"
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${view === "list" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
                >
                  <List className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setView("grid")}
                  aria-label="Mode grille"
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${view === "grid" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
                >
                  <LayoutGrid className="w-4 h-4" />
                </button>
              </div>
            </div>
            {view === "list" ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {episodes.map((ep, i) => (
                  <EpisodeCard key={ep.id} episode={ep} seasonLabel={seasonLabel} index={i} active={ep.id === episode.id} compact />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {episodes.map((ep, i) => (
                  <EpisodeCard key={ep.id} episode={ep} variant="grid" index={i} active={ep.id === episode.id} />
                ))}
              </div>
            )}
          </section>

          <AdsterraBanner format="native" className="mt-8" />

          <div className="mt-8">
            <CommentSection episodeId={episode.id} />
          </div>
        </div>
      </div>

      <Footer />
    </motion.div>
  );
}
