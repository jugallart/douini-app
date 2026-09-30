import { apiFetch } from "./client";
import type { Notification } from "../types/notifications";

export const notificationsApi = {
  list: () => apiFetch<Notification[]>("/notifications"),

  markRead: (id: number) =>
    apiFetch<{ status: string }>(`/notifications/${id}/read`, { method: "POST" }),

  markAllRead: () =>
    apiFetch<{ marked_read: number }>("/notifications/read-all", { method: "POST" }),
};
