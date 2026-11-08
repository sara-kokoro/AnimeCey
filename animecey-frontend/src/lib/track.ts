import api from "@/api/axios";
import { isNativeApp } from "@/lib/nativeDownloads";

/** Identifiant anonyme de l'appareil (aucune donnée personnelle) : sert aux statistiques d'audience. */
export function deviceId(): string {
  try {
    let id = localStorage.getItem("magi_device_id");
    if (!id) {
      id = (crypto.randomUUID?.() ?? `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 12)}`).replace(/-/g, "");
      localStorage.setItem("magi_device_id", id);
    }
    return id;
  } catch {
    return "anon";
  }
}

const platform = () => (isNativeApp() ? "app" : "web");

/** À l'ouverture du site / de l'app : compte l'appareil (utilisé par /stats dans le bot). */
export function trackPing(): void {
  if (typeof window === "undefined") return;
  // au plus une fois toutes les 6 h par appareil : évite d'écrire dans la base à chaque ouverture
  try {
    const last = Number(localStorage.getItem("magi:pingAt") ?? 0);
    if (Date.now() - last < 6 * 3_600_000) return;
    localStorage.setItem("magi:pingAt", String(Date.now()));
  } catch {
    /* stockage indisponible : on envoie */
  }
  void api.post("/track/ping", { device_id: deviceId(), platform: platform() }).catch(() => undefined);
}

/** Quand un épisode est ouvert : alimente les « plus regardés » de /stats. */
export function trackView(episodeId: number, animeId?: number): void {
  if (typeof window === "undefined") return;
  void api
    .post("/track/view", { device_id: deviceId(), episode_id: episodeId, anime_id: animeId, platform: platform() })
    .catch(() => undefined);
}
