import { useEffect } from "react";
import { CLICKADILLA } from "@/config/ads";
import { mountAdCode } from "@/lib/adCode";

let loaded = false;

/**
 * Charge le script Clickadilla une seule fois par visite : il active les formats créés dans leur tableau de bord
 * (vidéo in-stream, interstitiel, in-page push, bannière).
 * À placer uniquement sur les pages publiques, jamais dans l'admin.
 */
export function ClickadillaAd() {
  useEffect(() => {
    const code = CLICKADILLA.loader.trim();
    if (!code || loaded) return;
    loaded = true;
    const holder = document.createElement("div");
    holder.dataset.ad = "clickadilla";
    (document.body ?? document.documentElement).appendChild(holder);
    mountAdCode(holder, code);
  }, []);

  return null;
}
