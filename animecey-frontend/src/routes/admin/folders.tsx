import { createFileRoute } from "@tanstack/react-router";
import Page from "@/pages/admin/AdminFolders";

export const Route = createFileRoute("/admin/folders")({
  ssr: false,
  head: () => ({ meta: [{ title: "Admin Dossiers | Magi-Stream" }, { name: "robots", content: "noindex" }] }),
  component: Page,
});
