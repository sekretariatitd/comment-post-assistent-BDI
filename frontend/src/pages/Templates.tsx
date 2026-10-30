import { useState, type FormEvent } from "react";

import { useIsAdmin } from "../api/auth";
import {
  useDeleteTemplate,
  usePreviewTemplate,
  useSaveTemplate,
  useTemplateDefaults,
  useTemplates,
  type Template,
  type TemplateFields,
  type TemplateInput,
} from "../api/templates";
import { Badge, Button, ErrorText, Field, TextArea, TextInput } from "../components/ui";

const NEW = "new";

export default function Templates() {
  const templates = useTemplates();
  const defaults = useTemplateDefaults();
  const isAdmin = useIsAdmin();
  const [selected, setSelected] = useState<string | null>(null);

  if (templates.isPending || defaults.isPending)
    return <p className="text-sm text-slate-500">Loading…</p>;
  if (templates.isError) return <ErrorText error={templates.error} />;

  const list = templates.data;
  const activeId = selected ?? list[0]?.id ?? (isAdmin ? NEW : null);
  const active = list.find((t) => t.id === activeId) ?? null;

  return (
    <div className="flex gap-6">
      <aside className="w-60 shrink-0">
        <div className="mb-3 flex items-center justify-between">
          <h1 className="text-xl font-semibold">Templates</h1>
          {isAdmin && (
            <Button variant="ghost" onClick={() => setSelected(NEW)}>
              + New
            </Button>
          )}
        </div>
        <ul className="space-y-1">
          {list.map((t) => (
            <li key={t.id}>
              <button
                onClick={() => setSelected(t.id)}
                className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                  t.id === activeId ? "bg-indigo-50 text-indigo-700" : "hover:bg-slate-100"
                }`}
              >
                <div className="truncate font-medium">{t.name}</div>
                <div className="mt-0.5 flex gap-1.5 text-xs text-slate-500">
                  v{t.version} · {t.language} · {t.tone}
                  {!t.is_active && <Badge>inactive</Badge>}
                </div>
              </button>
            </li>
          ))}
          {activeId === NEW && (
            <li className="rounded-md bg-indigo-50 px-3 py-2 text-sm text-indigo-700">
              New template
            </li>
          )}
        </ul>
        {list.length === 0 && !isAdmin && (
          <p className="text-sm text-slate-500">No templates yet. An admin can create one.</p>
        )}
      </aside>

      {activeId && (
        <section className="min-w-0 flex-1">
          <TemplateEditor
            key={activeId}
            template={active}
            defaultRules={defaults.data?.relevance_rules ?? ""}
            readOnly={!isAdmin}
            onSaved={(id) => setSelected(id)}
            onDeleted={() => setSelected(null)}
          />
        </section>
      )}
    </div>
  );
}

function toInput(t: Template | null, defaultRules: string): TemplateInput {
  if (!t) {
    return {
      name: "",
      system_prompt: "",
      tone: "friendly",
      language: "English",
      max_length: 280,
      relevance_rules: defaultRules,
      plain_e: false,
      no_dashes: false,
      is_active: true,
    };
  }
  const { name, system_prompt, tone, language, max_length, relevance_rules } = t;
  const { plain_e, no_dashes, is_active } = t;
  return {
    name,
    system_prompt,
    tone,
    language,
    max_length,
    relevance_rules,
    plain_e,
    no_dashes,
    is_active,
  };
}

function TemplateEditor({
  template,
  defaultRules,
  readOnly,
  onSaved,
  onDeleted,
}: {
  template: Template | null;
  defaultRules: string;
  readOnly: boolean;
  onSaved: (id: string) => void;
  onDeleted: () => void;
}) {
  const initial = toInput(template, defaultRules);
  const [form, setForm] = useState<TemplateInput>(initial);
  const save = useSaveTemplate();
  const remove = useDeleteTemplate();
  const dirty = JSON.stringify(form) !== JSON.stringify(initial);

  const set = <K extends keyof TemplateInput>(key: K, value: TemplateInput[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  function onSave(e: FormEvent) {
    e.preventDefault();
    save.mutate({ id: template?.id, input: form }, { onSuccess: (t) => onSaved(t.id) });
  }

  function onDelete() {
    if (!template || !confirm(`Delete template "${template.name}"?`)) return;
    remove.mutate(template.id, { onSuccess: onDeleted });
  }

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <form onSubmit={onSave} className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">
            {template ? `Edit template` : "New template"}
            {template && (
              <span className="ml-2 text-sm font-normal text-slate-500">v{template.version}</span>
            )}
          </h2>
          {readOnly && <Badge>read-only</Badge>}
        </div>

        <fieldset disabled={readOnly} className="space-y-4">
          <Field label="Name">
            <TextInput required value={form.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field
            label="System prompt"
            hint="Who we are and how our account comments. Safety rules are added automatically."
          >
            <TextArea
              required
              rows={7}
              value={form.system_prompt}
              onChange={(e) => set("system_prompt", e.target.value)}
              placeholder="You write comments for the official account of …"
            />
          </Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="Tone">
              <TextInput required value={form.tone} onChange={(e) => set("tone", e.target.value)} />
            </Field>
            <Field label="Language">
              <TextInput
                required
                value={form.language}
                onChange={(e) => set("language", e.target.value)}
              />
            </Field>
            <Field label="Max length" hint="characters">
              <TextInput
                required
                type="number"
                min={20}
                max={5000}
                value={form.max_length}
                onChange={(e) => set("max_length", Number(e.target.value))}
              />
            </Field>
          </div>
          <Field
            label="Relevance rules"
            hint="What to engage with and what to skip. Posts about deaths, tragedies and violence are skipped unless these rules explicitly allow them."
          >
            <TextArea
              required
              rows={6}
              value={form.relevance_rules}
              onChange={(e) => set("relevance_rules", e.target.value)}
            />
          </Field>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.plain_e}
                onChange={(e) => set("plain_e", e.target.checked)}
              />
              Write “e”/“c” instead of “ë”/“ç”
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.no_dashes}
                onChange={(e) => set("no_dashes", e.target.checked)}
              />
              No dashes (— – -)
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => set("is_active", e.target.checked)}
              />
              Active
            </label>
          </div>
        </fieldset>

        <ErrorText error={save.error ?? remove.error} />
        {!readOnly && (
          <div className="flex items-center gap-2">
            <Button type="submit" variant="primary" disabled={!dirty || save.isPending}>
              {save.isPending ? "Saving…" : template ? "Save changes" : "Create template"}
            </Button>
            {dirty && template && (
              <Button type="button" variant="ghost" onClick={() => setForm(initial)}>
                Discard
              </Button>
            )}
            {template && (
              <Button
                type="button"
                variant="danger"
                className="ml-auto"
                onClick={onDelete}
                disabled={remove.isPending}
              >
                Delete
              </Button>
            )}
          </div>
        )}
      </form>

      <PreviewPanel template={template} fields={form} dirty={dirty} />
    </div>
  );
}

function PreviewPanel({
  template,
  fields,
  dirty,
}: {
  template: Template | null;
  fields: TemplateFields;
  dirty: boolean;
}) {
  const [sample, setSample] = useState("");
  const preview = usePreviewTemplate();
  const result = preview.data;

  function run() {
    if (!template) return;
    const { system_prompt, tone, language, max_length, relevance_rules, plain_e, no_dashes } =
      fields;
    preview.mutate({
      id: template.id,
      sampleText: sample,
      overrides: {
        system_prompt,
        tone,
        language,
        max_length,
        relevance_rules,
        plain_e,
        no_dashes,
      },
    });
  }

  return (
    <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-5">
      <div>
        <h2 className="font-semibold">Preview</h2>
        <p className="text-sm text-slate-500">
          Test this template on pasted text. Nothing is saved. To draft comments for a real post,
          use “Draft comments” on the Posts page.
        </p>
      </div>
      <TextArea
        rows={6}
        value={sample}
        onChange={(e) => setSample(e.target.value)}
        placeholder="Paste the text of a news post…"
      />
      <div className="flex items-center gap-3">
        <Button
          variant="primary"
          onClick={run}
          disabled={!template || !sample.trim() || preview.isPending}
        >
          {preview.isPending ? "Generating…" : "Run preview"}
        </Button>
        {!template && <span className="text-xs text-slate-500">Create the template first.</span>}
        {template && dirty && (
          <span className="text-xs text-amber-700">Uses your unsaved edits.</span>
        )}
      </div>
      <ErrorText error={preview.error} />

      {result && (
        <div className="space-y-4 border-t border-slate-100 pt-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-sm">
              <Badge tone={result.relevance.would_draft ? "green" : "amber"}>
                {result.relevance.would_draft ? "Would draft" : "Would skip"}
              </Badge>
              <span className="text-slate-600">
                score {result.relevance.score.toFixed(2)} (threshold {result.threshold})
              </span>
            </div>
            <p className="text-sm text-slate-700">{result.relevance.reason}</p>
          </div>
          <ol className="space-y-2">
            {result.drafts.map((d, i) => (
              <li key={i} className="rounded-lg border border-slate-200 p-3 text-sm">
                <p className="whitespace-pre-wrap text-slate-800">{d}</p>
                <p className="mt-1 text-right text-xs text-slate-400">
                  {d.length}/{fields.max_length} chars
                </p>
              </li>
            ))}
          </ol>
          <p className="text-xs text-slate-400">
            {result.model_name} · template v{result.template_version}
            {dirty && " + unsaved edits"}
          </p>
        </div>
      )}
    </div>
  );
}
