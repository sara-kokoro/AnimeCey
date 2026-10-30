import { useEffect, useState } from "react";
import { Check, CloudDownload, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { useQuery } from "@tanstack/react-query";
import { fetchEpisodeSizes } from "@/api/episodes";
import { useIsApp } from "@/hooks/useIsApp";
import { fmtSize } from "@/lib/fileSize";
import { getWifiOnly, isOnWifi } from "@/lib/appPrefs";
import { hasVideo } from "@/lib/offlineDb";
import { useDownloadsStore } from "@/stores/downloads";
import type { Episode } from "@/types";

interface Props {
  episode: Episode;
  animeTitle?: string;
  seasonLabel: string;
  /** octets : number = connu, null = inconnu (le parent s'en charge), absent = le bouton le demande lui-même */
  size?: number | null;
  /** petit bouton pour les listes */
  compact?: boolean;
}

/**
 * Bouton « Hors ligne » : ouvre la pub RichAds (lien direct) dans un nouvel onglet,
 * puis ajoute l'épisode à la file de téléchargement interne de l'app.
 * Visible uniquement quand l'épisode existe en fichier direct (ServCey 1).
 */
export function OfflineDownloadButton({ episode, animeTitle, seasonLabel, size, compact = false }: Props) {
  const isApp = useIsApp();
  const enqueue = useDownloadsStore((s) => s.requestDownloads);
  const removeTask = useDownloadsStore((s) => s.removeTask);
  const retryTask = useDownloadsStore((s) => s.retryTask);
  const task = useDownloadsStore((s) => s.tasks.find((t) => t.episodeId === episode.id));
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void hasVideo(episode.id).then((v) => !cancelled && setSaved(v));
    return () => {
      cancelled = true;
    };
  }, [episode.id, task?.status]);

  const { data: ownSizes } = useQuery({
    queryKey: ["episode-size", episode.id],
    queryFn: () => fetchEpisodeSizes([episode.id]),
    enabled: isApp && size === undefined && episode.servcey1_available,
    staleTime: 60 * 60_000,
  });
  const bytes = size === undefined ? ownSizes?.[episode.id] : (size ?? undefined);

  if (!episode.servcey1_available) return null;

  const onClick = async () => {
    if (saved || task?.status === "done") {
      toast.info("Cet épisode est déjà dans tes téléchargements.");
      return;
    }
    if (task?.status === "error") {
      retryTask(episode.id);
      return;
    }
    if (task) {
      toast.info("Cet épisode est déjà dans la file de téléchargement.");
      return;
    }
    if (isApp && getWifiOnly() && !isOnWifi()) {
      toast.error("Tu n'es pas sur le Wi-Fi. Connecte-toi au Wi-Fi ou désactive « Wi-Fi seulement » (bandeau de la saison).");
      return;
    }
    await enqueue([
      {
        episodeId: episode.id,
        animeId: episode.anime_id,
        animeTitle: animeTitle ?? "Anime",
        episodeNumber: episode.episode_number,
        seasonLabel,
        language: episode.language,
        thumbnailUrl: episode.thumbnail_url,
      },
    ]).catch((e) => toast.error(e instanceof Error ? e.message : "Téléchargement impossible."));
  };

  const busy = task?.status === "downloading" || task?.status === "pending";
  const done = saved || task?.status === "done";

  return (
    <span className="inline-flex items-center gap-1">
    <button
      onClick={onClick}
      disabled={busy}
      className={
        (isApp && !done && !busy
          ? "bg-primary text-primary-foreground border border-primary hover:bg-primary-dim "
          : "bg-surface border border-border hover:border-primary/40 ") +
        (compact ? "px-2.5 py-1.5 text-xs " : "px-3 py-2 text-sm ") +
        "inline-flex items-center gap-1.5 rounded-lg font-body font-semibold transition-colors disabled:opacity-60"
      }
    >
      {busy ? (
        <Loader2 className="w-4 h-4 animate-spin text-primary" />
      ) : done ? (
        <Check className="w-4 h-4 text-primary" />
      ) : (
        <CloudDownload className="w-4 h-4" />
      )}
      {busy
        ? task?.status === "downloading"
          ? `${task.progress}%`
          : "En attente"
        : done
          ? "Disponible"
          : task?.status === "error"
            ? "Réessayer"
            : isApp
              ? bytes
                ? `Télécharger · ${fmtSize(bytes)}`
                : "Télécharger"
              : "Hors ligne"}
    </button>
    {busy && (
      <button
        onClick={() => {
          removeTask(episode.id);
          toast.info("Téléchargement annulé.");
        }}
        aria-label="Annuler le téléchargement"
        className="inline-flex items-center gap-1 px-3 py-2 rounded-lg bg-surface border border-border text-sm font-semibold hover:border-destructive/60"
      >
        <X className="w-4 h-4" /> Annuler
      </button>
    )}
    </span>
  );
}
