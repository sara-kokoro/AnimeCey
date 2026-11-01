import { createFileRoute } from "@tanstack/react-router";
import Pub from "@/pages/Pub";

export const Route = createFileRoute("/pub")({
  head: () => ({
    meta: [
      { title: "Affiche ta pub sur Magi-Stream" },
      {
        name: "description",
        content: "Augmente ta visibilité auprès des fans d'animés, de films et de séries : affiche ta pub sur le site et l'application Magi-Stream.",
      },
    ],
  }),
  component: Pub,
});
