import { useState } from "react";

import { ACTIVITY_PAGE_SIZE, useActivity, type Activity as Entry } from "../api/review";
import { Badge, Button, ErrorText, Select } from "../components/ui";
import { formatDate } from "../lib/format";

const FILTERS = [
  { value: "", label: "All activity" },
  { value: "draft.", label: "Drafts" },
  { value: "post.", label: "Posts" },
  { value: "source.", label: "Sources" },
  { value: "template.", label: "Templates" },
  { value: "posting_account.", label: "Posting accounts" },
];

const TONE: Record<string, "green" | "red" | "amber" | "slate"> = {
  "draft.approved": "green",
  "draft.published": "green",
  "draft.rejected": "red",
  "draft.publish_failed": "red",
  "post.score_failed": "red",
  "post.draft_failed": "red",
  "source.poll_failed": "red",
  "draft.edited": "amber",
};

/** A short human-readable summary of the most useful payload fields. */
function summary(entry: Entry): string {
  const p = entry.payload;
  const parts: string[] = [];
  if (typeof p.text === "string") parts.push(`“${p.text}”`);
  if (typeof p.score === "number")
    parts.push(`score ${p.score.toFixed(2)}${p.skipped ? " (skipped)" : ""}`);
  if (typeof p.account === "string") parts.push(`as ${p.account}`);
  if (typeof p.error === "string") parts.push(p.error);
  if (Array.isArray(p.changed)) parts.push(`changed: ${p.changed.join(", ")}`);
  if (typeof p.name === "string") parts.push(p.name);
  if (typeof p.display_name === "string") parts.push(p.display_name);
  if (typeof p.new_posts === "number") parts.push(`${p.new_posts} new post(s)`);
  if (p.needs_reapproval) parts.push("needs approval again");
  return parts.join(" · ");
}

export default function Activity() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(0);
  const activity = useActivity(action, page * ACTIVITY_PAGE_SIZE);
  const total = activity.data?.total ?? 0;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Activity</h1>
          <p className="text-sm text-slate-500">
            Every change, who made it, and when. “system” means a background job.
          </p>
        </div>
        <div className="w-48">
          <Select
            value={action}
            onChange={(e) => {
              setAction(e.target.value);
              setPage(0);
            }}
          >
            {FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      <ErrorText error={activity.error} />

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500 uppercase">
            <tr>
              <th className="px-4 py-2 font-medium">When</th>
              <th className="px-4 py-2 font-medium">Who</th>
              <th className="px-4 py-2 font-medium">Action</th>
              <th className="px-4 py-2 font-medium">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {activity.data?.items.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-slate-500">
                  No activity yet.
                </td>
              </tr>
            )}
            {activity.data?.items.map((e) => (
              <tr key={e.id} className="align-top">
                <td className="px-4 py-2 whitespace-nowrap text-slate-500">
                  {formatDate(e.created_at)}
                </td>
                <td className="px-4 py-2 whitespace-nowrap">{e.actor_email ?? "system"}</td>
                <td className="px-4 py-2 whitespace-nowrap">
                  <Badge tone={TONE[e.action] ?? "slate"}>{e.action}</Badge>
                </td>
                <td className="max-w-xl px-4 py-2 text-slate-600">
                  <span className="line-clamp-2" title={JSON.stringify(e.payload, null, 2)}>
                    {summary(e) || "—"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > ACTIVITY_PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-slate-600">
          <span>
            {page * ACTIVITY_PAGE_SIZE + 1}–{Math.min((page + 1) * ACTIVITY_PAGE_SIZE, total)} of{" "}
            {total}
          </span>
          <div className="flex gap-2">
            <Button disabled={page === 0} onClick={() => setPage((n) => n - 1)}>
              Previous
            </Button>
            <Button
              disabled={(page + 1) * ACTIVITY_PAGE_SIZE >= total}
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
