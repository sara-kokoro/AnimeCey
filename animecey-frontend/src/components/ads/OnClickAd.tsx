import { useEffect } from "react";
import { MONETAG } from "@/config/ads";

let loaded = false;

/**
 * Monetag OnClick (Popunder), chargé une seule fois par visite.
 * Le script écoute les clics de la page : le recharger à chaque navigation multiplierait les popunders,
 * donc on ne le charge qu'une fois (il reste actif jusqu'au rechargement de la page).
 * À placer uniquement sur les pages publiques (détails, lecture), jamais dans l'admin.
 */
export function OnClickAd() {
  useEffect(() => {
    const { zone, src } = MONETAG.onclick;
    if (!zone.trim() || loaded) return;
    loaded = true;
    const s = document.createElement("script");
    s.dataset.zone = zone.trim();
    s.src = src;
    (document.body ?? document.documentElement).appendChild(s);
  }, []);

  return null;
}
