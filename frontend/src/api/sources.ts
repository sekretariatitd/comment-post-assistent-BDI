import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./client";

export type Platform = "rss" | "manual" | "facebook" | "tiktok";

export const PLATFORMS: { value: Platform; label: string; hint: string }[] = [
  { value: "rss", label: "RSS / news site", hint: "Feed URL, e.g. https://example.com/rss" },
  { value: "manual", label: "Manual", hint: "Posts are added by hand (by URL)" },
  { value: "facebook", label: "Facebook", hint: "Page handle (fetching not available yet)" },
  { value: "tiktok", label: "TikTok", hint: "Account handle (fetching not available yet)" },
];

export type SourceStance = "ally" | "opponent" | "neutral";

export const STANCES: { value: SourceStance; label: string }[] = [
  { value: "ally", label: "Ally (we support them)" },
  { value: "opponent", label: "Opponent (we criticise them)" },
  { value: "neutral", label: "Neutral" },
];

export interface SourceInput {
  platform: Platform;
  display_name: string;
  url_or_handle: string;
  prompt_template_id: string | null;
  stance: SourceStance;
  poll_interval_minutes: number;
  is_active: boolean;
}

export interface Source extends SourceInput {
  id: string;
  adapter: string;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

const KEY = ["sources"];

export function useSources() {
  return useQuery({ queryKey: KEY, queryFn: () => apiFetch<Source[]>("/sources") });
}

export function useSaveSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id?: string; input: Partial<SourceInput> }) =>
      id
        ? apiFetch<Source>(`/sources/${id}`, { method: "PATCH", json: input })
        : apiFetch<Source>("/sources", { method: "POST", json: input }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/sources/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}
