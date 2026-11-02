import { useEffect } from "react";
import { MONETAG } from "@/config/ads";
import { isNativeApp } from "@/lib/nativeDownloads";

let loaded = false;

/**
 * Monetag In-Page Push : petite bannière façon notification, affichée dans la page.
 * Chargée une seule fois par visite, sur le site uniquement (pas dans l'application Android).
 */
export function InPagePushAd() {
  useEffect(() => {
    if (isNativeApp() || loaded) return;
    const { zone, src } = MONETAG.inPagePush;
    if (!zone || !src) return;
    loaded = true;
    const s = document.createElement("script");
    s.dataset.zone = zone;
    s.src = src;
    (document.body ?? document.documentElement).appendChild(s);
  }, []);

  return null;
}
