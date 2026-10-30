import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "./client";

export type UserRole = "admin" | "reviewer";

export interface User {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", { method: "POST", json: { email, password } });
}

/** Writes to sources/templates are admin-only (enforced by the API too). */
export function useIsAdmin(): boolean {
  return useMe(true).data?.role === "admin";
}

export function useMe(enabled: boolean) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/auth/me"),
    enabled,
    retry: false,
    staleTime: 5 * 60_000,
  });
}
