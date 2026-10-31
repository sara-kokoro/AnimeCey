import { createFileRoute } from "@tanstack/react-router";
import Don from "@/pages/Don";

export const Route = createFileRoute("/don")({
  head: () => ({
    meta: [
      { title: "Faire un don | Magi-Stream" },
      { name: "description", content: "Soutiens Magi-Stream : ton don nous aide à garder le service gratuit." },
    ],
  }),
  component: Don,
});
