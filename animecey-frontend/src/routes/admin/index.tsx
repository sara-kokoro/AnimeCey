import { createFileRoute } from "@tanstack/react-router";
import Page from "@/pages/admin/AdminDashboard";

export const Route = createFileRoute("/admin/")({
  ssr: false,
  head: () => ({ meta: [{ title: "Admin Tableau de bord | Magi-Stream" }, { name: "robots", content: "noindex" }] }),
  component: Page,
});
