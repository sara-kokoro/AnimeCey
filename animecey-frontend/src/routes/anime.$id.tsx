import { createFileRoute } from "@tanstack/react-router";
import AnimeDetail from "@/pages/AnimeDetail";

export const Route = createFileRoute("/anime/$id")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Fiche animé | Magi-Stream" },
      { name: "description", content: "Synopsis, épisodes et animés liés sur Magi-Stream." },
      { property: "og:title", content: "Fiche animé | Magi-Stream" },
      { property: "og:description", content: "Synopsis, épisodes et animés liés sur Magi-Stream." },
    ],
  }),
  component: AnimeDetail,
});
