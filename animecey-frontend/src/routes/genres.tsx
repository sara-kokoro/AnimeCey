import { createFileRoute } from "@tanstack/react-router";
import Genres from "@/pages/Genres";

export const Route = createFileRoute("/genres")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Genres | Magi-Stream" },
      { name: "description", content: "Explore les animés par genre." },
      { property: "og:title", content: "Genres | Magi-Stream" },
      { property: "og:description", content: "Explore les animés par genre." },
    ],
  }),
  component: Genres,
});
