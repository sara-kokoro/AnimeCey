import { create } from "zustand";
import {
  fetchNotifications,
  fetchUnreadCount,
  markAllAsRead as apiMarkAllAsRead,
  markAsRead as apiMarkAsRead,
  type Notification,
} from "@/api/notifications";

interface NotifState {
  notifications: Notification[];
  unreadCount: number;
  isLoading: boolean;
  load: () => Promise<void>;
  loadUnread: () => Promise<void>;
  markAllAsRead: () => Promise<void>;
  markAsRead: (id: number) => Promise<void>;
}

export const useNotificationStore = create<NotifState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  isLoading: false,
  load: async () => {
    set({ isLoading: true });
    try {
      const data = await fetchNotifications(1, 50);
      set({ notifications: data.items, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },
  loadUnread: async () => {
    try {
      const count = await fetchUnreadCount();
      set({ unreadCount: count });
    } catch {
      /* ignore */
    }
  },
  markAllAsRead: async () => {
    try {
      await apiMarkAllAsRead();
      const next = get().notifications.map((n) => ({ ...n, is_read: true }));
      set({ notifications: next, unreadCount: 0 });
    } catch {
      /* ignore */
    }
  },
  markAsRead: async (id) => {
    try {
      await apiMarkAsRead(id);
      const next = get().notifications.map((n) => (n.id === id ? { ...n, is_read: true } : n));
      set({ notifications: next, unreadCount: next.filter((n) => !n.is_read).length });
    } catch {
      /* ignore */
    }
  },
}));
