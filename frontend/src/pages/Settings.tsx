import { useState } from "react";

import { useIsAdmin } from "../api/auth";
import {
  useAppSettings,
  usePostingAccounts,
  useSavePostingAccount,
  type PostingAccount,
} from "../api/review";
import { PLATFORMS, type Platform } from "../api/sources";
import { Badge, Button, ErrorText, TextInput } from "../components/ui";

export default function Settings() {
  const accounts = usePostingAccounts();
  const settings = useAppSettings();
  const isAdmin = useIsAdmin();
  const byPlatform = new Map((accounts.data ?? []).map((a) => [a.platform, a]));

  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-slate-500">
          Our posting accounts and the limits the server enforces.
        </p>
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">Posting accounts</h2>
        <p className="mb-4 text-sm text-slate-500">
          One official account per platform. Comments can only be marked as published on a platform
          that has an active account here. In manual mode only the name is needed.
        </p>
        <ErrorText error={accounts.error} />
        <div className="divide-y divide-slate-100">
          {accounts.isPending && <p className="py-3 text-sm text-slate-500">Loading…</p>}
          {accounts.data &&
            PLATFORMS.map((p) => (
              <AccountRow
                key={`${p.value}-${byPlatform.get(p.value)?.updated_at ?? "new"}`}
                platform={p.value}
                label={p.label}
                account={byPlatform.get(p.value)}
                readOnly={!isAdmin}
              />
            ))}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="font-semibold">Limits and AI</h2>
        <p className="mb-4 text-sm text-slate-500">
          Set in the server's <code>.env</code> file. Restart the backend and worker after changing
          them.
        </p>
        <ErrorText error={settings.error} />
        {settings.data && (
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <dt className="text-slate-500">Relevance threshold</dt>
            <dd>
              {settings.data.relevance_threshold}{" "}
              <span className="text-slate-400">(RELEVANCE_THRESHOLD)</span>
            </dd>
            <dt className="text-slate-500">Max comments per hour, per platform</dt>
            <dd>
              {settings.data.max_comments_per_hour}{" "}
              <span className="text-slate-400">(MAX_COMMENTS_PER_HOUR)</span>
            </dd>
            <dt className="text-slate-500">Publishing</dt>
            <dd>
              {settings.data.enable_automated_publishing ? (
                <Badge tone="amber">automated (not implemented)</Badge>
              ) : (
                <Badge tone="green">manual</Badge>
              )}
            </dd>
            <dt className="text-slate-500">AI model</dt>
            <dd>
              {settings.data.anthropic_model}{" "}
              {settings.data.anthropic_configured ? (
                <Badge tone="green">API key set</Badge>
              ) : (
                <Badge tone="red">no API key</Badge>
              )}
            </dd>
          </dl>
        )}
      </section>
    </div>
  );
}

function AccountRow({
  platform,
  label,
  account,
  readOnly,
}: {
  platform: Platform;
  label: string;
  account?: PostingAccount;
  readOnly: boolean;
}) {
  const save = useSavePostingAccount();
  const [name, setName] = useState(account?.display_name ?? "");
  const [active, setActive] = useState(account?.is_active ?? true);
  const dirty =
    name.trim() !== (account?.display_name ?? "") || active !== (account?.is_active ?? true);

  return (
    <div className="flex flex-wrap items-center gap-3 py-3">
      <div className="w-36 text-sm font-medium">
        {label}
        <div className="mt-0.5">
          {account ? (
            account.is_active ? (
              <Badge tone="green">active</Badge>
            ) : (
              <Badge>inactive</Badge>
            )
          ) : (
            <Badge tone="amber">not set up</Badge>
          )}
        </div>
      </div>
      <div className="min-w-48 flex-1">
        <TextInput
          aria-label={`${label} account name`}
          placeholder="Account name, e.g. @our_account"
          value={name}
          disabled={readOnly}
          onChange={(e) => setName(e.target.value)}
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={active}
          disabled={readOnly}
          onChange={(e) => setActive(e.target.checked)}
        />
        Active
      </label>
      {!readOnly && (
        <Button
          variant="primary"
          disabled={!name.trim() || !dirty || save.isPending}
          onClick={() => save.mutate({ platform, display_name: name.trim(), is_active: active })}
        >
          {save.isPending ? "Saving…" : "Save"}
        </Button>
      )}
      <div className="w-full">
        <ErrorText error={save.error} />
      </div>
    </div>
  );
}
