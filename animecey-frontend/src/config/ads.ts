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
  banner: (env.VITE_HILLTOP_BANNER as string | undefined) ??
    String.raw`<script>
(function(pkkdzx){
var d = document,
    s = d.createElement('script'),
    l = d.currentScript || d.scripts[d.scripts.length - 1];
s.settings = pkkdzx || {};
s.src = "\/\/shameful-farm.com\/btXDVis.dbGXlC0HY\/WNcZ\/NeYmE9\/uBZBU\/lKkLPHT\/cK1iMhDQk\/yNMnTgM\/tdNszCUzwYOfT\/IDx_NfwQ";
s.async = true;
s.referrerPolicy = 'no-referrer-when-downgrade';
l.parentNode.insertBefore(s, l);
})({})
</script>`,
  /** Lien direct (DirectLink) ouvert avant un téléchargement, par exemple « https://... ». */
  directLink: (env.VITE_HILLTOP_DIRECTLINK as string | undefined) ?? "https://uplcm.com/4/11978082",
};

/**
 * Pub vidéo HilltopAds (VAST), jouée avant la lecture d'un épisode.
 * Colle ici le lien de ta zone VAST. Une chaîne vide désactive la pub vidéo.
 * Peut aussi venir de la variable d'environnement VITE_HILLTOP_VAST.
 */
export const VAST = {
  tag:
    (env.VITE_HILLTOP_VAST as string | undefined) ??
    "https://windy-imagination.com/dXmlFQzrd.GKNdvoZZG_UY/CehmH9yuRZuUJlbk_P/TQcK1_MADik/yOMtDoU/taNizyUqwHOITXImwxO/Qk",
  /** Délai minimum entre deux pubs vidéo pour un même visiteur (en minutes). */
  minIntervalMin: 5,
};

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
