import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/catalogue")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Catalogue | Magi-Stream" },
      { name: "description", content: "Parcours tout le catalogue d'animés, films et séries." },
      { property: "og:title", content: "Catalogue | Magi-Stream" },
      { property: "og:description", content: "Parcours tout le catalogue d'animés, films et séries." },
    ],
  }),
  component: Catalogue,
});
