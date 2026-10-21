import { createFileRoute } from "@tanstack/react-router";
import Watch from "@/pages/Watch";

export const Route = createFileRoute("/watch/$id")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Lecture | Magi-Stream" },
      { name: "description", content: "Regarde ton épisode en VF ou VOSTFR sur Magi-Stream." },
      { property: "og:title", content: "Lecture | Magi-Stream" },
      { property: "og:description", content: "Regarde ton épisode en VF ou VOSTFR sur Magi-Stream." },
    ],
  }),
  component: Watch,
});
