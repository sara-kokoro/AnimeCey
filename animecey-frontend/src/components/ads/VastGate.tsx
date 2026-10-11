import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Loader2, Play } from "lucide-react";
import { VAST } from "@/config/ads";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Ima = any;

const IMA_SRC = "https://imasdk.googleapis.com/js/sdkloader/ima3.js";
const LAST_KEY = "vast:last";
const SCRIPT_TIMEOUT_MS = 6000; // le SDK ne charge pas (bloqueur de pub, réseau) : on laisse regarder
const START_TIMEOUT_MS = 10000; // aucune pub ne démarre : on laisse regarder
const MAX_AD_MS = 60000; // sécurité : une pub ne bloque jamais la vidéo plus d'une minute

function loadIma(): Promise<Ima> {
  const w = window as any;
  if (w.google?.ima) return Promise.resolve(w.google.ima);
  return new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${IMA_SRC}"]`);
    const s = existing ?? document.createElement("script");
    const timer = window.setTimeout(() => reject(new Error("timeout")), SCRIPT_TIMEOUT_MS);
    s.addEventListener("load", () => {
      window.clearTimeout(timer);
      if (w.google?.ima) resolve(w.google.ima);
      else reject(new Error("ima"));
    });
    s.addEventListener("error", () => {
      window.clearTimeout(timer);
      reject(new Error("blocked"));
    });
    if (!existing) {
      s.src = IMA_SRC;
      s.async = true;
      document.head.appendChild(s);
    }
  });
}

function recentlyShown(): boolean {
  try {
    const t = Number(localStorage.getItem(LAST_KEY));
    return t > 0 && Date.now() - t < VAST.minIntervalMin * 60000;
  } catch {
    return false;
  }
}

function markShown() {
  try {
    localStorage.setItem(LAST_KEY, String(Date.now()));
  } catch {
    /* stockage indisponible : on ignore */
  }
}

type Phase = "loading" | "ready" | "playing" | "done";

/**
 * Joue une pub vidéo VAST (HilltopAds) avant le lecteur, puis affiche le lecteur.
 * À placer dans le cadre du lecteur (le parent doit être en position: relative).
 * Le lecteur n'est affiché qu'après la pub. Dans tous ces cas, il s'affiche tout de suite :
 * pas de lien VAST, pub déjà vue il y a moins de VAST.minIntervalMin minutes,
 * SDK bloqué, aucune pub disponible ou erreur.
 */
export function VastGate({ children }: { children: ReactNode }) {
  const tag = VAST.tag.trim();
  const [phase, setPhase] = useState<Phase>(() => (!tag || recentlyShown() ? "done" : "loading"));

  const imaRef = useRef<Ima>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const displayRef = useRef<Ima>(null);
  const loaderRef = useRef<Ima>(null);
  const managerRef = useRef<Ima>(null);
  const timers = useRef<number[]>([]);
  const started = useRef(false);

  const clearTimers = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  };

  const destroyAll = () => {
    try {
      managerRef.current?.destroy();
    } catch {
      /* ignore */
    }
    try {
      loaderRef.current?.destroy();
    } catch {
      /* ignore */
    }
    try {
      displayRef.current?.destroy();
    } catch {
      /* ignore */
    }
    managerRef.current = null;
    loaderRef.current = null;
    displayRef.current = null;
  };

  const finish = useCallback(() => {
    clearTimers();
    destroyAll();
    if (started.current) markShown();
    setPhase("done");
  }, []);

  // Chargement du SDK
  useEffect(() => {
    if (phase !== "loading") return;
    let cancelled = false;
    loadIma()
      .then((ima) => {
        if (cancelled) return;
        imaRef.current = ima;
        setPhase("ready");
      })
      .catch(() => {
        if (!cancelled) setPhase("done");
      });
    return () => {
      cancelled = true;
    };
  }, [phase]);

  // Adapte la pub à la taille du cadre
  useEffect(() => {
    if (phase !== "playing" || !boxRef.current) return;
    const ro = new ResizeObserver(() => {
      const box = boxRef.current;
      const ima = imaRef.current;
      if (box && ima && managerRef.current) {
        try {
          managerRef.current.resize(box.clientWidth, box.clientHeight, ima.ViewMode.NORMAL);
        } catch {
          /* ignore */
        }
      }
    });
    ro.observe(boxRef.current);
    return () => ro.disconnect();
  }, [phase]);

  // Nettoyage en quittant la page
  useEffect(
    () => () => {
      clearTimers();
      destroyAll();
    },
    [],
  );

  // Le clic du visiteur est nécessaire : sur mobile, la pub ne peut pas démarrer sans.
  const start = () => {
    const ima = imaRef.current;
    const box = boxRef.current;
    const video = videoRef.current;
    if (!ima || !box || !video) {
      finish();
      return;
    }
    setPhase("playing");
    try {
      const display = new ima.AdDisplayContainer(box, video);
      display.initialize();
      displayRef.current = display;

      const loader = new ima.AdsLoader(display);
      loaderRef.current = loader;

      loader.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, () => finish());
      loader.addEventListener(ima.AdsManagerLoadedEvent.Type.ADS_MANAGER_LOADED, (e: any) => {
        try {
          const manager = e.getAdsManager(video);
          managerRef.current = manager;
          manager.addEventListener(ima.AdErrorEvent.Type.AD_ERROR, () => finish());
          manager.addEventListener(ima.AdEvent.Type.STARTED, () => {
            started.current = true;
          });
          manager.addEventListener(ima.AdEvent.Type.SKIPPED, () => finish());
          manager.addEventListener(ima.AdEvent.Type.ALL_ADS_COMPLETED, () => finish());
          manager.init(box.clientWidth, box.clientHeight, ima.ViewMode.NORMAL);
          manager.start();
        } catch {
          finish();
        }
      });

      const req = new ima.AdsRequest();
      req.adTagUrl = tag;
      req.linearAdSlotWidth = box.clientWidth;
      req.linearAdSlotHeight = box.clientHeight;
      req.nonLinearAdSlotWidth = box.clientWidth;
      req.nonLinearAdSlotHeight = Math.floor(box.clientHeight / 3);
      loader.requestAds(req);

      timers.current.push(
        window.setTimeout(() => {
          if (!started.current) finish();
        }, START_TIMEOUT_MS),
        window.setTimeout(() => finish(), MAX_AD_MS),
      );
    } catch {
      finish();
    }
  };

  if (phase === "done") return <>{children}</>;

  return (
    <div ref={boxRef} className="absolute inset-0 z-20 bg-black">
      <video
        ref={videoRef}
        playsInline
        className="pointer-events-none absolute h-px w-px opacity-0"
      />
      {phase !== "playing" && (
        <div className="absolute inset-0 flex items-center justify-center">
          {phase === "loading" ? (
            <Loader2 className="h-10 w-10 animate-spin text-primary" />
          ) : (
            <button
              type="button"
              onClick={start}
              className="inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 font-body font-semibold text-primary-foreground"
            >
              <Play className="h-5 w-5 fill-current" />
              Lancer la lecture
            </button>
          )}
        </div>
      )}
    </div>
  );
}
