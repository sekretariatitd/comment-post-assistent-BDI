import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./client";

export interface TemplateFields {
  system_prompt: string;
  tone: string;
  language: string;
  max_length: number;
  relevance_rules: string;
  plain_e: boolean;
  no_dashes: boolean;
}

export interface TemplateInput extends TemplateFields {
  name: string;
  is_active: boolean;
}

export interface Template extends TemplateInput {
  id: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PreviewResult {
  relevance: { relevant: boolean; score: number; reason: string; would_draft: boolean };
  drafts: string[];
  model_name: string;
  template_version: number;
  threshold: number;
}

const KEY = ["templates"];

export function useTemplates() {
  return useQuery({ queryKey: KEY, queryFn: () => apiFetch<Template[]>("/templates") });
}

export function useTemplateDefaults() {
  return useQuery({
    queryKey: [...KEY, "defaults"],
    queryFn: () => apiFetch<{ relevance_rules: string }>("/templates/defaults"),
    staleTime: Infinity,
  });
}

export function useSaveTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id?: string; input: TemplateInput }) =>
      id
        ? apiFetch<Template>(`/templates/${id}`, { method: "PATCH", json: input })
        : apiFetch<Template>("/templates", { method: "POST", json: input }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/templates/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
}

export function usePreviewTemplate() {
  return useMutation({
    mutationFn: ({
      id,
      sampleText,
      overrides,
    }: {
      id: string;
      sampleText: string;
      overrides: TemplateFields;
    }) =>
      apiFetch<PreviewResult>(`/templates/${id}/preview`, {
        method: "POST",
        json: { sample_text: sampleText, overrides },
      }),
  });
}
