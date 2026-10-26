import { useCallback, useEffect, useState } from "react";
import { Link } from "@/lib/router";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  Check,
  CloudDownload,
  Loader2,
  Play,
  Trash2,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { Navbar } from "@/components/layout/Navbar";
import { Footer } from "@/components/layout/Footer";
import { ServCeyPlayer } from "@/components/player/ServCeyPlayer";
import { deleteVideo, listVideos, type OfflineVideo } from "@/lib/offlineDb";
import { useDownloadsStore } from "@/stores/downloads";

function fmtSize(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} Go`;
  if (bytes >= 1_000_000) return `${Math.round(bytes / 1_000_000)} Mo`;
  return `${Math.round(bytes / 1024)} Ko`;
}

export default function Telechargements() {
  const [videos, setVideos] = useState<OfflineVideo[]>([]);
  const [playing, setPlaying] = useState<OfflineVideo | null>(null);
  const [playingUrl, setPlayingUrl] = useState<string | null>(null);
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);

  const tasks = useDownloadsStore((s) => s.tasks);
  const removeTask = useDownloadsStore((s) => s.removeTask);

  const refresh = useCallback(async () => {
    try {
      setVideos(await listVideos());
    } catch {
      setVideos([]);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh, tasks]);

  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  const play = (video: OfflineVideo) => {
    if (playingUrl) URL.revokeObjectURL(playingUrl);
    const url = URL.createObjectURL(video.blob);
    setPlaying(video);
    setPlayingUrl(url);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const closePlayer = () => {
    if (playingUrl) URL.revokeObjectURL(playingUrl);
    setPlaying(null);
    setPlayingUrl(null);
  };

  const remove = async (episodeId: number) => {
    await deleteVideo(episodeId);
    if (playing?.episodeId === episodeId) closePlayer();
    await refresh();
  };

  const activeTasks = tasks.filter((t) => t.status === "pending" || t.status === "downloading" || t.status === "error");
  const totalSize = videos.reduce((acc, v) => acc + v.size, 0);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="min-h-screen bg-background"
    >
      <Navbar />

      <div className="pt-20 pb-10 mx-auto max-w-5xl px-4 md:px-6">
        <div className="flex items-center justify-between gap-3">
          <h1 className="font-display font-extrabold text-2xl md:text-3xl">Mes Téléchargements</h1>
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold ${
              online ? "bg-foreground/10 text-muted-foreground" : "bg-primary/15 text-primary"
            }`}
          >
            {online ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            {online ? "En ligne" : "Hors ligne"}
          </span>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Tes épisodes sont gardés dans l'application : regarde-les même sans internet.
          {videos.length > 0 && ` · ${videos.length} épisode${videos.length > 1 ? "s" : ""} · ${fmtSize(totalSize)}`}
        </p>

        {/* Lecteur hors ligne */}
        {playing && playingUrl && (
          <div className="mt-6">
            <div className="relative w-full aspect-video bg-background rounded-2xl overflow-hidden ring-1 ring-border">
              <ServCeyPlayer
                key={`offline-${playing.episodeId}`}
                src={playingUrl}
                title={playing.animeTitle}
                subtitle={`${playing.seasonLabel} — Épisode ${playing.episodeNumber} · ${playing.language}`}
                storageKey={`offline-${playing.episodeId}`}
              />
            </div>
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="font-body font-semibold text-sm truncate">
                {playing.animeTitle} — Épisode {playing.episodeNumber}
              </p>
              <button
                onClick={closePlayer}
                className="shrink-0 inline-flex items-center gap-1.5 h-9 px-4 rounded-full bg-surface border border-border-subtle text-sm font-semibold hover:bg-surface-2 transition-colors"
              >
                <X className="w-4 h-4" />
                Fermer
              </button>
            </div>
          </div>
        )}

        {/* File d'attente */}
        {activeTasks.length > 0 && (
          <section className="mt-8">
            <h2 className="font-display font-bold text-lg mb-3">File de téléchargement</h2>
            <ul className="space-y-2">
              {activeTasks.map((t) => (
                <li
                  key={t.episodeId}
                  className="flex items-center gap-3 rounded-2xl bg-surface border border-border-subtle p-4"
                >
                  <div className="w-12 h-12 rounded-xl bg-primary/15 text-primary flex items-center justify-center shrink-0">
                    {t.status === "downloading" ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : t.status === "error" ? (
                      <AlertTriangle className="w-5 h-5 text-highlight" />
                    ) : (
                      <CloudDownload className="w-5 h-5" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-base font-bold truncate">
                      {t.animeTitle} — Épisode {t.episodeNumber}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t.status === "downloading"
                        ? `Téléchargement… ${t.progress}%`
                        : t.status === "error"
                          ? (t.error ?? "Erreur")
                          : "En attente"}
                    </p>
                    {t.status === "downloading" && (
                      <div className="mt-2 h-2.5 rounded-full bg-foreground/10 overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all duration-300"
                          style={{ width: `${t.progress}%` }}
                        />
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => removeTask(t.episodeId)}
                    aria-label="Annuler le téléchargement"
                    className="shrink-0 inline-flex items-center gap-1.5 h-10 px-4 rounded-full border border-border text-sm font-semibold hover:border-highlight/60 hover:text-highlight"
                  >
                    <X className="w-4 h-4" /> Annuler
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Bibliothèque hors ligne */}
        <section className="mt-8">
          {videos.length === 0 && activeTasks.length === 0 ? (
            <div className="mt-6 flex flex-col items-center text-center rounded-3xl border border-dashed border-border-subtle bg-surface/50 px-6 py-14">
              <div className="w-16 h-16 rounded-full bg-primary/15 text-primary flex items-center justify-center">
                <CloudDownload className="w-8 h-8" />
              </div>
              <h2 className="mt-4 font-display font-bold text-lg">Aucun téléchargement</h2>
              <p className="mt-1 max-w-sm text-sm text-muted-foreground">
                Sur la page d'un épisode, touche « Hors ligne » pour le garder dans l'application et le regarder sans
                internet.
              </p>
              <Link
                to="/catalogue"
                className="mt-5 inline-flex items-center justify-center rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary-dim"
              >
                Parcourir le catalogue
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {videos.map((v) => (
                <div
                  key={v.episodeId}
                  className="rounded-3xl bg-surface border border-border-subtle overflow-hidden hover:border-primary/40 transition-colors"
                >
                  <button onClick={() => play(v)} className="relative block w-full aspect-video bg-foreground/5">
                    {v.thumbnailUrl ? (
                      <img src={v.thumbnailUrl} alt="" className="w-full h-full object-cover" loading="lazy" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                        <Play className="w-10 h-10" />
                      </div>
                    )}
                    <span className="absolute -bottom-4 left-2 font-display font-black text-8xl leading-none text-foreground/20 pointer-events-none">
                      {v.episodeNumber}
                    </span>
                    <span className="absolute top-2 right-2 px-2 py-1 rounded-md bg-background/80 text-xs font-bold">
                      {v.language}
                    </span>
                    <span className="absolute inset-0 m-auto w-16 h-16 rounded-full bg-primary text-primary-foreground flex items-center justify-center shadow-glow">
                      <Play className="w-7 h-7 fill-current" />
                    </span>
                  </button>
                  <div className="p-4">
                    <p className="font-display text-lg font-bold truncate">{v.animeTitle}</p>
                    <p className="text-sm text-muted-foreground truncate">
                      {v.seasonLabel} · Épisode {v.episodeNumber} · {fmtSize(v.size)}
                    </p>
                    <div className="mt-4 flex items-center gap-2">
                      <button
                        onClick={() => play(v)}
                        className="flex-1 inline-flex items-center justify-center gap-2 h-11 rounded-full bg-primary text-primary-foreground font-bold hover:bg-primary-dim transition-colors"
                      >
                        <Play className="w-4 h-4" />
                        Regarder
                      </button>
                      <button
                        onClick={() => void remove(v.episodeId)}
                        aria-label="Supprimer"
                        className="w-11 h-11 rounded-full border border-border flex items-center justify-center text-muted-foreground hover:text-highlight hover:border-highlight/60 transition-colors"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                      {playing?.episodeId === v.episodeId && <Check className="w-5 h-5 text-primary" />}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      <Footer />
    </motion.div>
  );
}
