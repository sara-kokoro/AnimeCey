/**
 * Page « Hors connexion » de l'application Android (Capacitor).
 *
 * Quand le site (server.url) ne se charge pas, Capacitor affiche cette page, qui est EMBARQUÉE dans
 * l'APK (dossier app/www). Elle est construite avec `npm run build:offline` et réutilise les mêmes
 * composants React que la page « Mes téléchargements » du site.
 */
import { createRoot } from "react-dom/client";
import "./offline.css";
import { OfflineApp } from "./OfflineApp";

/* eslint-disable @typescript-eslint/no-explicit-any */
// Les vignettes sont gardées par le module natif (la page n'a pas le même stockage que le site) :
// on les recopie pour que DownloadsLibrary les trouve.
try {
  const covers = JSON.parse((window as any).MagiNative?.getCovers?.() ?? "{}") as Record<string, string>;
  for (const [id, dataUrl] of Object.entries(covers)) {
    try {
      localStorage.setItem(`magi_cover_${id}`, dataUrl);
    } catch {
      /* stockage plein : pas grave */
    }
  }
} catch {
  /* pas de vignettes */
}

document.documentElement.classList.add("dark");
createRoot(document.getElementById("root")!).render(<OfflineApp />);
