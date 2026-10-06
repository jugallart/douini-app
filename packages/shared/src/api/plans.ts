import { apiFetch } from "./client";
import type { PlanSummary, PlanDetail, PlanGeneratePayload, RefreshProposal, RegenerateResult, ReviewQueueItem, PlanSession } from "../types/plan";
import type { Celebration } from "../types/celebration";

export const plansApi = {
  generate: (payload: PlanGeneratePayload) =>
    apiFetch<{ plan_id: number }>("/plans/generate", { method: "POST", body: JSON.stringify(payload) }),

  list: () => apiFetch<PlanSummary[]>("/plans"),

  get: (id: number) => apiFetch<PlanDetail>(`/plans/${id}`),

  delete: (id: number, garminCleanup = false) =>
    apiFetch<{ status: string }>(`/plans/${id}${garminCleanup ? "?garmin_cleanup=true" : ""}`, { method: "DELETE" }),

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

  reviewQueue: (id: number) =>
    apiFetch<ReviewQueueItem[]>(`/plans/${id}/review-queue`),

  rejectAdjustment: (id: number, adjustmentId: number) =>
    apiFetch<{ id: number; status: string; restored: boolean; vdot_reverted?: number }>(`/plans/${id}/adjustments/${adjustmentId}/reject`, { method: "POST" }),

  restore: (id: number) =>
    apiFetch<Record<string, unknown>>(`/plans/${id}/adjustments/restore`, { method: "POST" }),

  syncAdjustmentGarmin: (id: number, adjustmentId: number) =>
    apiFetch<Record<string, unknown>>(`/plans/${id}/adjustments/${adjustmentId}/sync-garmin`, { method: "POST" }),

  paceChanges: (id: number, adjustmentId: number) =>
    apiFetch<Record<string, unknown>>(`/plans/${id}/adjustments/${adjustmentId}/pace-changes`),

  adjustments: (id: number) =>
    apiFetch<Record<string, unknown>[]>(`/plans/${id}/adjustments`),

  editWeek: (id: number, week: number, sessions: Partial<PlanSession>[]) =>
    apiFetch<{ status: string; week: number }>(`/plans/${id}/weeks/${week}`, { method: "PUT", body: JSON.stringify({ sessions }) }),

  deleteWeek: (id: number, week: number) =>
    apiFetch<{ status: string }>(`/plans/${id}/weeks/${week}`, { method: "DELETE" }),
};
