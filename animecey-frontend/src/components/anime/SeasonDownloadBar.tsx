import { useEffect, useMemo, useState } from "react";
import { CloudDownload, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { useIsApp } from "@/hooks/useIsApp";
import { fmtSize } from "@/lib/fileSize";
import { getWifiOnly, isOnWifi, setWifiOnly } from "@/lib/appPrefs";
import { useDownloadsStore } from "@/stores/downloads";
import type { Episode } from "@/types";

const BATCH = 12;
const HIDE_KEY = "magi:seasonBarHidden";

interface Props {
  episodes: Episode[];
  animeTitle: string;
  seasonNumber: number;
  seasonLabel: string;
  /** octets par épisode, quand connus */
  sizes: Record<number, number>;
}

/**
 * Bandeau « Télécharger les 12 premiers épisodes de la saison N », en bas de l'écran.
 * Visible uniquement dans l'application, et l'utilisateur peut le fermer (il revient au prochain lancement).
 */
export function SeasonDownloadBar({ episodes, animeTitle, seasonNumber, seasonLabel, sizes }: Props) {
  const isApp = useIsApp();
  const enqueue = useDownloadsStore((s) => s.requestDownloads);
  const [hidden, setHidden] = useState(false);
  const [wifiOnly, setWifi] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setWifi(getWifiOnly());
    try {
      setHidden(sessionStorage.getItem(HIDE_KEY) === "1");
    } catch {
      /* ignoré */
    }
  }, []);

  const batch = useMemo(
    () =>
      [...episodes]
        .filter((e) => e.servcey1_available)
        .sort((a, b) => a.episode_number - b.episode_number)
        .slice(0, BATCH),
    [episodes],
  );

  if (!isApp || hidden || batch.length === 0) return null;

  const known = batch.filter((e) => sizes[e.id]);
  const total = known.reduce((acc, e) => acc + sizes[e.id], 0);
  const sizeLabel =
    known.length === 0 ? null : `${known.length < batch.length ? "≈ " : ""}${fmtSize(total)}`;
  const title = batch.length === 1 ? "Télécharger l'épisode de la saison" : `Télécharger les ${batch.length} premiers épisodes`;

  const hide = () => {
    setHidden(true);
    try {
      sessionStorage.setItem(HIDE_KEY, "1");
    } catch {
      /* ignoré */
    }
  };

  const start = async () => {
    if (wifiOnly && !isOnWifi()) {
      toast.error("Tu n'es pas sur le Wi-Fi. Connecte-toi au Wi-Fi ou décoche « Wi-Fi seulement ».");
      return;
    }
    setBusy(true);
    try {
      const n = await enqueue(
        batch.map((e) => ({
          episodeId: e.id,
          animeId: e.anime_id,
          animeTitle,
          episodeNumber: e.episode_number,
          seasonLabel,
          language: e.language,
          thumbnailUrl: e.thumbnail_url,
        })),
      );
      toast.success(
        n > 0
          ? `${n} épisode${n > 1 ? "s" : ""} en téléchargement. Suis-les dans l'onglet Téléchargements.`
          : "Ces épisodes sont déjà téléchargés ou en cours.",
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Téléchargement impossible.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-x-3 z-40 mx-auto max-w-xl rounded-2xl bg-surface border border-primary/40 shadow-xl p-3"
      style={{ bottom: "calc(env(safe-area-inset-bottom) + 78px)" }}
    >
      <button
        onClick={hide}
        aria-label="Fermer"
        className="absolute -top-3 -right-1 w-8 h-8 rounded-full bg-surface-2 border border-border flex items-center justify-center text-muted-foreground"
      >
        <X className="w-4 h-4" />
      </button>
      <button
        onClick={() => void start()}
        disabled={busy}
        className="w-full flex items-center gap-3 text-left disabled:opacity-70"
      >
        <span className="shrink-0 w-11 h-11 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
          {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <CloudDownload className="w-5 h-5" />}
        </span>
        <span className="min-w-0">
          <span className="block font-display font-bold text-sm leading-snug">
            {title} · Saison {seasonNumber}
          </span>
          <span className="block text-xs text-muted-foreground">
            {sizeLabel ? `Environ ${sizeLabel} au total` : "Taille calculée au téléchargement"}
          </span>
        </span>
      </button>
      <label className="mt-2 flex items-center gap-2 text-xs text-muted-foreground select-none">
        <input
          type="checkbox"
          checked={wifiOnly}
          onChange={(e) => {
            setWifi(e.target.checked);
            setWifiOnly(e.target.checked);
          }}
          className="accent-[hsl(var(--primary))] w-4 h-4"
        />
        Wi-Fi seulement
      </label>
    </div>
  );
}
