/* Service worker des notifications push Monetag (zone 12007084).
 * Contenu fourni par Monetag, importé dans /sw.js (voir vite.config.ts).
 * Le try/catch évite que /sw.js (cache hors ligne, nos notifications) ne s'installe pas
 * si le domaine de Monetag est injoignable ou bloqué chez un visiteur. */
try {
  self.options = {
    "domain": "5gvci.com",
    "zoneId": 12007084
  }
  self.lary = ""
  importScripts('https://5gvci.com/act/files/service-worker.min.js?r=sw')
} catch (e) {
  /* Monetag injoignable : les notifications Monetag sont désactivées pour cette visite */
}
