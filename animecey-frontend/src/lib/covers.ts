/**
 * Vignettes « paysage » des dossiers de téléchargements (affiche TMDB de l'animé).
 *
 * Chaque image est réduite (480 px, JPEG léger, ~20-40 Ko) puis gardée dans le téléphone pour
 * s'afficher sans connexion. Dans l'application, une copie est aussi donnée au module natif :
 * c'est lui qui la fournit à la page hors ligne (voir MagiNative.saveCover / getCovers).
 * Tout se fait en arrière-plan, une seule fois par animé : rien ne ralentit l'ouverture de la page.
 */
import { fetchAnime } from "@/api/animes";

const KEY = (animeId: number) => `magi_cover_${animeId}`;
const inFlight = new Set<number>();

/* eslint-disable @typescript-eslint/no-explicit-any */
const nat = (): any => (typeof window === "undefined" ? undefined : (window as any).MagiNative);

export function getCover(animeId: number): string | null {
  try {
    return localStorage.getItem(KEY(animeId));
  } catch {
    return null;
  }
}

function shrink(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.decoding = "async";
    img.onload = () => {
      const w = 480;
      const h = Math.round((img.naturalHeight / img.naturalWidth) * w) || 270;
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = Math.min(h, 360);
      const ctx = canvas.getContext("2d");
      if (!ctx) return reject(new Error("canvas"));
      // recadrage au centre si l'image est plus haute que large
      const sh = (canvas.height / h) * img.naturalHeight;
      ctx.drawImage(img, 0, (img.naturalHeight - sh) / 2, img.naturalWidth, sh, 0, 0, w, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", 0.72));
    };
    img.onerror = () => reject(new Error("image"));
    img.src = url;
  });
}

/** Enregistre la vignette de l'animé si on ne l'a pas encore. Silencieux en cas d'échec. */
export async function ensureCover(animeId: number): Promise<void> {
  if (!animeId || inFlight.has(animeId) || getCover(animeId)) return;
  inFlight.add(animeId);
  try {
    const anime = await fetchAnime(animeId);
    const source = anime.banner_url || anime.poster_url;
    if (!source) return;
    const data = await shrink(source);
    try {
      localStorage.setItem(KEY(animeId), data);
    } catch {
      /* stockage plein : pas de vignette, ce n'est pas grave */
    }
    try {
      nat()?.saveCover?.(String(animeId), data);
    } catch {
      /* application ancienne : sans effet */
    }
  } catch {
    /* hors connexion ou image bloquée : on réessaiera au prochain téléchargement */
  } finally {
    inFlight.delete(animeId);
  }
}

/** Retire la vignette quand le dernier épisode de l'animé est supprimé. */
export function removeCover(animeId: number): void {
  try {
    localStorage.removeItem(KEY(animeId));
  } catch {
    /* ignoré */
  }
  try {
    nat()?.removeCover?.(String(animeId));
  } catch {
    /* ignoré */
  }
}
