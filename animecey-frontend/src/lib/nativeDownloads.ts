/**
 * Pont avec l'application Android (Capacitor) : téléchargements en arrière-plan, avec notification
 * de progression et bouton « Annuler », gérés par le plugin natif MagiDownloader (dossier app/native).
 * Dans un navigateur normal, rien de tout ça n'existe : isNativeApp() renvoie false et le site
 * utilise les téléchargements internes du navigateur (IndexedDB).
 */

export interface NativeItem {
  episodeId: number;
  status: "pending" | "downloading" | "done" | "error" | "cancelled";
  /** 0 à 100 */
  progress: number;
  /** octets déjà enregistrés */
  size: number;
  /** chemin du fichier, quand le téléchargement est terminé */
  path?: string;
  error?: string;
  /** JSON : infos de l'épisode données au démarrage (titre, saison...) */
  meta?: string;
  downloadedAt?: number;
}

export interface NativePlugin {
  start(o: { episodeId: number; apiBase: string; meta: string; title: string; subtitle: string }): Promise<void>;
  cancel(o: { episodeId: number }): Promise<void>;
  remove(o: { episodeId: number }): Promise<void>;
  list(): Promise<{ items: NativeItem[] }>;
  requestPermissions(): Promise<unknown>;
  addListener(event: "downloadUpdate", cb: (item: NativeItem) => void): Promise<{ remove: () => Promise<void> }>;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function cap(): any {
  return typeof window === "undefined" ? undefined : (window as any).Capacitor;
}

export function isNativeApp(): boolean {
  try {
    const c = cap();
    return !!c?.isNativePlatform?.() && !!c?.Plugins?.MagiDownloader;
  } catch {
    return false;
  }
}

export function nativePlugin(): NativePlugin {
  return cap().Plugins.MagiDownloader as NativePlugin;
}

/** Adresse lisible par la page pour un fichier du téléphone. */
export function nativeFileUrl(path: string): string {
  return cap().convertFileSrc(path) as string;
}
