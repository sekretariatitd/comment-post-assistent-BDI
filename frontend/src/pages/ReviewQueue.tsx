import { useState } from "react";
import { Link } from "react-router";

import { PAGE_SIZE, usePosts, type DraftStatus } from "../api/posts";
import { useSources } from "../api/sources";
import { useTemplates } from "../api/templates";
import { PostCard } from "../components/PostCard";
import { Button, ErrorText } from "../components/ui";

const TABS: { value: DraftStatus; label: string; empty: string }[] = [
  {
    value: "pending",
    label: "Needs review",
    empty: "Nothing to review. New drafts appear here as soon as they're written.",
  },
  {
    value: "approved",
    label: "Approved",
    empty: "No approved comments waiting to be posted.",
  },
  { value: "published", label: "Published", empty: "Nothing published yet." },
];

export default function ReviewQueue() {
  const [tab, setTab] = useState<DraftStatus>("pending");
  const [page, setPage] = useState(0);
  const sources = useSources();
  const templates = useTemplates();
  const posts = usePosts({ review: tab, offset: page * PAGE_SIZE });
  const sourceById = new Map((sources.data ?? []).map((s) => [s.id, s]));
  const total = posts.data?.total ?? 0;
  const current = TABS.find((t) => t.value === tab)!;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Review queue</h1>
          <p className="text-sm text-slate-500">
            Edit, approve or reject drafts. Approved comments are posted by hand from our account,
            then marked as published. Updates live.
          </p>
        </div>
        <div className="flex rounded-lg border border-slate-200 bg-white p-0.5 text-sm">
          {TABS.map((t) => (
            <button
              key={t.value}
              onClick={() => {
                setTab(t.value);
                setPage(0);
              }}
              className={`rounded-md px-3 py-1.5 ${
                tab === t.value ? "bg-indigo-600 text-white" : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              {t.label}
              {tab === t.value && posts.data ? ` (${total})` : ""}
            </button>
          ))}
        </div>
      </div>

      <ErrorText error={posts.error} />

      <ul className="space-y-3">
        {posts.isPending && <li className="text-sm text-slate-500">Loading…</li>}
        {posts.data?.items.length === 0 && (
          <li className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
            {current.empty}{" "}
            {tab === "pending" && (
              <Link to="/posts" className="text-indigo-600 hover:underline">
                Go to Posts
              </Link>
            )}
          </li>
        )}
        {posts.data?.items.map((p) => (
          <PostCard
            key={p.id}
            post={p}
            source={sourceById.get(p.source_id)}
            templates={templates.data ?? []}
          />
        ))}
      </ul>

      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
          </span>
          <div className="flex gap-2">
            <Button disabled={page === 0} onClick={() => setPage((n) => n - 1)}>
              Previous
            </Button>
            <Button
              disabled={(page + 1) * PAGE_SIZE >= total}
              onClick={() => setPage((n) => n + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
