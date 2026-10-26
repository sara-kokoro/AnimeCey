import { createFileRoute } from "@tanstack/react-router";
import Telechargements from "@/pages/Telechargements";

export const Route = createFileRoute("/telechargements")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Mes Téléchargements | Magi-Stream" },
      { name: "description", content: "Regarde tes épisodes téléchargés hors ligne sur Magi-Stream." },
      { property: "og:title", content: "Mes Téléchargements | Magi-Stream" },
      { property: "og:description", content: "Regarde tes épisodes téléchargés hors ligne sur Magi-Stream." },
    ],
  }),
  component: Telechargements,
});
