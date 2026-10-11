/**
 * Publicités HilltopAds de Magi-Stream.
 *
 * Colle ci-dessous le code fourni par HilltopAds (tableau de bord → Sites → ta zone → « Code »).
 * Une chaîne vide désactive le format : rien n'est chargé et aucun espace n'est réservé.
 * Chaque valeur peut aussi venir d'une variable d'environnement Vercel (VITE_HILLTOP_...).
 */
const env = import.meta.env;

export const HILLTOP = {
  /** Zone MultiTag (popunder, in-page, video slider...) : chargée sur les pages de lecture. */
  multitag: (env.VITE_HILLTOP_MULTITAG as string | undefined) ?? ``,
  /** Zone bannière 300×250 (code à coller tel quel). */
  banner: (env.VITE_HILLTOP_BANNER as string | undefined) ?? ``,
  /** Lien direct (DirectLink) ouvert avant un téléchargement, par exemple « https://... ». */
  directLink: (env.VITE_HILLTOP_DIRECTLINK as string | undefined) ?? "",
};

/**
 * Monetag (In-Page Push).
 * Zone fournie par Monetag. Une chaîne vide désactive le format.
 * Peut aussi venir de la variable d'environnement VITE_MONETAG_ZONE.
 */
export const MONETAG = {
  zone: (env.VITE_MONETAG_ZONE as string | undefined) ?? "12006031",
  src: "https://nap5k.com/tag.min.js",
};
