import { apiFetch } from "./client";
import type { GarminStatus, GarminPushResult, GarminSyncResult } from "../types/garmin";

export const garminApi = {
  connect: (email: string, password: string) =>
    apiFetch<{ status: string }>("/garmin/connect", { method: "POST", body: JSON.stringify({ email, password }) }),

  status: () => apiFetch<GarminStatus>("/garmin/status"),

  push: (planId: number) =>
    apiFetch<GarminPushResult>(`/garmin/push/${planId}`, { method: "POST" }),

  sync: (planId: number) =>
    apiFetch<GarminSyncResult>(`/garmin/sync/${planId}`, { method: "POST" }),

  deleteWorkouts: (planId: number) =>
    apiFetch<{ deleted: number; failed: number }>(`/garmin/workouts/${planId}`, { method: "DELETE" }),

  autoPush: (planId: number, week: number, force?: boolean) =>
    apiFetch<GarminPushResult>(`/garmin/auto-push/${planId}`, { method: "POST", body: JSON.stringify({ week, force }) }),

  autoSync: (planId: number) =>
    apiFetch<GarminSyncResult>(`/garmin/auto-sync/${planId}`, { method: "POST" }),

  disconnect: () =>
    apiFetch<{ status: string }>("/garmin/disconnect", { method: "DELETE" }),
};
