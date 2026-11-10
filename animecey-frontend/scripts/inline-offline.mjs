/**
 * Rend app/www/offline.html AUTONOME : le JavaScript et le CSS construits par Vite sont copiés DANS le fichier.
 *
 * Pourquoi : quand Capacitor affiche la page d'erreur (errorPath) alors que `server.url` est défini, seul ce fichier
 * HTML est servi depuis l'APK. Les fichiers qu'il référence (./assets/*.js, *.css) ne sont pas servis : ils
 * échouent ("Fichier non chargé") et on obtient un écran noir. Une page 100 % autonome n'a pas ce problème.
 *
 * Lancé automatiquement par `npm run build:offline` (après `vite build`). Échoue s'il reste une référence externe.
 */
import { readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const racine = join(dirname(fileURLToPath(import.meta.url)), "..");
const www = process.argv[2] ? resolve(process.argv[2]) : join(racine, "app", "www");
const htmlPath = join(www, "offline.html");

if (!existsSync(htmlPath)) {
  console.error(`✗ ${htmlPath} introuvable : lance d'abord « vite build -c vite.offline.config.ts ».`);
  process.exit(1);
}

let html = readFileSync(htmlPath, "utf8");
const utilises = [];

// <script type="module" crossorigin src="./assets/xxx.js"></script>  →  <script type="module">…</script>
html = html.replace(/<script\b[^>]*\bsrc="(\.\/assets\/[^"]+\.js)"[^>]*><\/script>/g, (_m, src) => {
  utilises.push(src);
  const code = readFileSync(join(www, src), "utf8").replace(/<\/script/gi, "<\\/script").replace(/<!--/g, "<\\!--");
  return `<script type="module">\n${code}\n</script>`;
});

// <link rel="stylesheet" href="./assets/xxx.css">  →  <style>…</style>
html = html.replace(/<link\b[^>]*\bhref="(\.\/assets\/[^"]+\.css)"[^>]*>/g, (_m, href) => {
  utilises.push(href);
  const css = readFileSync(join(www, href), "utf8").replace(/<\/style/gi, "<\\/style");
  return `<style>\n${css}\n</style>`;
});

// Préchargements de modules devenus inutiles
html = html.replace(/<link\b[^>]*\brel="modulepreload"[^>]*>\s*/g, "");

const reste = html.match(/(?:src|href)="\.\/assets\/[^"]+"/g);
if (reste) {
  console.error("✗ Références externes restantes dans offline.html :", reste.join(", "));
  process.exit(1);
}
if (utilises.length === 0) {
  console.error("✗ Aucun fichier à inclure : offline.html ne référence pas ./assets/ (déjà autonome, ou build inattendu).");
  process.exit(1);
}

writeFileSync(htmlPath, html);
// Les fichiers sources ne servent plus (et ne doivent pas être pris pour la page à jour) : on les supprime.
for (const f of utilises) rmSync(join(www, f), { force: true });
console.log(`✓ offline.html autonome : ${utilises.length} fichier(s) inclus, ${(html.length / 1024).toFixed(0)} Ko`);
