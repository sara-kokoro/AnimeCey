/* Magi-Stream Push Notification Service Worker (notifications envoyées par notre propre backend).
 * Les notifications Monetag sont gérées par public/monetag-sw.js (importé dans /sw.js) :
 * on ignore donc tout push qui ne vient pas de chez nous (url relative « /... »), sans quoi
 * chaque notification Monetag s'afficherait en double. */
self.addEventListener("push", (event) => {
  let data = null;
  try {
    data = event.data.json();
  } catch {
    return;
  }
  if (!data || typeof data.url !== "string" || !data.url.startsWith("/")) return;
  event.waitUntil(
    self.registration.showNotification(data.title || "Magi-Stream", {
      body: data.body || "",
      icon: "/favicon.ico",
      badge: "/favicon.ico",
      data: { magi: true, url: data.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  const info = event.notification.data;
  if (!info || !info.magi) return; // notification d'une autre régie : son propre worker s'en occupe
  event.notification.close();
  event.waitUntil(clients.openWindow(info.url || "/"));
});
