import { apiFetch } from "./client";
import type { Session, SessionFeedbackPayload } from "../types/session";

export const sessionsApi = {
  get: (id: number) => apiFetch<Session>(`/sessions/${id}`),

  patch: (id: number, data: { status?: string }) =>
    apiFetch<Session>(`/sessions/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  addFeedback: (id: number, payload: SessionFeedbackPayload) =>
    apiFetch<unknown>(`/sessions/${id}/feedback`, { method: "POST", body: JSON.stringify(payload) }),
};
