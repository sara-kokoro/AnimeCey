import { useEffect, useState } from "react";
import { Smartphone } from "lucide-react";
import { APP } from "@/config/app";
import { isNativeApp } from "@/lib/nativeDownloads";

/**
 * Bouton « Télécharger notre application » (APK Android).
 * Caché dans l'application elle-même, où il n'a plus de sens.
 * - variant="banner" : grande carte, pour l'accueil
 * - variant="inline" : lien compact, pour le pied de page
 */
export function AppDownloadButton({ variant = "banner" }: { variant?: "banner" | "inline" }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    setShow(!isNativeApp()); // décidé côté navigateur uniquement (évite un décalage avec le rendu serveur)
  }, []);

  if (!show || !APP.apkUrl.trim()) return null;

  if (variant === "inline") {
    return (
      <a
        href={APP.apkUrl}
        download
        className="inline-flex items-center gap-1.5 text-sm font-body font-semibold text-primary hover:text-primary-dim"
      >
        <Smartphone className="w-4 h-4" /> Télécharger notre application
      </a>
    );
  }

  return (
    <a
      href={APP.apkUrl}
      download
      className="mt-4 flex items-center gap-3 rounded-2xl border border-primary/40 bg-primary/10 p-3.5 hover:bg-primary/15 transition-colors"
    >
      <span className="shrink-0 w-11 h-11 rounded-xl bg-primary text-primary-foreground flex items-center justify-center">
        <Smartphone className="w-5 h-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-display font-bold text-sm">Télécharger notre application</span>
        <span className="block text-xs text-muted-foreground">
          Android · téléchargements en arrière-plan et lecture hors ligne
        </span>
      </span>
      <span className="shrink-0 rounded-full bg-primary text-primary-foreground px-4 py-2 text-xs font-bold">Installer</span>
    </a>
  );
}
