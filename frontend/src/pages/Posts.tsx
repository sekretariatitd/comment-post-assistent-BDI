import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";

import { PAGE_SIZE, useAddPost, useImportPosts, usePosts, type PostStatus } from "../api/posts";
import { useSources, type Source } from "../api/sources";
import { useTemplates } from "../api/templates";
import { PostCard } from "../components/PostCard";
import { Button, ErrorText, Field, Modal, Select, TextArea, TextInput } from "../components/ui";

export default function Posts() {
  const [params, setParams] = useSearchParams();
  const sourceId = params.get("source") ?? "";
  const status = (params.get("status") ?? "") as PostStatus | "";
  const [page, setPage] = useState(0);
  const [adding, setAdding] = useState(false);
  const [importing, setImporting] = useState(false);

  const sources = useSources();
  const templates = useTemplates();
  const posts = usePosts({
    source_id: sourceId || undefined,
    status: status || undefined,
    offset: page * PAGE_SIZE,
  });
  const sourceById = new Map((sources.data ?? []).map((s) => [s.id, s]));

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
    setPage(0);
  }

  const total = posts.data?.total ?? 0;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Posts</h1>
          <p className="text-sm text-slate-500">
            Everything fetched from your sources or added by hand. Updates live.
          </p>
        </div>
        <div className="flex items-end gap-2">
          <div className="w-52">
            <Select value={sourceId} onChange={(e) => setFilter("source", e.target.value)}>
              <option value="">All sources</option>
              {sources.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name}
                </option>
              ))}
            </Select>
          </div>
          <div className="w-36">
            <Select value={status} onChange={(e) => setFilter("status", e.target.value)}>
              <option value="">Any status</option>
              <option value="new">New</option>
              <option value="drafted">Drafted</option>
              <option value="skipped">Skipped</option>
            </Select>
          </div>
          <Button onClick={() => setImporting(true)} disabled={!sources.data?.length}>
            Import
          </Button>
          <Button
            variant="primary"
            onClick={() => setAdding(true)}
            disabled={!sources.data?.length}
          >
            Add post
          </Button>
        </div>
      </div>

      <ErrorText error={posts.error} />

      <ul className="space-y-3">
        {posts.isPending && <li className="text-sm text-slate-500">Loading…</li>}
        {posts.data?.items.length === 0 && (
          <li className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
            No posts yet. Use “Import” to bring in a Facebook page's or TikTok profile's latest
            posts at once, or “Add post” for a single post.
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

      {adding && sources.data && (
        <AddPostDialog
          sources={sources.data}
          defaultSourceId={sourceId}
          onClose={() => setAdding(false)}
        />
      )}
      {importing && sources.data && (
        <ImportDialog
          sources={sources.data}
          defaultSourceId={sourceId}
          onClose={() => setImporting(false)}
        />
      )}
    </div>
  );
}

function AddPostDialog({
  sources,
  defaultSourceId,
  onClose,
}: {
  sources: Source[];
  defaultSourceId: string;
  onClose: () => void;
}) {
  const add = useAddPost();
  const preferred =
    sources.find((s) => s.id === defaultSourceId) ?? sources.find((s) => s.adapter !== "rss");
  const [sourceId, setSourceId] = useState(preferred?.id ?? sources[0].id);
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    add.mutate({ source_id: sourceId, url, text }, { onSuccess: onClose });
  }

  return (
    <Modal title="Add post" onClose={onClose}>
      <form onSubmit={onSubmit} className="space-y-4">
        <p className="text-sm text-slate-500">
          For posts the app can't fetch itself (Facebook, TikTok): paste the post's link and its
          text.
        </p>
        <Field label="Source">
          <Select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.display_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Post URL">
          <TextInput
            required
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://www.facebook.com/…/posts/…"
          />
        </Field>
        <Field label="Post text" hint="Copy the post's text (and any key details from images).">
          <TextArea required rows={7} value={text} onChange={(e) => setText(e.target.value)} />
        </Field>
        <ErrorText error={add.error} />
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={add.isPending}>
            {add.isPending ? "Adding…" : "Add post"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function ImportDialog({
  sources,
  defaultSourceId,
  onClose,
}: {
  sources: Source[];
  defaultSourceId: string;
  onClose: () => void;
}) {
  const importPosts = useImportPosts();
  const preferred =
    sources.find((s) => s.id === defaultSourceId) ??
    sources.find((s) => s.platform === "facebook" || s.platform === "tiktok");
  const [sourceId, setSourceId] = useState(preferred?.id ?? sources[0].id);
  const [payload, setPayload] = useState("");
  const result = importPosts.data;
  const isTikTok = sources.find((s) => s.id === sourceId)?.platform === "tiktok";

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    importPosts.mutate({ sourceId, payload });
  }

  return (
    <Modal title="Import posts" onClose={onClose}>
      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Source">
          <Select value={sourceId} onChange={(e) => setSourceId(e.target.value)}>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.display_name}
              </option>
            ))}
          </Select>
        </Field>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600">
          {isTikTok ? (
            <>
              <li>Open the TikTok profile page (tiktok.com/@…) in your browser.</li>
              <li>Press F12 → Network → filter “item_list”, then reload the page.</li>
              <li>Click the item_list request, copy its whole Response tab, and paste it below.</li>
            </>
          ) : (
            <>
              <li>
                Open the Facebook page in your browser. Press F12 → Network → filter “graphql”.
              </li>
              <li>Scroll the page, click the request whose Response contains “creation_time”.</li>
              <li>Copy its whole Response tab and paste it below. (The page’s HTML also works.)</li>
            </>
          )}
        </ol>
        <Field label="Response">
          <TextArea
            required
            rows={8}
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            placeholder={isTikTok ? '{"cursor":"…","itemList":[…' : '{"data":{"node":{…'}
          />
        </Field>
        <ErrorText error={importPosts.error} />
        {result && (
          <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
            Found {result.found} post{result.found === 1 ? "" : "s"}, {result.new} new.
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button type="button" onClick={onClose}>
            {result ? "Done" : "Cancel"}
          </Button>
          <Button type="submit" variant="primary" disabled={importPosts.isPending || !payload}>
            {importPosts.isPending ? "Importing…" : "Import"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
