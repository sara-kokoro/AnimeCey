import { createFileRoute } from "@tanstack/react-router";
import Home from "@/pages/Home";

export const Route = createFileRoute("/")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Streaming d'animés en VF et VOSTFR | Magi-Stream" },
      { name: "description", content: "Regarde tes animés, films et séries préférés en streaming gratuit, en VF et VOSTFR." },
      { property: "og:title", content: "Streaming d'animés en VF et VOSTFR | Magi-Stream" },
      { property: "og:description", content: "Regarde tes animés, films et séries préférés en streaming gratuit, en VF et VOSTFR." },
    ],
  }),
  component: Home,
});
