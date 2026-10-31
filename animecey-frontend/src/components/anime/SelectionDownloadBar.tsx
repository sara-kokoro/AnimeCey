import { useEffect, useState } from "react";
import { CloudDownload, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { fmtSize } from "@/lib/fileSize";
import { getWifiOnly, isOnWifi, setWifiOnly } from "@/lib/appPrefs";
import { useDownloadsStore, type NewDownloadTask } from "@/stores/downloads";

export const MAX_SELECTION = 10;

export interface Picked {
  task: NewDownloadTask;
  size?: number;
}

/**
 * Barre « Télécharger (N/10) » : télécharge les épisodes cochés, même s'ils viennent de plusieurs saisons.
 */
export function SelectionDownloadBar({
  picked,
  onCancel,
  onDone,
}: {
  picked: Picked[];
  onCancel: () => void;
  onDone: () => void;
}) {
  const enqueue = useDownloadsStore((s) => s.requestDownloads);
  const [wifiOnly, setWifi] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => setWifi(getWifiOnly()), []);

  const known = picked.filter((p) => p.size);
  const total = known.reduce((a, p) => a + (p.size ?? 0), 0);
  const label = known.length ? `${known.length < picked.length ? "≈ " : ""}${fmtSize(total)}` : null;

  const start = async () => {
    if (picked.length === 0) return;
    if (wifiOnly && !isOnWifi()) {
      toast.error("Tu n'es pas sur le Wi-Fi. Connecte-toi au Wi-Fi ou décoche « Wi-Fi seulement ».");
      return;
    }
    setBusy(true);
    try {
      const n = await enqueue(picked.map((p) => p.task));
      toast.success(n > 0 ? `${n} épisode${n > 1 ? "s" : ""} en téléchargement.` : "Déjà téléchargés ou en cours.");
      onDone();
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
      <div className="flex items-center gap-2">
        <button
          onClick={onCancel}
          aria-label="Annuler la sélection"
          className="shrink-0 w-10 h-10 rounded-full border border-border flex items-center justify-center text-muted-foreground"
        >
          <X className="w-5 h-5" />
        </button>
        <button
          onClick={() => void start()}
          disabled={busy || picked.length === 0}
          className="flex-1 min-w-0 h-12 rounded-full bg-primary text-primary-foreground font-bold flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {busy ? <Loader2 className="w-5 h-5 animate-spin" /> : <CloudDownload className="w-5 h-5" />}
          <span className="truncate">
            Télécharger ({picked.length}/{MAX_SELECTION}){label ? ` · ${label}` : ""}
          </span>
        </button>
      </div>
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
