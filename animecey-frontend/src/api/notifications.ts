import api from "./axios";

export interface Notification {
  id: number;
  title: string;
  content: string;
  image_url?: string;
  caption?: string;
  type: "info" | "new" | "alert" | "maintenance";
  is_read: boolean;
  created_at: string;
}

export interface PaginatedNotifications {
  items: Notification[];
  total: number;
  page: number;
  pages: number;
}

export async function fetchNotifications(page = 1, limit = 20): Promise<PaginatedNotifications> {
  const res = await api.get("/notifications", { params: { page, limit } });
  return res.data;
}

export async function fetchUnreadCount(): Promise<number> {
  const res = await api.get("/notifications/unread-count");
  return res.data.count;
}

export async function markAsRead(id: number) {
  await api.post(`/notifications/${id}/read`);
}

export async function markAllAsRead() {
  await api.post("/notifications/read-all");
}
