/**
 * Page « Hors connexion » de l'application Android (Capacitor).
 *
 * Quand le site (server.url) ne se charge pas, Capacitor affiche cette page, qui est EMBARQUÉE dans
 * l'APK (dossier app/www). Elle est construite avec `npm run build:offline` et réutilise les mêmes
 * composants React que la page « Mes téléchargements » du site.
 */
import { Component, type ReactNode } from "react";
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

/** Si une erreur survient pendant l'affichage, on la montre à l'écran au lieu d'un écran noir. */
class Garde extends Component<{ children: ReactNode }, { erreur: Error | null }> {
  state = { erreur: null as Error | null };

  static getDerivedStateFromError(erreur: Error) {
    return { erreur };
  }

  render() {
    if (!this.state.erreur) return this.props.children;
    return (
      <div style={{ padding: "calc(env(safe-area-inset-top) + 24px) 20px 24px", color: "#f5f5f5", fontFamily: "system-ui,sans-serif" }}>
        <h1 style={{ fontSize: 20, fontWeight: 800, margin: 0 }}>La page hors connexion a rencontré une erreur</h1>
        <p style={{ opacity: 0.7, fontSize: 14 }}>Envoie ce message au développeur :</p>
        <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12, background: "#1a1a1a", padding: 12, borderRadius: 12 }}>
          {String(this.state.erreur?.stack || this.state.erreur?.message || this.state.erreur)}
        </pre>
        <button
          onClick={() => location.reload()}
          style={{ marginTop: 12, height: 44, padding: "0 20px", borderRadius: 999, border: 0, background: "#f97316", color: "#fff", fontWeight: 700 }}
        >
          Réessayer
        </button>
      </div>
    );
  }
}

document.documentElement.classList.add("dark");
createRoot(document.getElementById("root")!).render(
  <Garde>
    <OfflineApp />
  </Garde>,
);
