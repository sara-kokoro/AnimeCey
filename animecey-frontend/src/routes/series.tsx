import { createFileRoute } from "@tanstack/react-router";
import Catalogue from "@/pages/Catalogue";

export const Route = createFileRoute("/series")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Séries | Magi-Stream" },
      { name: "description", content: "Des sagas épiques aux tranches de vie intimistes." },
      { property: "og:title", content: "Séries | Magi-Stream" },
      { property: "og:description", content: "Des sagas épiques aux tranches de vie intimistes." },
    ],
  }),
  component: () => <Catalogue presetType="serie"  title="Séries" subtitle="Des sagas épiques aux tranches de vie intimistes." />,
});
