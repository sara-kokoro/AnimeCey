import { useEffect } from "react";
import { HILLTOP } from "@/config/ads";
import { mountAdCode } from "@/lib/adCode";

/**
 * Charge la zone MultiTag de HilltopAds (popunder, in-page, video slider...) tant que la page est ouverte.
 * À placer uniquement sur les pages publiques (lecture), jamais dans l'admin. Sans code : ne fait rien.
 */
export function MultiTagAd() {
  useEffect(() => {
    const code = HILLTOP.multitag.trim();
    if (!code) return;
    const holder = document.createElement("div");
    holder.dataset.ad = "hilltop-multitag";
    (document.body ?? document.documentElement).appendChild(holder);
    mountAdCode(holder, code);
    return () => {
      holder.remove();
    };
  }, []);

  return null;
}
