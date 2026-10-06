import { apiFetch } from "./client";
import type { RaceResult, RaceResultPayload } from "../types/race";

export const raceResultsApi = {
  add: (payload: RaceResultPayload) =>
    apiFetch<RaceResult>("/race-results", { method: "POST", body: JSON.stringify(payload) }),

  get: (id: number) => apiFetch<RaceResult>(`/race-results/${id}`),

  list: () => apiFetch<RaceResult[]>("/race-results"),

  delete: (id: number) =>
    apiFetch<{ status: string }>(`/race-results/${id}`, { method: "DELETE" }),
};
