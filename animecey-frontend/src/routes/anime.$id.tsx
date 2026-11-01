import { createFileRoute } from "@tanstack/react-router";
import AnimeDetail from "@/pages/AnimeDetail";
import type { Anime } from "@/types";

const SITE = "https://www.magi-stream.online";
const API_BASE = import.meta.env.VITE_API_URL ?? "https://yumeflowerbot.koyeb.app/api";

const clean = (s: string, n: number) => {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n - 1).trimEnd()}…` : t;
};

export const Route = createFileRoute("/anime/$id")({
  // "data-only" : le serveur récupère la fiche pour écrire le <head> (titre, description, image),
  // visibles par Google dès le HTML ; la page elle-même reste affichée côté navigateur.
  ssr: "data-only",
  loader: async ({ params }): Promise<Anime | null> => {
    try {
      const res = await fetch(`${API_BASE}/animes/${params.id}`, { signal: AbortSignal.timeout(8000) });
      return res.ok ? ((await res.json()) as Anime) : null;
    } catch {
      return null;
    }
  },
  head: ({ loaderData, params }) => {
    const a = loaderData;
    if (!a) {
      return { meta: [{ title: "Animé en streaming VF et VOSTFR | Magi-Stream" }] };
    }
    const kind = a.category === "live" ? (a.type === "film" ? "film" : "série") : a.type === "film" ? "film" : "animé";
    const langs = a.languages_available?.length ? a.languages_available.join(" et ") : "VF et VOSTFR";
    const title = `${a.title} ${kind === "film" ? "film complet" : "saison et épisodes"} en streaming ${langs} gratuit | Magi-Stream`;
    const description = clean(
      `Regarde ${a.title} (${kind}) en streaming ${langs} gratuit et en HD sur Magi-Stream. ${a.synopsis || ""}`,
      160,
    );
    const url = `${SITE}/anime/${params.id}`;
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: kind === "film" ? "video.movie" : "video.tv_show" },
        { property: "og:url", content: url },
        ...(a.poster_url ? [{ property: "og:image", content: a.poster_url }] : []),
        { name: "twitter:card", content: "summary_large_image" },
      ],
      links: [{ rel: "canonical", href: url }],
    };
  },
  component: AnimeDetail,
});
