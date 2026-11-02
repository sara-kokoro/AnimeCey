import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/series")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Séries en streaming VF et VOSTFR gratuit | Magi-Stream" },
      { name: "description", content: "Séries et animés en streaming gratuit, en VF et VOSTFR, en HD sur Magi-Stream : sagas épiques, tranches de vie, nouveautés de la saison." },
      { property: "og:title", content: "Séries en streaming VF et VOSTFR gratuit | Magi-Stream" },
      { property: "og:description", content: "Séries et animés en streaming gratuit, en VF et VOSTFR, en HD sur Magi-Stream : sagas épiques, tranches de vie, nouveautés de la saison." },
    ],
  }),
  component: () => <Catalogue presetType="serie"  title="Séries" subtitle="Des sagas épiques aux tranches de vie intimistes." />,
});
