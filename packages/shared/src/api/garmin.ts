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

  disconnect: () =>
    apiFetch<{ status: string }>("/garmin/disconnect", { method: "DELETE" }),
};
