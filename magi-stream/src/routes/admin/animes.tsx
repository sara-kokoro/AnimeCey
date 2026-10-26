import { createFileRoute } from "@tanstack/react-router";
import Page from "@/pages/admin/AdminAnimes";

export const Route = createFileRoute("/admin/animes")({
  ssr: false,
  head: () => ({ meta: [{ title: "Admin Animés | Magi-Stream" }, { name: "robots", content: "noindex" }] }),
  component: Page,
});
