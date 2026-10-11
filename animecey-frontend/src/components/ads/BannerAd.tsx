import { useEffect, useRef, useState } from "react";
import { HILLTOP } from "@/config/ads";
import { cn } from "@/lib/utils";

/**
 * Bannière HilltopAds 300×250.
 * - Chargée seulement quand elle approche de l'écran (page plus rapide).
 * - Placée dans un cadre isolé (sandbox, sans accès à ton site) : le script publicitaire ne peut pas lire
 *   le jeton de connexion des visiteurs.
 * - L'espace est réservé d'avance : la page ne saute pas quand la pub arrive. Sans code : ne rend rien.
 */
export function BannerAd({ className }: { className?: string }) {
  const code = HILLTOP.banner.trim();
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!code || !ref.current) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          io.disconnect();
        }
      },
      { rootMargin: "200px" },
    );
    io.observe(ref.current);
    return () => io.disconnect();
  }, [code]);

  if (!code) return null;

  const srcDoc =
    `<!doctype html><html><head><meta charset="utf-8"><base target="_blank">` +
    `<style>html,body{margin:0;padding:0;background:transparent;overflow:hidden}body{display:flex;justify-content:center}</style>` +
    `</head><body>${code}</body></html>`;

  return (
    <div ref={ref} className={cn("mx-auto w-[300px] max-w-full", className)}>
      <p className="mb-1 text-center text-[10px] font-body uppercase tracking-wider text-muted-foreground">Publicité</p>
      <div className="max-w-full" style={{ width: 300, height: 250 }}>
        {visible && (
          <iframe
            title="Publicité"
            srcDoc={srcDoc}
            width={300}
            height={250}
            loading="lazy"
            scrolling="no"
            sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox allow-top-navigation-by-user-activation"
            className="block border-0"
          />
        )}
      </div>
    </div>
  );
}
