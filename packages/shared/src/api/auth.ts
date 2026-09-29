import { apiFetch } from "./client";
import type { AuthTokens, SignupPayload, LoginPayload, ResetPasswordPayload, User } from "../types/auth";

export const authApi = {
  signup: (payload: SignupPayload) =>
    apiFetch<AuthTokens>("/auth/signup", { method: "POST", body: JSON.stringify(payload) }),

  login: (payload: LoginPayload) =>
    apiFetch<AuthTokens>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),

  logout: (refreshToken: string) =>
    apiFetch<{ status: string }>("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) }),

  verifyEmail: (token: string) =>
    apiFetch<{ status: string }>("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }),

  resendVerification: (email: string) =>
    apiFetch<{ status: string }>("/auth/resend-verification", { method: "POST", body: JSON.stringify({ email }) }),

  forgotPassword: (email: string) =>
    apiFetch<{ status: string }>("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }),

  resetPassword: (payload: ResetPasswordPayload) =>
    apiFetch<{ status: string }>("/auth/reset-password", { method: "POST", body: JSON.stringify(payload) }),

  me: () => apiFetch<User>("/auth/me"),
};
