export interface TokenStorage {
  getAccessToken(): string | null;
  getRefreshToken(): string | null;
  setTokens(access: string, refresh: string): void;
  clear(): void;
}

let storage: TokenStorage | null = null;
let apiBaseUrl: string | null = null;

export function configureClient(s: TokenStorage): void {
  storage = s;
}

export function getApiBaseUrl(): string {
  if (apiBaseUrl) return apiBaseUrl;
  if (typeof window !== "undefined") {
    return (import.meta as any).env?.VITE_API_URL || "/api/v1";
  }
  return "http://localhost:8000/api/v1";
}

export function setApiBaseUrl(url: string): void {
  apiBaseUrl = url;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${getApiBaseUrl()}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (storage?.getAccessToken()) {
    headers["Authorization"] = `Bearer ${storage.getAccessToken()}`;
  }

  let res = await fetch(url, { ...options, headers });

  if (res.status === 401 && storage?.getRefreshToken()) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers["Authorization"] = `Bearer ${storage.getAccessToken()}`;
      res = await fetch(url, { ...options, headers });
    }
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

async function tryRefresh(): Promise<boolean> {
  if (!storage?.getRefreshToken()) return false;
  try {
    const res = await fetch(`${getApiBaseUrl()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: storage.getRefreshToken() }),
    });
    if (!res.ok) {
      storage.clear();
      return false;
    }
    const data = await res.json();
    storage.setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    storage.clear();
    return false;
  }
}
