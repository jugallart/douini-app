import { apiFetch } from "./client";
import type { RunnerProfile, ProfileCompleteness } from "../types/profile";

export const profileApi = {
  get: () => apiFetch<RunnerProfile>("/profile"),

  update: (data: Partial<RunnerProfile>) =>
    apiFetch<RunnerProfile>("/profile", { method: "PUT", body: JSON.stringify(data) }),

  completeness: () => apiFetch<ProfileCompleteness>("/profile/completeness"),
};

export const accountApi = {
  delete: () => apiFetch<{ status: string }>("/account", { method: "DELETE" }),

  resetData: () => apiFetch<{ status: string }>("/account/reset-data", { method: "POST" }),

  updateIdentity: (data: { pseudo?: string; prenom?: string; nom?: string }) =>
    apiFetch<{ status: string }>("/account/identity", { method: "PUT", body: JSON.stringify(data) }),
};
