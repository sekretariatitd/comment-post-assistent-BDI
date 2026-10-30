import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./client";
import type { Draft } from "./posts";
import type { Platform } from "./sources";

function useDraftMutation<V>(fn: (vars: V) => Promise<Draft>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["posts"] });
      qc.invalidateQueries({ queryKey: ["activity"] });
    },
  });
}

export function useEditDraft() {
  return useDraftMutation(({ id, text }: { id: string; text: string }) =>
    apiFetch<Draft>(`/drafts/${id}`, { method: "PATCH", json: { text } }),
  );
}

export function useApproveDraft() {
  return useDraftMutation((id: string) =>
    apiFetch<Draft>(`/drafts/${id}/approve`, { method: "POST" }),
  );
}

export function useRejectDraft() {
  return useDraftMutation((id: string) =>
    apiFetch<Draft>(`/drafts/${id}/reject`, { method: "POST" }),
  );
}

export function useMarkPublished() {
  return useDraftMutation((id: string) =>
    apiFetch<Draft>(`/drafts/${id}/mark-published`, { method: "POST" }),
  );
}

export interface Activity {
  id: string;
  created_at: string;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  payload: Record<string, unknown>;
}

export interface ActivityPage {
  items: Activity[];
  total: number;
  limit: number;
  offset: number;
}

export const ACTIVITY_PAGE_SIZE = 50;

export function useActivity(action: string, offset: number) {
  const params = new URLSearchParams({ limit: String(ACTIVITY_PAGE_SIZE), offset: String(offset) });
  if (action) params.set("action", action);
  return useQuery({
    queryKey: ["activity", action, offset],
    queryFn: () => apiFetch<ActivityPage>(`/activity?${params}`),
    placeholderData: (prev) => prev,
  });
}

export interface AppSettings {
  relevance_threshold: number;
  max_comments_per_hour: number;
  enable_automated_publishing: boolean;
  anthropic_model: string;
  anthropic_configured: boolean;
}

export function useAppSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: () => apiFetch<AppSettings>("/settings"),
  });
}

export interface PostingAccount {
  id: string;
  platform: Platform;
  display_name: string;
  is_active: boolean;
  has_credentials: boolean;
  updated_at: string;
}

export function usePostingAccounts() {
  return useQuery({
    queryKey: ["posting-accounts"],
    queryFn: () => apiFetch<PostingAccount[]>("/posting-accounts"),
  });
}

export function useSavePostingAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      platform,
      display_name,
      is_active,
    }: {
      platform: Platform;
      display_name: string;
      is_active: boolean;
    }) =>
      apiFetch<PostingAccount>(`/posting-accounts/${platform}`, {
        method: "PUT",
        json: { display_name, is_active },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["posting-accounts"] }),
  });
}
