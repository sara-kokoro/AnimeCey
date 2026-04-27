import { useParams, Navigate, Link, useNavigate } from "react-router-dom";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight, Heart, Loader2 } from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { ToggleGroup2 } from "@/components/ui/ToggleGroup2";
import { EpisodeCard } from "@/components/anime/EpisodeCard";
import { CommentSection } from "@/components/comments/CommentSection";
import { getEpisodeById, getEpisodes } from "@/data/mock";
import type { Language } from "@/types";

export default function Watch() {
  const { id } = useParams();
  const navigate = useNavigate();
  const data = getEpisodeById(Number(id));

  const [serveur, setServeur] = useState<"servcey1" | "servcey2">("servcey1");
  const [language, setLanguage] = useState<Language | null>(null);
  const [liked, setLiked] = useState(false);
  const [loading, setLoading] = useState(true);

  const lang = (language ?? data?.episode.language) as Language;

  const episodes = useMemo(() => {
    if (!data) return [];
    return getEpisodes(data.anime.id, lang, data.episode.season_number);
  }, [data, lang]);

  if (!data) return <Navigate to="/" replace />;
  const { episode, anime } = data;

  const currentIndex = episodes.findIndex((e) => e.episode_number === episode.episode_number);
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
          {/* Player */}
          <div className="relative w-full aspect-video bg-black md:rounded-2xl overflow-hidden">
            {loading && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className="w-10 h-10 text-primary animate-spin" />
              </div>
            )}
            <motion.iframe
              key={`${episode.id}-${serveur}-${lang}`}
              src="about:blank"
              title={`${anime.title} - ${episode.title}`}
              className="w-full h-full"
              allow="autoplay; encrypted-media; fullscreen"
              allowFullScreen
              onLoad={() => setLoading(false)}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.4 }}
            />
          </div>

          {/* Controls */}
          <div className="px-4 md:px-0 mt-4 flex flex-col md:flex-row gap-4 md:items-end md:justify-between">
            <div className="flex flex-wrap gap-5">
              <div>
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground font-body font-semibold mb-1.5">
                  Serveur
                </p>
                <ToggleGroup2
                  size="sm"
                  value={serveur}
                  onChange={(v) => setServeur(v as "servcey1" | "servcey2")}
                  options={[
                    { value: "servcey1", label: "ServCey 1" },
                    { value: "servcey2", label: "ServCey 2" },
                  ]}
                />
              </div>
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

          {/* Episode info */}
          <div className="px-4 md:px-0 mt-6">
            <Link to={`/anime/${anime.id}`} className="font-display font-bold text-xl text-foreground hover:text-primary transition-colors">
              {anime.title}
            </Link>
            <p className="text-sm text-muted-foreground font-body mt-1">
              Saison {episode.season_number} — Épisode {episode.episode_number} — {lang}
            </p>
            {episode.title && (
              <h2 className="font-display font-semibold text-base mt-1.5">
                {episode.title}
              </h2>
            )}

            <button
              onClick={() => setLiked((v) => !v)}
              className="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-surface border border-border font-body font-semibold text-sm hover:border-primary/40 transition-colors"
            >
              <motion.span
                key={String(liked)}
                initial={{ scale: 0.6 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 400, damping: 14 }}
                className="inline-flex"
              >
                <Heart className={`w-4 h-4 ${liked ? "fill-primary text-primary" : ""}`} />
              </motion.span>
              {episode.likes_count + (liked ? 1 : 0)}
            </button>
          </div>

          <CommentSection episodeId={episode.id} />
        </div>

        {/* Sidebar episodes */}
        <aside className="px-4 md:px-0">
          <div className="lg:sticky lg:top-20 bg-surface lg:bg-transparent rounded-2xl lg:rounded-none p-3 lg:p-0">
            <h3 className="font-display font-bold text-base mb-3 px-1">
              Épisodes — Saison {episode.season_number}
            </h3>
            <div className="lg:max-h-[calc(100vh-160px)] lg:overflow-y-auto pr-1 space-y-1">
              {episodes.map((ep) => (
                <EpisodeCard
                  key={ep.id}
                  episode={ep}
                  compact
                  active={ep.id === episode.id}
                />
              ))}
            </div>
          </div>
        </aside>
      </div>

      <Footer />
    </motion.div>
  );
}