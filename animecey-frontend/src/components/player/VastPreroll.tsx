import { useEffect, useRef, useState } from "react";
import { loadVast, ping, type VastAd } from "@/lib/vast";

/* eslint-disable @typescript-eslint/no-explicit-any */
const MAX_WAIT_MS = 6000;

/**
 * Pub vidéo VAST affichée avant l'épisode (application seulement).
 * Si la pub ne charge pas en 6 secondes ou échoue, elle disparaît et l'épisode démarre.
 */
export function VastPreroll({ url, onDone }: { url: string; onDone: () => void }) {
  const [ad, setAd] = useState<VastAd | null>(null);
  const [left, setLeft] = useState<number | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const done = useRef(false);
  const fired = useRef<Set<string>>(new Set());

  const finish = () => {
    if (done.current) return;
    done.current = true;
    onDone();
  };

  useEffect(() => {
    let cancelled = false;
    const timeout = window.setTimeout(finish, MAX_WAIT_MS);
    loadVast(url)
      .then((a) => {
        if (cancelled) return;
        if (!a) return finish();
        window.clearTimeout(timeout);
        setAd(a);
      })
      .catch(() => !cancelled && finish());
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  const fire = (ev: string) => {
    if (!ad || fired.current.has(ev)) return;
    fired.current.add(ev);
    ping(ad.events[ev]);
  };

  if (!ad) {
    return (
      <div className="absolute inset-0 z-30 bg-black flex items-center justify-center text-xs text-white/60">
        Chargement…
      </div>
    );
  }

  const canSkip = left !== null && left <= 0;

  return (
    <div className="absolute inset-0 z-30 bg-black">
      <video
        ref={videoRef}
        src={ad.mediaUrl}
        autoPlay
        playsInline
        className="absolute inset-0 w-full h-full object-contain"
        onPlay={() => {
          if (!fired.current.has("impression")) {
            fired.current.add("impression");
            ping(ad.impressions);
          }
          fire("start");
        }}
        onTimeUpdate={(e) => {
          const v = e.currentTarget;
          if (ad.skipAfter !== null) setLeft(Math.ceil(ad.skipAfter - v.currentTime));
          else setLeft(Math.ceil(5 - v.currentTime)); // pas de délai indiqué : passage possible après 5 s
          if (v.duration) {
            const p = v.currentTime / v.duration;
            if (p >= 0.25) fire("firstQuartile");
            if (p >= 0.5) fire("midpoint");
            if (p >= 0.75) fire("thirdQuartile");
          }
        }}
        onEnded={() => {
          fire("complete");
          finish();
        }}
        onError={() => {
          ping(ad.errors);
          finish();
        }}
        onClick={() => {
          if (!ad.clickUrl) return;
          fire("clickTracking");
          (window as any).MagiNative?.openExternal?.(ad.clickUrl);
        }}
      />
      <span className="absolute top-2 left-2 rounded bg-black/70 px-2 py-0.5 text-[11px] text-white">Publicité</span>
      <button
        onClick={() => {
          if (!canSkip) return;
          fire("skip");
          finish();
        }}
        className="absolute bottom-3 right-3 rounded-full bg-black/75 border border-white/30 px-4 py-2 text-xs font-semibold text-white disabled:opacity-70"
        disabled={!canSkip}
      >
        {canSkip ? "Passer ›" : left !== null ? `Passer dans ${left} s` : "…"}
      </button>
    </div>
  );
}
