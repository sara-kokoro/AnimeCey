import { createFileRoute } from "@tanstack/react-router";
import Search from "@/pages/Search";

export const Route = createFileRoute("/search")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Recherche | Magi-Stream" },
      { name: "description", content: "Recherche instantanée parmi tous les animés, films et séries." },
      { property: "og:title", content: "Recherche | Magi-Stream" },
      { property: "og:description", content: "Recherche instantanée parmi tous les animés, films et séries." },
    ],
  }),
  component: Search,
});
