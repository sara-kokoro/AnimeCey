import { useEffect, useRef, useState } from "react";

const LOTTIE_URL = "https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie_light.min.js";

type LottieLib = {
  loadAnimation: (o: Record<string, unknown>) => { destroy: () => void; addEventListener: (e: string, cb: () => void) => void };
};

let libPromise: Promise<LottieLib | null> | null = null;

/** Charge le lecteur Lottie léger une seule fois, uniquement quand on en a besoin. */
function loadLottie(): Promise<LottieLib | null> {
  const w = window as unknown as { lottie?: LottieLib };
  if (w.lottie) return Promise.resolve(w.lottie);
  if (!libPromise) {
    libPromise = new Promise((resolve) => {
      const s = document.createElement("script");
      s.src = LOTTIE_URL;
      s.async = true;
      s.onload = () => resolve(w.lottie ?? null);
      s.onerror = () => {
        libPromise = null;
        resolve(null);
      };
      document.head.appendChild(s);
    });
  }
  return libPromise;
}

const idle = (cb: () => void) => {
  const w = window as unknown as { requestIdleCallback?: (f: () => void, o?: { timeout: number }) => number };
  if (w.requestIdleCallback) w.requestIdleCallback(cb, { timeout: 4000 });
  else window.setTimeout(cb, 1500);
};

/**
 * Logo de crypto : image légère tout de suite, animation Lottie chargée seulement
 * quand elle est visible et que le navigateur est au repos. Jouée une fois puis
 * détruite (pas de RAM gardée). Un toucher la rejoue.
 */
export function LottieCoin({ coin, size = 44 }: { coin: string; size?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const [playing, setPlaying] = useState(false);
  const [visible, setVisible] = useState(false);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const el = box.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          io.disconnect();
        }
      },
      { rootMargin: "50px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    let anim: { destroy: () => void } | null = null;
    let cancelled = false;
    idle(() => {
      if (cancelled) return;
      void (async () => {
        try {
          const [lib, data] = await Promise.all([
            loadLottie(),
            fetch(`/lottie/${coin}.json`).then((r) => (r.ok ? r.json() : null)),
          ]);
          if (cancelled || !lib || !data || !box.current) return;
          const holder = document.createElement("div");
          holder.style.cssText = "position:absolute;inset:0";
          box.current.appendChild(holder);
          const a = lib.loadAnimation({ container: holder, renderer: "svg", loop: false, autoplay: true, animationData: data });
          anim = { destroy: () => { a.destroy(); holder.remove(); } };
          setPlaying(true);
          a.addEventListener("complete", () => {
            anim?.destroy();
            anim = null;
            setPlaying(false);
          });
        } catch {
          /* l'image statique reste affichée */
        }
      })();
    });
    return () => {
      cancelled = true;
      anim?.destroy();
    };
  }, [visible, coin, tick]);

  return (
    <div
      ref={box}
      onClick={() => !playing && setTick((t) => t + 1)}
      className="relative shrink-0"
      style={{ width: size, height: size }}
    >
      <img
        src={`/lottie/${coin}.webp`}
        alt=""
        width={size}
        height={size}
        loading="lazy"
        decoding="async"
        className="w-full h-full object-contain"
        style={{ opacity: playing ? 0 : 1 }}
      />
    </div>
  );
}
