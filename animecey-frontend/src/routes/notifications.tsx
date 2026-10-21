import { createFileRoute } from "@tanstack/react-router";
import Notifications from "@/pages/Notifications";

export const Route = createFileRoute("/notifications")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Notifications | Magi-Stream" },
      { name: "description", content: "Tes notifications Magi-Stream." },
      { property: "og:title", content: "Notifications | Magi-Stream" },
      { property: "og:description", content: "Tes notifications Magi-Stream." },
    ],
  }),
  component: Notifications,
});
