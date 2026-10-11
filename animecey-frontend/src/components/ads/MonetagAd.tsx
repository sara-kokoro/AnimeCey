import { useEffect } from "react";
import { MONETAG } from "@/config/ads";

/**
 * Charge la zone Monetag (In-Page Push) tant que la page est ouverte.
 * À placer uniquement sur les pages publiques (lecture), jamais dans l'admin.
 * Sans zone : ne fait rien.
 */
export function MonetagAd() {
  useEffect(() => {
    const zone = MONETAG.zone.trim();
    if (!zone) return;
    const s = document.createElement("script");
    s.dataset.zone = zone;
    s.src = MONETAG.src;
    (document.body ?? document.documentElement).appendChild(s);
    return () => {
      s.remove();
    };
  }, []);

  return null;
}
