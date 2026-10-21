import { createFileRoute } from "@tanstack/react-router";
import Auth from "@/pages/Auth";

export const Route = createFileRoute("/auth")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Connexion | Magi-Stream" },
      { name: "description", content: "Connecte-toi ou crée ton compte Magi-Stream." },
      { property: "og:title", content: "Connexion | Magi-Stream" },
      { property: "og:description", content: "Connecte-toi ou crée ton compte Magi-Stream." },
    ],
  }),
  component: Auth,
});
