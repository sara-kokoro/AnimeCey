import { useEffect } from "react";
import { ADSTERRA } from "@/config/ads";

let loaded = false;

/**
 * Charge le Social Bar Adsterra, une seule fois par visite.
 * Le script doit tourner dans la page elle-même : il a le même accès à ton site que Monetag.
 * À placer uniquement sur les pages publiques, jamais dans l'admin.
 * Une fois chargé, il reste affiché pendant la navigation dans le site, jusqu'au rechargement de la page.
 */
export function SocialBarAd() {
  useEffect(() => {
    const src = ADSTERRA.socialBar.src.trim();
    if (!src || loaded) return;
    loaded = true;
    const s = document.createElement("script");
    s.src = src;
    s.async = true;
    (document.body ?? document.documentElement).appendChild(s);
  }, []);

  return null;
}
