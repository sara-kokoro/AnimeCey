import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/films-japanime")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Films Japanime | Magi-Stream" },
      { name: "description", content: "Les longs métrages d'animation japonaise : Your Name, Les Enfants du temps et bien d'autres." },
      { property: "og:title", content: "Films Japanime | Magi-Stream" },
      { property: "og:description", content: "Les longs métrages d'animation japonaise : Your Name, Les Enfants du temps et bien d'autres." },
    ],
  }),
  component: () => <Catalogue presetType="film" presetCategory="anime" title="Films Japanime" subtitle="Les longs métrages d'animation japonaise : Your Name, Les Enfants du temps et bien d'autres." />,
});
