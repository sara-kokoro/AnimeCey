/**
 * Réglages de l'application Android (stockés sur le téléphone).
 * « Wi-Fi seulement » est activé par défaut pour ne pas vider le forfait mobile.
 */
const WIFI_KEY = "magi:wifiOnly";

export function getWifiOnly(): boolean {
  try {
    return localStorage.getItem(WIFI_KEY) !== "0";
  } catch {
    return true;
  }
}

export function setWifiOnly(on: boolean): void {
  try {
    localStorage.setItem(WIFI_KEY, on ? "1" : "0");
  } catch {
    /* stockage indisponible : le réglage vaut pour cette visite seulement */
  }
}

/* eslint-disable @typescript-eslint/no-explicit-any */
/** true si le téléphone est sur Wi-Fi. En cas de doute, renvoie true (on ne bloque pas à tort). */
export function isOnWifi(): boolean {
  try {
    const native = (window as any).MagiNative;
    if (native?.isWifi) return !!native.isWifi();
    const type = (navigator as any).connection?.type;
    if (type) return type !== "cellular";
  } catch {
    /* ignoré */
  }
  return true;
}
