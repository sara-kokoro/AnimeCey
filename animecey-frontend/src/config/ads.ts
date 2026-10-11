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
