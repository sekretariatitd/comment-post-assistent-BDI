import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./client";

export type PostStatus = "new" | "skipped" | "drafted";
export type DraftStatus = "pending" | "approved" | "rejected" | "published" | "failed";

export interface Draft {
  id: string;
  post_id: string;
  template_id: string;
  template_version: number;
  text: string;
  edited_text: string | null;
  status: DraftStatus;
  model_name: string;
  created_at: string;
}

export interface Post {
  id: string;
  source_id: string;
  platform_post_id: string;
  url: string;
  text: string;
  thumbnail_url: string | null;
  published_at: string | null;
  fetched_at: string;
  relevance_score: number | null;
  relevance_reason: string | null;
  status: PostStatus;
  created_at: string;
  drafts: Draft[];
}

export interface PostPage {
  items: Post[];
  total: number;
  limit: number;
  offset: number;
}

export interface PostFilters {
  status?: PostStatus;
  source_id?: string;
  offset?: number;
}

export const PAGE_SIZE = 50;
const KEY = ["posts"];

export function usePosts(filters: PostFilters) {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
  for (const [k, v] of Object.entries(filters))
    if (v !== undefined && v !== "") params.set(k, String(v));
  return useQuery({
    queryKey: [...KEY, filters],
    queryFn: () => apiFetch<PostPage>(`/posts?${params}`),
    // Live updates arrive over the WebSocket in Phase 5; until then, poll (faster while the
    // worker is still scoring or drafting new posts).
    refetchInterval: (query) =>
      query.state.data?.items.some((p) => p.status === "new" && !p.relevance_reason)
        ? 4000
        : 30_000,
    placeholderData: (prev) => prev,
  });
}

export function useAddPost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { source_id: string; url: string; text: string }) =>
      apiFetch<Post>("/posts", { method: "POST", json: input }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useImportPosts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, payload }: { sourceId: string; payload: string }) =>
      apiFetch<{ found: number; new: number }>(`/posts/import/${sourceId}`, {
        method: "POST",
        json: { payload },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useRegenerate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ postId, templateId }: { postId: string; templateId?: string }) =>
      apiFetch<Post>(`/posts/${postId}/regenerate`, {
        method: "POST",
        json: { template_id: templateId || null },
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function usePollNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sourceId: string) =>
      apiFetch<{ queued: boolean }>(`/sources/${sourceId}/poll-now`, { method: "POST" }),
    onSuccess: () => {
      // The worker usually finishes within a few seconds.
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: KEY });
        qc.invalidateQueries({ queryKey: ["sources"] });
      }, 4000);
    },
  });
}
