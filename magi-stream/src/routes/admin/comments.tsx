import { createFileRoute } from "@tanstack/react-router";
import Page from "@/pages/admin/AdminComments";

export const Route = createFileRoute("/admin/comments")({
  ssr: false,
  head: () => ({ meta: [{ title: "Admin Commentaires | Magi-Stream" }, { name: "robots", content: "noindex" }] }),
  component: Page,
});
