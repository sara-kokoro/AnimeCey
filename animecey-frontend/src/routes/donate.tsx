import { createFileRoute } from "@tanstack/react-router";
import Don from "@/pages/Don";

export const Route = createFileRoute("/donate")({
  head: () => ({
    meta: [
      { title: "Faire un don | Magi-Stream" },
      { name: "description", content: "Soutiens Magi-Stream par Mobile Money : choisis ton montant, sans frais, et aide-nous à garder le service gratuit." },
    ],
  }),
  component: Don,
});
