/* AnimeCey Push Notification Service Worker */
self.addEventListener("push", (event) => {
  let data = { title: "AnimeCey", body: "Nouvelle notification" };
  try {
    data = event.data.json();
  } catch {
    /* fallback */
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/favicon.ico",
      badge: "/favicon.ico",
      data: data.url ?? "/",
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data ?? "/"));
});
