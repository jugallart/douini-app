import { apiFetch } from "./client";
import type { Stats } from "../types";

export const statsApi = {
  get: () => apiFetch<Stats>("/statistics"),
};
