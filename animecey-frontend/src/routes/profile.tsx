import { createFileRoute } from "@tanstack/react-router";
import Profile from "@/pages/Profile";

export const Route = createFileRoute("/profile")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Mon profil | Magi-Stream" },
      { name: "description", content: "Ta liste, tes favoris et ton compte." },
      { property: "og:title", content: "Mon profil | Magi-Stream" },
      { property: "og:description", content: "Ta liste, tes favoris et ton compte." },
    ],
  }),
  component: Profile,
});
