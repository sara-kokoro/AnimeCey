import { createFileRoute } from "@tanstack/react-router";

const SITE = "https://www.magi-stream.online";
const API_BASE = import.meta.env.VITE_API_URL ?? "https://yumeflowerbot.koyeb.app/api";

// Pages publiques fixes (les fiches animé sont ajoutées depuis l'API).
const STATIC_PAGES: { path: string; priority: string; changefreq: string }[] = [
  { path: "/", priority: "1.0", changefreq: "daily" },
  { path: "/catalogue", priority: "0.9", changefreq: "daily" },
  { path: "/series", priority: "0.8", changefreq: "daily" },
  { path: "/films", priority: "0.8", changefreq: "daily" },
  { path: "/films-japanime", priority: "0.7", changefreq: "daily" },
  { path: "/calendrier", priority: "0.7", changefreq: "daily" },
  { path: "/genres", priority: "0.6", changefreq: "weekly" },
];

function esc(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export const Route = createFileRoute("/sitemap.xml")({
  server: {
    handlers: {
      GET: async () => {
        let entries: { id: number; updated_at: string | null }[] = [];
        try {
          const res = await fetch(`${API_BASE}/animes/sitemap/entries`, { signal: AbortSignal.timeout(10_000) });
          if (res.ok) entries = await res.json();
        } catch {
          // API injoignable : on sert quand même les pages fixes.
        }

        const urls = [
          ...STATIC_PAGES.map(
            (p) =>
              `  <url><loc>${SITE}${p.path}</loc><changefreq>${p.changefreq}</changefreq><priority>${p.priority}</priority></url>`,
          ),
          ...entries.map((e) => {
            const lastmod = e.updated_at ? `<lastmod>${esc(e.updated_at.slice(0, 10))}</lastmod>` : "";
            return `  <url><loc>${SITE}/anime/${e.id}</loc>${lastmod}<changefreq>weekly</changefreq><priority>0.8</priority></url>`;
          }),
        ];

        const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join("\n")}\n</urlset>\n`;
        return new Response(xml, {
          headers: {
            "content-type": "application/xml; charset=utf-8",
            "cache-control": "public, max-age=3600, s-maxage=3600",
          },
        });
      },
    },
  },
});
