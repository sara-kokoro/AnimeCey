import { useEffect, useState } from "react";
import { Download, X } from "lucide-react";
import { APP } from "@/config/app";
import { useIsApp } from "@/hooks/useIsApp";

/* eslint-disable @typescript-eslint/no-explicit-any */
const SEEN_KEY = "magi:updateSeen";

/**
 * Application Android : affiche « Nouvelle version disponible » quand le dernier APK publié
 * (numéro de build dans la description de la release GitHub) est plus récent que celui installé.
 * Ne fait rien dans le navigateur, ni hors connexion.
 */
export function UpdateNotice() {
  const isApp = useIsApp();
  const [latest, setLatest] = useState(0);

  useEffect(() => {
    if (!isApp) return;
    const native = (window as any).MagiNative;
    const installed = Number(native?.appVersion?.() ?? 0);
    if (!installed || !navigator.onLine) return;
    let cancelled = false;
    void fetch(APP.releaseApi, { headers: { Accept: "application/vnd.github+json" } })
      .then((r) => (r.ok ? r.json() : null))
      .then((rel: { body?: string } | null) => {
        const m = /build\s+(\d+)/i.exec(rel?.body ?? "");
        const n = m ? Number(m[1]) : 0;
        if (cancelled || !n || n <= installed) return;
        let seen = 0;
        try {
          seen = Number(sessionStorage.getItem(SEEN_KEY) ?? 0);
        } catch {
          /* ignoré */
        }
        if (seen !== n) setLatest(n);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [isApp]);

  if (!latest) return null;

  const dismiss = () => {
    try {
      sessionStorage.setItem(SEEN_KEY, String(latest));
    } catch {
      /* ignoré */
    }
    setLatest(0);
  };

  return (
    <div
      className="fixed inset-x-3 top-3 z-50 mx-auto max-w-xl rounded-2xl bg-surface border border-primary/50 shadow-xl p-3 flex items-center gap-3"
      style={{ top: "calc(env(safe-area-inset-top) + 12px)" }}
    >
      <span className="shrink-0 w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
        <Download className="w-5 h-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-display font-bold text-sm leading-snug">Nouvelle version disponible</p>
        <p className="text-xs text-muted-foreground">Mets l'application à jour pour profiter des nouveautés.</p>
      </div>
      <button
        onClick={() => {
          (window as any).MagiNative?.openExternal?.(APP.apkUrl);
          dismiss();
        }}
        className="shrink-0 h-9 px-4 rounded-full bg-primary text-primary-foreground text-sm font-bold"
      >
        Mettre à jour
      </button>
      <button onClick={dismiss} aria-label="Plus tard" className="shrink-0 text-muted-foreground">
        <X className="w-5 h-5" />
      </button>
    </div>
  );
}
