import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/films-japanime")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Films d'animation japonaise en streaming VF et VOSTFR | Magi-Stream" },
      { name: "description", content: "Les longs métrages d'animation japonaise en streaming gratuit, VF et VOSTFR : Your Name, Les Enfants du temps et bien d'autres sur Magi-Stream." },
      { property: "og:title", content: "Films d'animation japonaise en streaming VF et VOSTFR | Magi-Stream" },
      { property: "og:description", content: "Les longs métrages d'animation japonaise en streaming gratuit, VF et VOSTFR : Your Name, Les Enfants du temps et bien d'autres sur Magi-Stream." },
    ],
  }),
  component: () => <Catalogue presetType="film" presetCategory="anime" title="Films Japanime" subtitle="Les longs métrages d'animation japonaise : Your Name, Les Enfants du temps et bien d'autres." />,
});
