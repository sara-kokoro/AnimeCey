import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/films")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Films | Magi-Stream" },
      { name: "description", content: "Longs métrages : animation et prises de vue réelles." },
      { property: "og:title", content: "Films | Magi-Stream" },
      { property: "og:description", content: "Longs métrages : animation et prises de vue réelles." },
    ],
  }),
  component: () => <Catalogue presetType="film"  title="Films" subtitle="Longs métrages : animation et prises de vue réelles." />,
});
