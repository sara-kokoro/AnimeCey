import { createFileRoute } from "@tanstack/react-router";
import Calendrier from "@/pages/Calendrier";

export const Route = createFileRoute("/calendrier")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Calendrier des sorties d'épisodes d'animés | Magi-Stream" },
      { name: "description", content: "Le planning de la semaine : jour et heure de sortie des nouveaux épisodes d'animés en VOSTFR et VF, mis à jour chaque jour sur Magi-Stream." },
      { property: "og:title", content: "Calendrier des sorties d'épisodes d'animés | Magi-Stream" },
      { property: "og:description", content: "Le planning de la semaine : jour et heure de sortie des nouveaux épisodes d'animés en VOSTFR et VF, mis à jour chaque jour sur Magi-Stream." },
    ],
  }),
  component: Calendrier,
});
