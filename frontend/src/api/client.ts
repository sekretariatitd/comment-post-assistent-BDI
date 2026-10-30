const TOKEN_KEY = "nca.token";
const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string): void {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      // Storage unavailable (private mode etc.); the session just won't survive a reload.
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      // ignore
    }
  },
};

let onUnauthorized: (() => void) | null = null;

/** Called when an authenticated request comes back 401 (expired or revoked token). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler;
}

type ApiInit = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

export async function apiFetch<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { json, headers: initHeaders, ...rest } = init;
  const headers = new Headers(initHeaders);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let body = rest.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  const res = await fetch(`${API_PREFIX}${path}`, { ...rest, headers, body });
  if (res.status === 401 && token) onUnauthorized?.();

  const data: unknown = res.status === 204 ? undefined : await res.json().catch(() => undefined);
  if (!res.ok) {
    throw new ApiError(res.status, errorMessage(data) ?? `Request failed (${res.status})`, data);
  }
  return data as T;
}

function errorMessage(data: unknown): string | undefined {
  if (data && typeof data === "object" && "detail" in data) {
    const { detail } = data as { detail: unknown };
    if (typeof detail === "string") return detail;
  }
  return undefined;
}
