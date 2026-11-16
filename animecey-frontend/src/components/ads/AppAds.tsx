import { useEffect } from "react";
import { APP_ADS } from "@/config/ads";
import { isNativeApp } from "@/lib/nativeDownloads";

let loaded = false;

/**
 * Pubs Monetag « Vignette » et « In-Page Push » : uniquement dans l'application Android.
 * Les scripts sont ajoutés une seule fois, au premier affichage. Sur le site, ce composant ne fait rien.
 */
export function AppAds() {
  useEffect(() => {
    if (!isNativeApp() || loaded) return;
    loaded = true;
    for (const { zone, src } of [APP_ADS.vignette, APP_ADS.inPagePush]) {
      if (!zone || !src) continue;
      const s = document.createElement("script");
      s.dataset.zone = zone;
      s.src = src;
      (document.body ?? document.documentElement).appendChild(s);
    }
  }, []);

  return null;
}
