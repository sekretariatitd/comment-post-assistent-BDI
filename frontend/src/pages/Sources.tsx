import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import { useIsAdmin } from "../api/auth";
import {
  PLATFORMS,
  STANCES,
  useDeleteSource,
  useSaveSource,
  useSources,
  type Source,
  type SourceInput,
  type SourceStance,
} from "../api/sources";
import { usePollNow } from "../api/posts";
import { useTemplates, type Template } from "../api/templates";
import { Badge, Button, ErrorText, Field, Modal, Select, TextInput } from "../components/ui";
import { timeAgo } from "../lib/format";

const UNSUPPORTED = new Set(["facebook", "tiktok"]);
const STANCE_TONE = { ally: "green", opponent: "red", neutral: "slate" } as const;

export default function Sources() {
  const sources = useSources();
  const templates = useTemplates();
  const isAdmin = useIsAdmin();
  const save = useSaveSource();
  const remove = useDeleteSource();
  const pollNow = usePollNow();
  const [editing, setEditing] = useState<Source | "new" | null>(null);

  const templateName = (id: string | null) =>
    templates.data?.find((t) => t.id === id)?.name ?? null;

  function onDelete(s: Source) {
    if (confirm(`Delete source "${s.display_name}"? Its fetched posts are deleted too.`)) {
      remove.mutate(s.id);
    }
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Sources</h1>
          <p className="text-sm text-slate-500">News accounts and feeds we watch for new posts.</p>
        </div>
        {isAdmin && (
          <Button variant="primary" onClick={() => setEditing("new")}>
            Add source
          </Button>
        )}
      </div>

      <ErrorText error={sources.error ?? remove.error ?? save.error ?? pollNow.error} />

      <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500 uppercase">
            <tr>
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Platform</th>
              <th className="px-4 py-2 font-medium">URL / handle</th>
              <th className="px-4 py-2 font-medium">Stance</th>
              <th className="px-4 py-2 font-medium">Template</th>
              <th className="px-4 py-2 font-medium">Fetching</th>
              <th className="px-4 py-2 font-medium">Active</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sources.isPending && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-slate-500">
                  Loading…
                </td>
              </tr>
            )}
            {sources.data?.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-slate-500">
                  No sources yet.{isAdmin && " Add an RSS feed to get started."}
                </td>
              </tr>
            )}
            {sources.data?.map((s) => (
              <tr key={s.id}>
                <td className="px-4 py-3 font-medium">
                  <Link
                    to={`/posts?source=${s.id}`}
                    className="hover:text-indigo-700 hover:underline"
                  >
                    {s.display_name}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  {PLATFORMS.find((p) => p.value === s.platform)?.label}
                </td>
                <td className="max-w-64 truncate px-4 py-3 text-slate-600" title={s.url_or_handle}>
                  {s.url_or_handle}
                </td>
                <td className="px-4 py-3">
                  <Badge tone={STANCE_TONE[s.stance]}>{s.stance}</Badge>
                </td>
                <td className="px-4 py-3">
                  {templateName(s.prompt_template_id) ?? <Badge tone="amber">none</Badge>}
                </td>
                <td className="px-4 py-3 text-slate-600">
                  {s.adapter === "rss" ? (
                    <>
                      every {s.poll_interval_minutes} min
                      <div className="text-xs text-slate-400">
                        checked {timeAgo(s.last_checked_at).toLowerCase()}
                      </div>
                    </>
                  ) : (
                    <Badge tone="amber">posts added by hand</Badge>
                  )}
                </td>
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    aria-label={`${s.display_name} active`}
                    checked={s.is_active}
                    disabled={!isAdmin || save.isPending}
                    onChange={(e) =>
                      save.mutate({ id: s.id, input: { is_active: e.target.checked } })
                    }
                  />
                </td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  {s.adapter === "rss" ? (
                    <Button
                      variant="ghost"
                      disabled={!s.is_active || (pollNow.isPending && pollNow.variables === s.id)}
                      onClick={() => pollNow.mutate(s.id)}
                    >
                      {pollNow.isSuccess && pollNow.variables === s.id ? "Queued ✓" : "Poll now"}
                    </Button>
                  ) : (
                    <Link
                      to={`/posts?source=${s.id}`}
                      className="rounded-md px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100"
                    >
                      Add posts
                    </Link>
                  )}
                  {isAdmin && (
                    <>
                      <Button variant="ghost" onClick={() => setEditing(s)}>
                        Edit
                      </Button>
                      <Button variant="ghost" className="text-red-600" onClick={() => onDelete(s)}>
                        Delete
                      </Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <SourceDialog
          source={editing === "new" ? null : editing}
          templates={templates.data ?? []}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function SourceDialog({
  source,
  templates,
  onClose,
}: {
  source: Source | null;
  templates: Template[];
  onClose: () => void;
}) {
  const save = useSaveSource();
  const [form, setForm] = useState<SourceInput>(
    source
      ? {
          platform: source.platform,
          display_name: source.display_name,
          url_or_handle: source.url_or_handle,
          prompt_template_id: source.prompt_template_id,
          stance: source.stance,
          poll_interval_minutes: source.poll_interval_minutes,
          is_active: source.is_active,
        }
      : {
          platform: "rss",
          display_name: "",
          url_or_handle: "",
          prompt_template_id: templates.find((t) => t.is_active)?.id ?? null,
          stance: "neutral",
          poll_interval_minutes: 15,
          is_active: true,
        },
  );
  const set = <K extends keyof SourceInput>(key: K, value: SourceInput[K]) =>
    setForm((f) => ({ ...f, [key]: value }));
  const platform = PLATFORMS.find((p) => p.value === form.platform)!;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    save.mutate({ id: source?.id, input: form }, { onSuccess: onClose });
  }

  return (
    <Modal title={source ? "Edit source" : "Add source"} onClose={onClose}>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Platform">
          <Select
            value={form.platform}
            onChange={(e) => set("platform", e.target.value as SourceInput["platform"])}
          >
            {PLATFORMS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </Select>
        </Field>
        {UNSUPPORTED.has(form.platform) && (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Automatic fetching isn't available for {platform.label} yet. Save the source, then add
            its posts by hand on the Posts page (paste the link and text).
          </p>
        )}
        <Field label="Display name">
          <TextInput
            required
            value={form.display_name}
            onChange={(e) => set("display_name", e.target.value)}
          />
        </Field>
        <Field label={form.platform === "rss" ? "Feed URL" : "URL or handle"} hint={platform.hint}>
          <TextInput
            required
            type={form.platform === "rss" ? "url" : "text"}
            value={form.url_or_handle}
            onChange={(e) => set("url_or_handle", e.target.value)}
          />
        </Field>
        <Field
          label="This account is our…"
          hint="Tells the AI whether to back or criticise the author, whichever template you draft with."
        >
          <Select
            value={form.stance}
            onChange={(e) => set("stance", e.target.value as SourceStance)}
          >
            {STANCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Template" hint="Used to score posts and draft comments.">
          <Select
            value={form.prompt_template_id ?? ""}
            onChange={(e) => set("prompt_template_id", e.target.value || null)}
          >
            <option value="">No template</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
                {!t.is_active && " (inactive)"}
              </option>
            ))}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Check every" hint="minutes">
            <TextInput
              required
              type="number"
              min={1}
              max={1440}
              value={form.poll_interval_minutes}
              onChange={(e) => set("poll_interval_minutes", Number(e.target.value))}
            />
          </Field>
          <label className="mt-6 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => set("is_active", e.target.checked)}
            />
            Active
          </label>
        </div>
        <ErrorText error={save.error} />
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={save.isPending}>
            {save.isPending ? "Saving…" : source ? "Save" : "Add source"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
