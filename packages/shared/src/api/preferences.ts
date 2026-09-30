import { apiFetch } from "./client";
import type { UserPreferences } from "../types/preferences";

export const preferencesApi = {
  get: () => apiFetch<UserPreferences>("/preferences"),

  update: (prefs: Partial<UserPreferences>) =>
    apiFetch<UserPreferences>("/preferences", { method: "PUT", body: JSON.stringify(prefs) }),
};
