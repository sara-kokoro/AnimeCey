import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/films")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Films en streaming VF et VOSTFR gratuit | Magi-Stream" },
      { name: "description", content: "Films d'animation et films live en streaming gratuit, VF et VOSTFR, en HD sur Magi-Stream. Regarde ou télécharge pour voir hors ligne." },
      { property: "og:title", content: "Films en streaming VF et VOSTFR gratuit | Magi-Stream" },
      { property: "og:description", content: "Films d'animation et films live en streaming gratuit, VF et VOSTFR, en HD sur Magi-Stream. Regarde ou télécharge pour voir hors ligne." },
    ],
  }),
  component: () => <Catalogue presetType="film"  title="Films" subtitle="Longs métrages : animation et prises de vue réelles." />,
});
