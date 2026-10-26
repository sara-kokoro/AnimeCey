import { useEffect } from "react";

// Zone Monetag « Vignette » de magi-stream.online. Surchargeable avec VITE_MONETAG_VIGNETTE_ZONE.
const ZONE: string = import.meta.env.VITE_MONETAG_VIGNETTE_ZONE ?? "11978346";
const SRC = "https://n6wxm.com/vignette.min.js";

/**
 * Charge la pub Monetag « Vignette » tant que la page qui l'affiche est ouverte.
 * À placer uniquement sur les pages publiques (lecture), pas dans l'admin.
 * Le script est retiré quand on quitte la page.
 */
export function VignetteAd() {
  useEffect(() => {
    const script = document.createElement("script");
    script.dataset.zone = ZONE;
    script.src = SRC;
    (document.body ?? document.documentElement).appendChild(script);
    return () => {
      script.remove();
    };
  }, []);

  return null;
}
