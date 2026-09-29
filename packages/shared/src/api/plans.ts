import { apiFetch } from "./client";
import type { PlanSummary, PlanDetail, PlanGeneratePayload, RefreshProposal } from "../types/plan";

export const plansApi = {
  generate: (payload: PlanGeneratePayload) =>
    apiFetch<{ plan_id: number }>("/plans/generate", { method: "POST", body: JSON.stringify(payload) }),

  list: () => apiFetch<PlanSummary[]>("/plans"),

  get: (id: number) => apiFetch<PlanDetail>(`/plans/${id}`),

  delete: (id: number) =>
    apiFetch<{ status: string }>(`/plans/${id}`, { method: "DELETE" }),

  getRefreshProposal: (id: number) =>
    apiFetch<RefreshProposal>(`/plans/${id}/refresh-proposal`),

  acceptRefresh: (id: number, nextGoal?: Record<string, unknown>) =>
    apiFetch<{ status: string }>(`/plans/${id}/refresh-proposal/accept`, { method: "POST", body: JSON.stringify({ next_goal: nextGoal }) }),

  declineRefresh: (id: number) =>
    apiFetch<{ status: string }>(`/plans/${id}/refresh-proposal/decline`, { method: "POST" }),
};
