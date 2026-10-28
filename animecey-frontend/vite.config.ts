// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
  vite: {
    plugins: [
      VitePWA({
        registerType: "autoUpdate",
        // L'enregistrement passe uniquement par src/lib/pwaRegister.ts (gardes preview/dev).
        injectRegister: null,
        devOptions: { enabled: false },
        filename: "sw.js",
        // Le manifeste existe déjà : public/site.webmanifest
        manifest: false,
        workbox: {
          // Notifications push : nos notifications (push-sw.js) et celles de Monetag (monetag-sw.js) sont importées dans le worker généré.
          importScripts: ["/push-sw.js", "/monetag-sw.js"],
          navigateFallback: "/index.html",
          navigateFallbackDenylist: [/^\/~oauth/, /^\/api\//],
          runtimeCaching: [
            {
              // Pages HTML : réseau d'abord, cache en secours (hors ligne).
              urlPattern: ({ request }: { request: Request }) => request.mode === "navigate",
              handler: "NetworkFirst",
              options: {
                cacheName: "magi-html",
                networkTimeoutSeconds: 5,
                expiration: { maxEntries: 50, maxAgeSeconds: 7 * 24 * 3600 },
              },
            },
            {
              // Assets buildés (hashés) du même domaine : cache d'abord.
              urlPattern: ({ url }: { url: URL }) =>
                url.origin === self.location.origin && /\/assets\/.+\.[a-z0-9]{8,}\./i.test(url.pathname),
              handler: "CacheFirst",
              options: {
                cacheName: "magi-assets",
                expiration: { maxEntries: 200, maxAgeSeconds: 30 * 24 * 3600 },
              },
            },
          ],
        },
      }),
    ],
  },
});
