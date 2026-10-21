import { createFileRoute } from "@tanstack/react-router";
import Page from "@/pages/admin/AdminBroadcast";

export const Route = createFileRoute("/admin/broadcast")({
  ssr: false,
  head: () => ({ meta: [{ title: "Admin Diffusion | Magi-Stream" }, { name: "robots", content: "noindex" }] }),
  component: Page,
});
