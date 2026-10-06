import { apiFetch } from "./client";
import type { UserPreferences } from "../types/preferences";

export const preferencesApi = {
  get: () => apiFetch<UserPreferences>("/preferences"),

  update: (prefs: Partial<UserPreferences>) =>
    apiFetch<UserPreferences>("/preferences", { method: "PUT", body: JSON.stringify(prefs) }),

  setIntervalUnit: (useDistance: boolean) =>
    apiFetch<{ ok: boolean }>("/preferences/interval-unit", { method: "POST", body: JSON.stringify({ use_distance: useDistance }) }),
};
