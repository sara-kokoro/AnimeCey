import { createFileRoute } from "@tanstack/react-router";
import Calendrier from "@/pages/Calendrier";

export const Route = createFileRoute("/calendrier")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Calendrier des sorties | Magi-Stream" },
      { name: "description", content: "Le planning hebdomadaire des sorties d'épisodes." },
      { property: "og:title", content: "Calendrier des sorties | Magi-Stream" },
      { property: "og:description", content: "Le planning hebdomadaire des sorties d'épisodes." },
    ],
  }),
  component: Calendrier,
});
