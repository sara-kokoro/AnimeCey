/**
 * Lecture minimale d'une pub vidéo VAST (pré-roll) : choisit un fichier MP4, renvoie les adresses de suivi.
 * Pas de VPAID ni de VMAP. En cas d'erreur, l'appelant lance simplement la vidéo.
 * Dans l'application, la requête passe par le module HTTP natif de Capacitor (pas de blocage CORS).
 */
/* eslint-disable @typescript-eslint/no-explicit-any */

export interface VastAd {
  mediaUrl: string;
  clickUrl?: string;
  /** secondes avant de pouvoir passer la pub ; null = pas de passage possible indiqué */
  skipAfter: number | null;
  impressions: string[];
  events: Record<string, string[]>;
  errors: string[];
}

async function getText(url: string): Promise<string> {
  const http = (window as any).Capacitor?.Plugins?.CapacitorHttp;
  if (http?.get) {
    const r = await http.get({ url, responseType: "text", readTimeout: 8000, connectTimeout: 8000 });
    if (r.status >= 400) throw new Error(`VAST HTTP ${r.status}`);
    return typeof r.data === "string" ? r.data : String(r.data);
  }
  const r = await fetch(url);
  if (!r.ok) throw new Error(`VAST HTTP ${r.status}`);
  return r.text();
}

function parseTime(v: string | null): number | null {
  if (!v) return null;
  const m = /^(\d+):(\d+):(\d+(?:\.\d+)?)$/.exec(v.trim());
  return m ? Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]) : null;
}

const text = (n: Element) => (n.textContent ?? "").trim();

export async function loadVast(url: string, depth = 0): Promise<VastAd | null> {
  if (depth > 3) return null;
  const doc = new DOMParser().parseFromString(await getText(url), "text/xml");
  const ad = doc.querySelector("Ad");
  if (!ad) return null;

  const wrapper = ad.querySelector("Wrapper");
  const out: VastAd = { mediaUrl: "", skipAfter: null, impressions: [], events: {}, errors: [] };
  ad.querySelectorAll("Impression").forEach((n) => text(n) && out.impressions.push(text(n)));
  ad.querySelectorAll("Error").forEach((n) => text(n) && out.errors.push(text(n)));
  ad.querySelectorAll("Tracking").forEach((n) => {
    const ev = n.getAttribute("event");
    if (ev && text(n)) (out.events[ev] ??= []).push(text(n));
  });

  if (wrapper) {
    const next = text(ad.querySelector("VASTAdTagURI") ?? doc.createElement("x"));
    if (!next) return null;
    const inner = await loadVast(next, depth + 1);
    if (!inner) return null;
    inner.impressions.push(...out.impressions);
    for (const [k, v] of Object.entries(out.events)) (inner.events[k] ??= []).push(...v);
    return inner;
  }

  const linear = ad.querySelector("Linear");
  if (!linear) return null;
  const files = Array.from(linear.querySelectorAll("MediaFile"))
    .map((f) => ({
      url: text(f),
      type: f.getAttribute("type") ?? "",
      width: Number(f.getAttribute("width") ?? 0),
      delivery: f.getAttribute("delivery") ?? "progressive",
    }))
    .filter((f) => f.url && f.type.includes("mp4") && f.delivery !== "streaming");
  if (files.length === 0) return null;
  // la plus grande définition jusqu'à 1280 px de large (assez pour un téléphone, sans gros fichier)
  files.sort((a, b) => Math.abs(720 - a.width) - Math.abs(720 - b.width));
  out.mediaUrl = files[0].url;
  const click = linear.querySelector("ClickThrough");
  if (click) out.clickUrl = text(click);
  out.skipAfter = parseTime(linear.getAttribute("skipoffset"));
  return out;
}

export function ping(urls: string[] | undefined): void {
  for (const u of urls ?? []) {
    try {
      new Image().src = u;
    } catch {
      /* ignoré */
    }
  }
}
