import { useEffect, useRef, useState } from "react";
import { ADSTERRA } from "@/config/ads";
import { cn } from "@/lib/utils";

type Format = "native" | "banner";

/**
 * Bannière Adsterra.
 * - format="native" : bannière native, qui prend la largeur disponible (jusqu'à 576 px).
 *   La hauteur s'adapte au contenu ; sans pub, rien n'est affiché et aucun espace n'est réservé.
 * - format="banner" : bannière 320×50.
 * Chargée seulement quand elle approche de l'écran, dans un cadre isolé (sandbox) :
 * le script publicitaire ne peut pas lire le jeton de connexion des visiteurs.
 */
export function AdsterraBanner({ format, className }: { format: Format; className?: string }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [visible, setVisible] = useState(false);
  const [nativeHeight, setNativeHeight] = useState(0);

  const isNative = format === "native";
  const src = isNative ? ADSTERRA.native.src : ADSTERRA.banner.src;

  useEffect(() => {
    if (!src || !wrapRef.current) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    io.observe(wrapRef.current);
    return () => io.disconnect();
  }, [src]);

  // Reçoit la hauteur réelle de la bannière native depuis son cadre
  useEffect(() => {
    if (!isNative) return;
    const onMessage = (e: MessageEvent) => {
      if (e.source !== frameRef.current?.contentWindow) return;
      const h = Number((e.data as { __adh?: number } | null)?.__adh);
      if (h > 0 && h < 1500) setNativeHeight(Math.ceil(h));
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [isNative]);

  if (!src) return null;

  const base =
    `<!doctype html><html><head><meta charset="utf-8"><base target="_blank">` +
    `<style>html,body{margin:0;padding:0;background:transparent}body{display:flex;justify-content:center}</style>` +
    `</head><body>`;

  const nativeSizer =
    `<script>(function(){function p(){try{parent.postMessage({__adh:document.body.offsetHeight},"*")}catch(e){}}` +
    `if(window.ResizeObserver){new ResizeObserver(p).observe(document.body)}` +
    `window.addEventListener("load",p);setTimeout(p,1500);setTimeout(p,4000);})();</script>`;

  const srcDoc = isNative
    ? `${base}<div style="width:100%">` +
      `<script async="async" data-cfasync="false" src="${ADSTERRA.native.src}"></script>` +
      `<div id="${ADSTERRA.native.containerId}"></div></div>${nativeSizer}</body></html>`
    : `${base}<script>atOptions={'key':'${ADSTERRA.banner.key}','format':'iframe','height':${ADSTERRA.banner.height},'width':${ADSTERRA.banner.width},'params':{}};</script>` +
      `<script src="${ADSTERRA.banner.src}"></script></body></html>`;

  const showLabel = isNative ? nativeHeight > 0 : true;

  return (
    <div
      ref={wrapRef}
      className={cn("mx-auto max-w-full", isNative ? "w-full max-w-xl px-4 md:px-0" : "", className)}
      style={isNative ? { minHeight: 1 } : { width: ADSTERRA.banner.width }}
    >
      {showLabel && (
        <p className="mb-1 text-center text-[10px] font-body uppercase tracking-wider text-muted-foreground">
          Publicité
        </p>
      )}
      <div style={isNative ? undefined : { width: ADSTERRA.banner.width, height: ADSTERRA.banner.height }} className="max-w-full">
        {visible && (
          <iframe
            ref={frameRef}
            title="Publicité"
            srcDoc={srcDoc}
            scrolling="no"
            sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
            className="block w-full border-0"
            style={
              isNative
                ? { height: nativeHeight }
                : { width: ADSTERRA.banner.width, height: ADSTERRA.banner.height }
            }
          />
        )}
      </div>
    </div>
  );
}
