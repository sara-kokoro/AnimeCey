import { createFileRoute } from "@tanstack/react-router";
import Home from "@/pages/Home";

export const Route = createFileRoute("/")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Magi-Stream : animés en streaming VF et VOSTFR gratuit, films et séries" },
      { name: "description", content: "Magi-Stream (Magi Stream) : regarde tes animés en streaming VF et VOSTFR gratuit, ainsi que des films et séries en HD, sur le site et l'application Android. Mushoku Tensei, Deadpool, One Piece et plus." },
      { property: "og:title", content: "Magi-Stream : animés en streaming VF et VOSTFR gratuit, films et séries" },
      { property: "og:description", content: "Magi-Stream (Magi Stream) : regarde tes animés en streaming VF et VOSTFR gratuit, ainsi que des films et séries en HD, sur le site et l'application Android. Mushoku Tensei, Deadpool, One Piece et plus." },
    ],
  }),
  component: Home,
});
