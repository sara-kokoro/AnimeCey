import { createFileRoute } from "@tanstack/react-router";
import Page from "@/pages/admin/AdminUsers";

export const Route = createFileRoute("/admin/users")({
  ssr: false,
  head: () => ({ meta: [{ title: "Admin Utilisateurs | Magi-Stream" }, { name: "robots", content: "noindex" }] }),
  component: Page,
});
