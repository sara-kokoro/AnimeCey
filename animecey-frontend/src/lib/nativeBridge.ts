import { fetchAd } from "@/api/ads";

/* eslint-disable @typescript-eslint/no-explicit-any */
const nat = (): any => (typeof window === "undefined" ? undefined : (window as any).MagiNative);

const API_BASE: string = import.meta.env.VITE_API_URL ?? "https://yumeflowerbot.koyeb.app/api";

function toDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsDataURL(blob);
  });
}

/**
 * Application Android uniquement (MagiNative n'existe pas sur le site) :
 *  - active les notifications du bot ;
 *  - ouvre la page demandée par un clic sur une notification ;
 *  - garde la pub « hors ligne » pour la page sans connexion.
 */
export async function initNativeBridge(): Promise<void> {
  const n = nat();
  if (!n) return;
  try {
    // Google Analytics : distingue les visites de l'application de celles du site
    (window as any).gtag?.("set", "user_properties", { platform: "app" });
    n.configure?.(API_BASE);
    const p: string = n.consumeOpenPath?.() ?? "";
    if (p.startsWith("/") && p !== location.pathname) window.location.assign(p);
  } catch {
    /* ignoré */
  }
  try {
    const res = await fetchAd("offline");
    const ad = res.ad;
    let image = "";
    if (ad) {
      const blob = await (await fetch(ad.media_url)).blob();
      if (blob.size <= 1_500_000 && blob.type.startsWith("image/")) image = await toDataUrl(blob);
    }
    n.saveOfflineAd?.(JSON.stringify({ ad: ad && image ? { ...ad, image } : null, contact: res.contact }));
  } catch {
    /* hors connexion : on garde la dernière pub enregistrée */
  }
}
