import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/genre/$slug")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Genre | Magi-Stream" },
      { name: "description", content: "Les animés de ce genre sur Magi-Stream." },
      { property: "og:title", content: "Genre | Magi-Stream" },
      { property: "og:description", content: "Les animés de ce genre sur Magi-Stream." },
    ],
  }),
  component: Catalogue,
});
