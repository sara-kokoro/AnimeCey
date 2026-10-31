import { useEffect } from "react";
import { ONCLICKA } from "@/config/ads";
import { mountAdCode } from "@/lib/adCode";

let loaded = false;

/**
 * Charge le script OnClicka une seule fois par visite (nécessaire pour la bannière de la fiche anime).
 * Sans code dans ONCLICKA.loader, ne fait rien.
 */
export function OnclickaAd() {
  useEffect(() => {
    const code = ONCLICKA.loader.trim();
    if (!code || loaded) return;
    loaded = true;
    const holder = document.createElement("div");
    holder.dataset.ad = "onclicka";
    (document.body ?? document.documentElement).appendChild(holder);
    mountAdCode(holder, code);
  }, []);

  return null;
}
