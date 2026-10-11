import { useEffect, useRef, useState } from "react";
import { ADSTERRA } from "@/config/ads";
import { cn } from "@/lib/utils";

type Format = "native" | "banner";

// Hauteur donnée au cadre natif tant qu'il n'a rien affiché : certains scripts publicitaires
// ne s'affichent pas dans un cadre de hauteur nulle.
const NATIVE_PROBE_HEIGHT = 250;

/**
 * Bannière Adsterra.
 * - format="native" : bannière native, qui prend la largeur disponible (jusqu'à 576 px).
 *   La hauteur s'adapte au contenu ; sans pub, rien n'est affiché et aucun espace n'est réservé.
 * - format="banner" : bannière 320×50.
 * Chargée seulement quand elle approche de l'écran, dans un cadre isolé (sandbox) qui affiche une page de public/ads :
 * le script publicitaire ne peut pas lire le jeton de connexion des visiteurs.
 */
export function AdsterraBanner({ format, className }: { format: Format; className?: string }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [visible, setVisible] = useState(false);
  const [nativeHeight, setNativeHeight] = useState(0);
  const [filled, setFilled] = useState(false);

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
      if (h > 0 && h < 1500) {
        setNativeHeight(Math.ceil(h));
        setFilled(true);
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [isNative]);

  if (!src) return null;

  // Pages hébergées sur ton site (dossier public/ads) : le script voit ainsi le vrai nom de domaine,
  // tout en restant isolé dans un cadre sécurisé (sandbox).
  const page = isNative ? "/ads/adsterra-native.html" : "/ads/adsterra-banner-320x50.html";

  // Bannière native : tant qu'aucune pub n'est arrivée, le cadre est invisible, sans espace réservé
  // ni clic intercepté, mais il garde une vraie taille pour que le script se charge.
  const showLabel = isNative ? filled : true;

  return (
    <div
      ref={wrapRef}
      className={cn("mx-auto max-w-full", isNative ? "relative w-full max-w-xl px-4 md:px-0" : "", className)}
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
            src={page}
            scrolling="no"
            sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
            className="block w-full border-0"
            style={
              isNative
                ? filled
                  ? { height: nativeHeight }
                  : { position: "absolute", top: 0, left: 0, height: NATIVE_PROBE_HEIGHT, pointerEvents: "none" }
                : { width: ADSTERRA.banner.width, height: ADSTERRA.banner.height }
            }
          />
        )}
      </div>
    </div>
  );
}
