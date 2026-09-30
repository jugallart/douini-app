import { apiFetch } from "./client";
import type { Session, SessionFeedbackPayload, FeedbackResult } from "../types/session";

export const sessionsApi = {
  get: (id: number) => apiFetch<Session>(`/sessions/${id}`),

  patch: (id: number, data: { status?: string }) =>
    apiFetch<Session>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  addFeedback: (id: number, payload: SessionFeedbackPayload) =>
    apiFetch<FeedbackResult>(`/sessions/${id}/feedback`, { method: "POST", body: JSON.stringify(payload) }),
};
