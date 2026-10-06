import { apiFetch } from "./client";
import type { ReleaseNote } from "../types/releases";

export const releasesApi = {
  list: () => apiFetch<ReleaseNote[]>("/releases"),

  unread: () => apiFetch<ReleaseNote[]>("/releases/unread"),

  markRead: (version: string) =>
    apiFetch<{ ok: boolean }>(`/releases/${version}/read`, { method: "POST" }),

  markAllRead: () =>
    apiFetch<{ ok: boolean; marked: number }>("/releases/read-all", { method: "POST" }),
};
