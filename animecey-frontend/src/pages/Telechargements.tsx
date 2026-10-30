import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
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
import { deleteVideo, getPlaybackUrl, listVideos, type OfflineVideo } from "@/lib/offlineDb";
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
  const retryTask = useDownloadsStore((s) => s.retryTask);

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

  const releaseRef = useRef<() => void>(() => undefined);

  const play = async (video: OfflineVideo) => {
    releaseRef.current();
    try {
      const { url, release } = await getPlaybackUrl(video);
      releaseRef.current = release;
      setPlaying(video);
      setPlayingUrl(url);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch {
      releaseRef.current = () => undefined;
      toast.error("Impossible d'ouvrir cet épisode. Supprime-le puis télécharge-le à nouveau.");
    }
  };

  const closePlayer = () => {
    releaseRef.current();
    releaseRef.current = () => undefined;
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
                  {t.status === "error" && (
                    <button
                      onClick={() => retryTask(t.episodeId)}
                      className="shrink-0 inline-flex items-center gap-1.5 h-10 px-4 rounded-full bg-primary text-primary-foreground text-sm font-semibold"
                    >
                      Réessayer
                    </button>
                  )}
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
            <ul className="space-y-2.5">
              {videos.map((v) => (
                <li
                  key={v.episodeId}
                  className="flex items-center gap-3 rounded-2xl bg-surface border border-border-subtle p-2.5 hover:border-primary/40 transition-colors"
                >
                  <button
                    onClick={() => play(v)}
                    aria-label={`Regarder ${v.animeTitle}`}
                    className="relative shrink-0 w-24 sm:w-28 aspect-video rounded-xl overflow-hidden bg-foreground/5"
                  >
                    {v.thumbnailUrl ? (
                      <img src={v.thumbnailUrl} alt="" className="w-full h-full object-cover" loading="lazy" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                        <Play className="w-6 h-6" />
                      </div>
                    )}
                    <span className="absolute inset-0 m-auto w-8 h-8 rounded-full bg-primary/90 text-primary-foreground flex items-center justify-center">
                      <Play className="w-4 h-4 fill-current" />
                    </span>
                  </button>
                  <div className="min-w-0 flex-1">
                    <p className="font-display text-[15px] font-bold leading-snug line-clamp-2">{v.animeTitle}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {v.seasonLabel} · Épisode {v.episodeNumber}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {v.language} · {fmtSize(v.size)}
                    </p>
                  </div>
                  <div className="shrink-0 flex items-center gap-1.5">
                    <button
                      onClick={() => play(v)}
                      className="inline-flex items-center justify-center gap-1.5 h-10 px-4 rounded-full bg-primary text-primary-foreground text-sm font-bold hover:bg-primary-dim transition-colors"
                    >
                      <Play className="w-4 h-4" />
                      <span className="hidden sm:inline">Regarder</span>
                    </button>
                    <button
                      onClick={() => void remove(v.episodeId)}
                      aria-label="Supprimer"
                      className="w-10 h-10 rounded-full border border-border flex items-center justify-center text-muted-foreground hover:text-highlight hover:border-highlight/60 transition-colors"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                    {playing?.episodeId === v.episodeId && <Check className="w-5 h-5 text-primary" />}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <Footer />
    </motion.div>
  );
}
