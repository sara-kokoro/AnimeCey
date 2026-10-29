/**
 * Publicités de Magi-Stream : Monetag, RichAds (téléchargements) et Adsterra.
 * Une chaîne vide désactive le format : rien n'est chargé et aucun espace n'est réservé.
 * Chaque valeur peut aussi venir d'une variable d'environnement (VITE_...).
 */
const env = import.meta.env;

/**
 * RichAds : tag VAST éditeur pour les téléchargements hors ligne.
 * La zone doit autoriser ce placement et les demandes consécutives.
 * Sans tag, les téléchargements restent bloqués : aucune pub simulée.
 */
export const RICHADS = {
  directLink: (env.VITE_RICHADS_DIRECTLINK as string | undefined) ?? "",
  vastTag: (env.VITE_RICHADS_VAST as string | undefined) ?? "",
};

/**
 * Adsterra : bannière native (largeur adaptable) et bannière 320×50.
 * Pour désactiver un format, mets sa valeur « src » à une chaîne vide.
 */
export const ADSTERRA = {
  native: {
    src: "https://asperitymeg.com/0860f51b75536f1919cf4b33ca6be827/invoke.js",
    containerId: "container-0860f51b75536f1919cf4b33ca6be827",
  },
  banner: {
    key: "263e39d26222551b3b48784264465d9b",
    src: "https://asperitymeg.com/263e39d26222551b3b48784264465d9b/invoke.js",
    width: 320,
    height: 50,
  },
  /** Social Bar : doit tourner dans la page elle-même (comme Monetag). Vide = désactivé. */
  socialBar: {
    src: "https://asperitymeg.com/65/0e/b5/650eb564bed8abd40af0d7ca7ac5f337.js",
  },
};

/**
 * Monetag (tableau de bord Monetag → Sites → magi-stream.online).
 * Chaque valeur peut être remplacée par une variable d'environnement (VITE_MONETAG_...).
 * Une zone vide désactive le format.
 */
export const MONETAG = {
  /** OnClick (Popunder) : pages « détails » et « lecture ». */
  onclick: {
    zone: (env.VITE_MONETAG_ONCLICK_ZONE as string | undefined) ?? "12139840",
    src: "https://al5sm.com/tag.min.js",
  },
  /** Notifications push (remplacent celles de HilltopAds) : code Monetag collé tel quel. */
  push: {
    code:
      (env.VITE_MONETAG_PUSH_CODE as string | undefined) ??
      String.raw`<script src="https://5gvci.com/act/files/tag.min.js?z=12007084" data-cfasync="false" async></script>`,
  },
};
