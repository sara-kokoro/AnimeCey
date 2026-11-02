import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/catalogue")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Catalogue d'animés, films et séries en streaming VF et VOSTFR | Magi-Stream" },
      { name: "description", content: "Tout le catalogue Magi-Stream : animés, films et séries en streaming gratuit, VF et VOSTFR. Filtre par genre, année, langue et statut." },
      { property: "og:title", content: "Catalogue d'animés, films et séries en streaming VF et VOSTFR | Magi-Stream" },
      { property: "og:description", content: "Tout le catalogue Magi-Stream : animés, films et séries en streaming gratuit, VF et VOSTFR. Filtre par genre, année, langue et statut." },
    ],
  }),
  component: Catalogue,
});
