import { useEffect } from "react";
import { MONETAG } from "@/config/ads";
import { isNativeApp } from "@/lib/nativeDownloads";
import { mountAdCode } from "@/lib/adCode";

let loaded = false;

/**
 * Notifications push Monetag (remplacent celles de HilltopAds) : le code Monetag est inséré tel quel
 * (voir MONETAG.push.code dans config/ads.ts), une seule fois par visite.
 * Le service worker de Monetag est inclus dans /sw.js : voir public/monetag-sw.js.
 * À placer uniquement sur les pages publiques, jamais dans l'admin.
 */
export function PushAd() {
  useEffect(() => {
    // Dans l'application Android : pas de popunder ni de push web (ils sortiraient l'utilisateur de l'app)
    if (isNativeApp()) return;
    const code = MONETAG.push.code.trim();
    if (!code || loaded) return;
    loaded = true;
    const holder = document.createElement("div");
    holder.dataset.ad = "monetag-push";
    (document.body ?? document.documentElement).appendChild(holder);
    mountAdCode(holder, code);
  }, []);

  return null;
}
