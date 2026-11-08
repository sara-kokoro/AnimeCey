/**
 * Publicités de Magi-Stream : Monetag et RichAds (téléchargements). Adsterra a été retiré.
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
  /** In-Page Push (bannière de notification dans la page, sans autorisation) : zone « Interesting tag ». */
  inPagePush: {
    zone: (env.VITE_MONETAG_INPAGE_ZONE as string | undefined) ?? "12006031",
    src: "https://nap5k.com/tag.min.js",
  },
};
