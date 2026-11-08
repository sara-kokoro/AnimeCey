/**
 * Construit la page « Hors connexion » React de l'application Android.
 * Sortie : app/www/offline.html + app/www/assets/ (embarqués dans l'APK par `cap sync`).
 *   npm run build:offline
 */
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";

const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  root: here("./offline"),
  base: "./",
  plugins: [react(), tailwindcss()],
  // Tailwind 4 passe par son plugin Vite : on ignore postcss.config.js du projet principal.
  css: { postcss: { plugins: [] } },
  resolve: { alias: { "@": here("./src") } },
  build: {
    outDir: here("./app/www"),
    emptyOutDir: false, // on garde index.html et lottie/
    rollupOptions: { input: here("./offline/offline.html") },
  },
});
