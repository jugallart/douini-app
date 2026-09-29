import { apiFetch } from "./client";
import type { RunnerProfile, ProfileCompleteness } from "../types/profile";

export const profileApi = {
  get: () => apiFetch<RunnerProfile>("/profile"),

  update: (data: Partial<RunnerProfile>) =>
    apiFetch<RunnerProfile>("/profile", { method: "PUT", body: JSON.stringify(data) }),

  completeness: () => apiFetch<ProfileCompleteness>("/profile/completeness"),
};
