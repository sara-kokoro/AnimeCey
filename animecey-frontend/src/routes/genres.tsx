import { createFileRoute } from "@tanstack/react-router";
import Genres from "@/pages/Genres";

export const Route = createFileRoute("/genres")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Animés par genre : action, romance, isekai… en streaming | Magi-Stream" },
      { name: "description", content: "Explore les animés, films et séries par genre en streaming gratuit VF et VOSTFR sur Magi-Stream." },
      { property: "og:title", content: "Animés par genre : action, romance, isekai… en streaming | Magi-Stream" },
      { property: "og:description", content: "Explore les animés, films et séries par genre en streaming gratuit VF et VOSTFR sur Magi-Stream." },
    ],
  }),
  component: Genres,
});
