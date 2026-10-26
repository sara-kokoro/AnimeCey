/**
 * Enregistrement du service worker hors ligne (/sw.js), généré par vite-plugin-pwa.
 * Jamais en dev ni dans les previews Lovable : uniquement sur le site publié.
 * `?sw=off` dans l'URL désenregistre le worker (kill switch).
 */

const PREVIEW_LABEL = /^(?:id-preview|preview)(?:-[a-z0-9]+)?--.+$/;
const PREVIEW_DOMAIN_SUFFIXES = [".lovable.app", ".gpt-eng.com", ".gptengineer.run"];
const BLOCKED_HOST_SUFFIXES = [".lovableproject.com", ".lovableproject-dev.com", ".beta.lovable.dev"];

function isRefusedContext(): boolean {
  if (!import.meta.env.PROD) return true;
  if (window.self !== window.top) return true; // iframe (preview Lovable)
  const host = window.location.hostname.toLowerCase();
  const firstLabel = host.split(".")[0] ?? "";
  if (PREVIEW_DOMAIN_SUFFIXES.some((d) => host.endsWith(d)) && PREVIEW_LABEL.test(firstLabel)) return true;
  if (BLOCKED_HOST_SUFFIXES.some((d) => host === d.slice(1) || host.endsWith(d))) return true;
  if (new URLSearchParams(window.location.search).get("sw") === "off") return true;
  return false;
}

async function unregisterAppSw(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const regs = await navigator.serviceWorker.getRegistrations();
  await Promise.allSettled(
    regs
      .filter((r) => r.active?.scriptURL.endsWith("/sw.js") || r.waiting?.scriptURL.endsWith("/sw.js"))
      .map((r) => r.unregister()),
  );
}

export async function registerAppSw(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  if (isRefusedContext()) {
    await unregisterAppSw();
    return;
  }
  try {
    await navigator.serviceWorker.register("/sw.js");
  } catch {
    /* enregistrement impossible : l'app reste utilisable en ligne */
  }
}
