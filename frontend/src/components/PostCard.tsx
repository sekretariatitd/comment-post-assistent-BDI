import { useState } from "react";

import { useRegenerate, type Draft, type Post } from "../api/posts";
import { useApproveDraft, useEditDraft, useMarkPublished, useRejectDraft } from "../api/review";
import { PLATFORMS, type Source } from "../api/sources";
import type { Template } from "../api/templates";
import { formatDate } from "../lib/format";
import { Badge, Button, ErrorText, Select } from "./ui";

const POST_TONE = { new: "slate", skipped: "amber", drafted: "green" } as const;
const DRAFT_TONE = {
  pending: "slate",
  approved: "green",
  published: "green",
  failed: "red",
  rejected: "slate",
} as const;

export function PostCard({
  post,
  source,
  templates,
}: {
  post: Post;
  source?: Source;
  templates: Template[];
}) {
  const [title, ...rest] = post.text.split("\n\n");
  const regenerate = useRegenerate();
  const [templateId, setTemplateId] = useState(
    source?.prompt_template_id ?? templates.find((t) => t.is_active)?.id ?? "",
  );
  const scoring = post.status === "new" && post.relevance_score === null && !post.relevance_reason;
  const maxLength = (d: Draft) => templates.find((t) => t.id === d.template_id)?.max_length;

  return (
    <li className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex gap-4">
        {post.thumbnail_url && (
          <img
            src={post.thumbnail_url}
            alt=""
            loading="lazy"
            className="h-20 w-28 shrink-0 rounded-md bg-slate-100 object-cover"
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="font-medium text-slate-700">
              {source?.display_name ?? "Unknown source"}
            </span>
            {source && <span>{PLATFORMS.find((x) => x.value === source.platform)?.label}</span>}
            <span>·</span>
            <span title="Published">{formatDate(post.published_at ?? post.fetched_at)}</span>
            <Badge tone={POST_TONE[post.status]}>{post.status}</Badge>
            {post.relevance_score !== null && <span>score {post.relevance_score.toFixed(2)}</span>}
            {scoring && <span className="animate-pulse text-indigo-600">scoring…</span>}
          </div>
          <a
            href={post.url}
            target="_blank"
            rel="noreferrer"
            className="font-medium text-slate-900 hover:text-indigo-700 hover:underline"
          >
            {title}
          </a>
          {rest.length > 0 && (
            <p className="mt-1 line-clamp-2 text-sm text-slate-600">{rest.join(" ")}</p>
          )}
          {post.relevance_reason && (
            <p className="mt-2 text-xs text-slate-500">Why: {post.relevance_reason}</p>
          )}
        </div>
      </div>

      {post.drafts.length > 0 && (
        <ol className="mt-4 space-y-2">
          {post.drafts.map((d, i) => (
            <DraftItem
              key={d.id}
              index={i + 1}
              draft={d}
              postUrl={post.url}
              maxLength={maxLength(d)}
            />
          ))}
        </ol>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
        <div className="w-44">
          <Select
            aria-label="Template"
            value={templateId}
            onChange={(e) => setTemplateId(e.target.value)}
          >
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </Select>
        </div>
        <Button
          variant={post.drafts.length ? "secondary" : "primary"}
          disabled={!templateId || regenerate.isPending}
          onClick={() => regenerate.mutate({ postId: post.id, templateId })}
        >
          {regenerate.isPending ? "Drafting…" : post.drafts.length ? "Redraft" : "Draft comments"}
        </Button>
        <a
          href={post.url}
          target="_blank"
          rel="noreferrer"
          className="ml-auto rounded-md px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
        >
          Open post ↗
        </a>
        <div className="w-full">
          <ErrorText error={regenerate.error} />
        </div>
      </div>
    </li>
  );
}

function DraftItem({
  index,
  draft,
  postUrl,
  maxLength,
}: {
  index: number;
  draft: Draft;
  postUrl: string;
  maxLength?: number;
}) {
  const text = draft.edited_text ?? draft.text;
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(text);
  const [copied, setCopied] = useState(false);
  const edit = useEditDraft();
  const approve = useApproveDraft();
  const reject = useRejectDraft();
  const markPublished = useMarkPublished();
  const busy = edit.isPending || approve.isPending || reject.isPending || markPublished.isPending;
  const error = edit.error ?? approve.error ?? reject.error ?? markPublished.error;
  const tooLong = maxLength !== undefined && value.trim().length > maxLength;

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function save() {
    edit.mutate({ id: draft.id, text: value }, { onSuccess: () => setEditing(false) });
  }

  function publish() {
    if (confirm("Did you post this comment on the platform? It will be recorded as published.")) {
      markPublished.mutate(draft.id);
    }
  }

  const tone = DRAFT_TONE[draft.status];
  return (
    <li
      className={`rounded-lg border p-3 text-sm ${
        draft.status === "approved"
          ? "border-emerald-200 bg-emerald-50/50"
          : "border-slate-200 bg-slate-50"
      }`}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-xs font-medium text-slate-400">{index}</span>
        <div className="min-w-0 flex-1">
          {editing ? (
            <textarea
              className="block w-full rounded-md border border-slate-300 bg-white p-2 text-sm focus:border-indigo-500 focus:outline-none"
              rows={4}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              autoFocus
            />
          ) : (
            <p className="whitespace-pre-wrap text-slate-800">{text}</p>
          )}
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <Badge tone={tone}>{draft.status}</Badge>
            {draft.edited_text && <span>edited</span>}
            <span className={tooLong ? "text-red-600" : undefined}>
              {(editing ? value.trim() : text).length}
              {maxLength ? `/${maxLength}` : ""} chars
            </span>
            {draft.status === "published" && <span>on {formatDate(draft.published_at)}</span>}
            {draft.status === "failed" && <span className="text-red-600">{draft.error}</span>}
            {draft.status === "approved" && (
              <span className="text-emerald-700">
                approved — copy it, post it, then mark it as published
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap justify-end gap-2">
        {editing ? (
          <>
            <Button
              onClick={() => {
                setValue(text);
                setEditing(false);
              }}
            >
              Cancel
            </Button>
            <Button variant="primary" onClick={save} disabled={busy || tooLong || !value.trim()}>
              {edit.isPending ? "Saving…" : "Save"}
            </Button>
          </>
        ) : (
          <>
            {(draft.status === "pending" || draft.status === "approved") && (
              <>
                <Button variant="ghost" onClick={() => setEditing(true)} disabled={busy}>
                  Edit
                </Button>
                <Button variant="danger" onClick={() => reject.mutate(draft.id)} disabled={busy}>
                  Reject
                </Button>
              </>
            )}
            {draft.status === "pending" && (
              <Button variant="primary" onClick={() => approve.mutate(draft.id)} disabled={busy}>
                Approve
              </Button>
            )}
            {(draft.status === "approved" || draft.status === "published") && (
              <Button onClick={copy}>{copied ? "Copied ✓" : "Copy comment"}</Button>
            )}
            {draft.status === "approved" && (
              <>
                <a
                  href={postUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  Open post ↗
                </a>
                <Button variant="primary" onClick={publish} disabled={busy}>
                  {markPublished.isPending ? "Saving…" : "Mark as published"}
                </Button>
              </>
            )}
          </>
        )}
      </div>
      <ErrorText error={error} />
    </li>
  );
}
