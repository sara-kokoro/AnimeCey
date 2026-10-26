import { useEffect, useRef, useState } from "react";
import { Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { RICHADS } from "@/config/ads";
import { requiredDownloadAds, useDownloadsStore } from "@/stores/downloads";

/* eslint-disable @typescript-eslint/no-explicit-any */
const IMA_SRC = "https://imasdk.googleapis.com/js/sdkloader/ima3.js";
const START_TIMEOUT_MS = 12000; // une pub qui ne démarre pas : on passe à la suivante
const MAX_AD_MS = 60000; // sécurité par pub

function loadIma(): Promise<any> {
  const w = window as any;
  if (w.google?.ima) return Promise.resolve(w.google.ima);
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    const t = window.setTimeout(() => reject(new Error("timeout")), 8000);
    s.onload = () => {
      window.clearTimeout(t);
      w.google?.ima ? resolve(w.google.ima) : reject(new Error("ima"));
    };
    s.onerror = () => {
      window.clearTimeout(t);
      reject(new Error("blocked"));
    };
    s.src = IMA_SRC;
    s.async = true;
    document.head.appendChild(s);
  });
}

/** Joue une pub VAST dans la boîte donnée. Se résout à la fin, en erreur ou au délai dépassé. */
function playOneAd(ima: any, box: HTMLDivElement, video: HTMLVideoElement, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    let manager: any = null;
    let finished = false;
    const timers: number[] = [];
    const display = new ima.AdDisplayContainer(box, video);
    const loader = new ima.AdsLoader(display);
    const end = () => {
      if (finished) return;
      finished = true;
      timers.forEach((t) => window.clearTimeout(t));
      try { manager?.destroy(); } catch { /* ignore */ }
      try { loader.destroy(); display.destroy(); } catch { /* ignore */ }
      box.innerHTML = "";
      resolve();
    };
    signal.addEventListener("abort", end);
    timers.push(window.setTimeout(end, START_TIMEOUT_MS));
    loader.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, end);
    loader.addEventListener(ima.AdsManagerLoadedEvent.Type.ADS_MANAGER_LOADED, (e: any) => {
      manager = e.getAdsManager(video);
      manager.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, end);
      manager.addEventListener(ima.AdEvent.Type.ALL_ADS_COMPLETED, end);
      manager.addEventListener(ima.AdEvent.Type.SKIPPED, end);
      manager.addEventListener(ima.AdEvent.Type.STARTED, () => {
        timers.forEach((t) => window.clearTimeout(t));
        timers.push(window.setTimeout(end, MAX_AD_MS));
      });
      try {
        manager.init(box.clientWidth, box.clientHeight, ima.ViewMode.NORMAL);
        manager.start();
      } catch {
        end();
      }
    });
    display.initialize();
    const req = new ima.AdsRequest();
    const sep = RICHADS.vastTag.includes("?") ? "&" : "?";
    req.adTagUrl = `${RICHADS.vastTag.trim()}${sep}cb=${Date.now()}`;
    req.linearAdSlotWidth = box.clientWidth;
    req.linearAdSlotHeight = box.clientHeight;
    loader.requestAds(req);
  });
}

/**
 * Fenêtre plein écran des pubs vidéo RichAds avant téléchargement.
 * 1 pub pour un épisode, 3 pubs enchaînées pour une sélection ; ensuite la file démarre.
 */
export function DownloadAdModal() {
  const batch = useDownloadsStore((s) => s.adBatch);
  const cancelAds = useDownloadsStore((s) => s.cancelAds);
  const completeAds = useDownloadsStore((s) => s.completeAds);
  const boxRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [current, setCurrent] = useState(1);

  const total = batch ? requiredDownloadAds(batch.items.length) : 0;

  useEffect(() => {
    if (!batch || batch.items.length === 0) return;
    const ctrl = new AbortController();
    const id = batch.id;
    (async () => {
      try {
        const ima = await loadIma();
        for (let i = 1; i <= total; i++) {
          if (ctrl.signal.aborted) return;
          setCurrent(i);
          await playOneAd(ima, boxRef.current!, videoRef.current!, ctrl.signal);
        }
      } catch {
        /* SDK bloqué : on lance quand même le téléchargement */
      }
      if (ctrl.signal.aborted) return;
      const n = await completeAds(id);
      if (n > 0) toast.success(`${n} épisode${n > 1 ? "s" : ""} en téléchargement.`);
    })();
    return () => ctrl.abort();
  }, [batch?.id, batch?.items.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!batch || batch.items.length === 0) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-background flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-4xl flex items-center justify-between mb-3">
        <p className="font-display text-lg font-bold">
          Publicité <span className="text-primary">{current}/{total}</span>
        </p>
        <button
          onClick={cancelAds}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border border-border bg-surface font-semibold hover:border-destructive/60"
        >
          <X className="w-4 h-4" /> Annuler
        </button>
      </div>
      <div className="relative w-full max-w-4xl aspect-video bg-card rounded-xl overflow-hidden">
        <video ref={videoRef} playsInline muted={false} className="absolute inset-0 w-full h-full" />
        <div ref={boxRef} className="absolute inset-0" />
        <Loader2 className="absolute inset-0 m-auto w-8 h-8 animate-spin text-primary pointer-events-none -z-0" />
      </div>
      <p className="mt-4 text-sm text-muted-foreground text-center">
        Tes {batch.items.length} épisode{batch.items.length > 1 ? "s" : ""} se téléchargeront automatiquement après {total > 1 ? "les pubs" : "la pub"}.
      </p>
    </div>
  );
}
