import { apiFetch } from "./client";
import type { PlanSummary, PlanDetail, PlanGeneratePayload, RefreshProposal, RegenerateResult } from "../types/plan";
import type { Celebration } from "../types/celebration";

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

  getCelebration: (id: number) =>
    apiFetch<Celebration>(`/plans/${id}/celebration`),

  markCelebrationSeen: (id: number) =>
    apiFetch<{ status: string }>(`/plans/${id}/celebration/seen`, { method: "POST" }),

  regenerate: (id: number, fromWeek?: number) =>
    apiFetch<RegenerateResult>(`/plans/${id}/regenerate`, { method: "POST", body: JSON.stringify({ from_week: fromWeek }) }),
};
