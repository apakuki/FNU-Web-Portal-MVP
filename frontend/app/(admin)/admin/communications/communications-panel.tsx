"use client";

import { useEffect, useState } from "react";

import { apiFetch, ApiError } from "@/lib/api-client";

type Template = {
  id: string;
  code: string;
  name: string;
  channel: "email" | "sms";
  subject_template: string | null;
  body_template: string;
  is_active: boolean;
  updated_at: string;
};

type BatchResponse = {
  template_code: string;
  channel: string;
  recipient_count: number;
  sent: number;
  failed: number;
  dry_run: boolean;
  content_hash: string;
};

type NotificationRow = {
  id: string;
  channel: string;
  subject: string | null;
  recipient_email: string | null;
  recipient_phone: string | null;
  status: string;
  template_code: string | null;
  queued_at: string;
  sent_at: string | null;
  error_message: string | null;
};

const ROLES = ["student", "staff", "lecturer", "finance", "manager", "vc", "admin"];

export function CommunicationsPanel() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [recent, setRecent] = useState<NotificationRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selected, setSelected] = useState<string>("");
  const [role, setRole] = useState("student");
  const [bannerPrefix, setBannerPrefix] = useState("");
  const [variablesText, setVariablesText] = useState("{}");
  const [preview, setPreview] = useState<BatchResponse | null>(null);
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<BatchResponse | null>(null);

  const refresh = async () => {
    try {
      const [t, n] = await Promise.all([
        apiFetch<Template[]>("/api/admin/notification-templates"),
        apiFetch<NotificationRow[]>("/api/admin/notifications?limit=20"),
      ]);
      setTemplates(t);
      setRecent(n);
      if (!selected && t.length > 0) setSelected(t[0].code);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runBatch(dryRun: boolean) {
    setError(null);
    setSendResult(null);
    setPreview(null);
    let variables: Record<string, unknown>;
    try {
      variables = variablesText.trim() ? JSON.parse(variablesText) : {};
    } catch {
      setError("Variables must be valid JSON");
      return;
    }

    setSending(true);
    try {
      const res = await apiFetch<BatchResponse>(
        "/api/admin/communications/batch",
        {
          method: "POST",
          body: JSON.stringify({
            template_code: selected,
            role,
            banner_id_prefix: bannerPrefix || null,
            variables,
            dry_run: dryRun,
          }),
        },
      );
      if (dryRun) setPreview(res);
      else setSendResult(res);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed");
    } finally {
      setSending(false);
    }
  }

  const activeTemplate = templates.find((t) => t.code === selected);

  if (loading) return <p className="text-sm text-dark/60">Loading…</p>;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-semibold text-dark">Send batch</h2>
        <div className="mt-3 space-y-3 text-sm">
          <label className="block">
            <span className="mb-1 block font-medium text-dark">Template</span>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="w-full rounded border px-3 py-2"
            >
              {templates.map((t) => (
                <option key={t.code} value={t.code}>
                  {t.name} ({t.channel})
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1 block font-medium text-dark">Audience role</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full rounded border px-3 py-2"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="mb-1 block font-medium text-dark">
              Banner ID prefix (optional)
            </span>
            <input
              type="text"
              value={bannerPrefix}
              onChange={(e) => setBannerPrefix(e.target.value)}
              placeholder="e.g. S00012"
              className="w-full rounded border px-3 py-2"
            />
          </label>

          <label className="block">
            <span className="mb-1 block font-medium text-dark">
              Template variables (JSON)
            </span>
            <textarea
              value={variablesText}
              onChange={(e) => setVariablesText(e.target.value)}
              rows={6}
              className="w-full rounded border px-3 py-2 font-mono text-xs"
            />
          </label>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={sending || !selected}
              onClick={() => runBatch(true)}
              className="min-h-[44px] rounded border border-fnu-blue px-4 py-2 font-medium text-fnu-blue disabled:opacity-60"
            >
              Preview
            </button>
            <button
              type="button"
              disabled={sending || !selected}
              onClick={() => runBatch(false)}
              className="min-h-[44px] rounded bg-fnu-blue px-4 py-2 font-medium text-white disabled:opacity-60"
            >
              {sending ? "Sending…" : "Send"}
            </button>
          </div>

          {preview && (
            <div className="mt-2 rounded bg-info/10 p-3 text-xs">
              Preview: {preview.recipient_count} recipients via{" "}
              <span className="font-mono">{preview.channel}</span>, content hash{" "}
              <span className="font-mono">{preview.content_hash.slice(0, 12)}…</span>
            </div>
          )}
          {sendResult && (
            <div className="mt-2 rounded bg-success/10 p-3 text-xs">
              Sent {sendResult.sent}/{sendResult.recipient_count}, failed{" "}
              {sendResult.failed}.
            </div>
          )}
          {error && (
            <div role="alert" className="rounded bg-danger/10 p-2 text-sm text-danger">
              {error}
            </div>
          )}
        </div>
      </section>

      <section className="rounded border bg-white p-4">
        <h2 className="text-lg font-semibold text-dark">Template preview</h2>
        {activeTemplate ? (
          <div className="mt-3 space-y-2 text-sm">
            <p>
              <span className="text-dark/60">Code:</span>{" "}
              <span className="font-mono">{activeTemplate.code}</span>
            </p>
            <p>
              <span className="text-dark/60">Channel:</span>{" "}
              {activeTemplate.channel}
            </p>
            {activeTemplate.subject_template && (
              <div>
                <p className="text-dark/60">Subject</p>
                <pre className="whitespace-pre-wrap rounded bg-surface/60 p-2 text-xs">
                  {activeTemplate.subject_template}
                </pre>
              </div>
            )}
            <div>
              <p className="text-dark/60">Body</p>
              <pre className="whitespace-pre-wrap rounded bg-surface/60 p-2 text-xs">
                {activeTemplate.body_template}
              </pre>
            </div>
          </div>
        ) : (
          <p className="text-sm text-dark/60">No template selected.</p>
        )}
      </section>

      <section className="rounded border bg-white p-4 lg:col-span-2">
        <h2 className="text-lg font-semibold text-dark">Recent notifications</h2>
        {recent.length === 0 ? (
          <p className="mt-2 text-sm text-dark/60">None yet.</p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead className="text-xs uppercase text-dark/60">
              <tr>
                <th className="py-2">When</th>
                <th>Channel</th>
                <th>Recipient</th>
                <th>Template</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((n) => (
                <tr key={n.id} className="border-t">
                  <td className="py-2 text-xs text-dark/70">
                    {new Date(n.queued_at).toLocaleString()}
                  </td>
                  <td>{n.channel}</td>
                  <td className="text-xs">
                    {n.recipient_email ?? n.recipient_phone ?? "—"}
                  </td>
                  <td className="font-mono text-xs">{n.template_code ?? "—"}</td>
                  <td>
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        n.status === "sent"
                          ? "bg-success/10 text-success"
                          : n.status === "failed"
                          ? "bg-danger/10 text-danger"
                          : "bg-dark/10 text-dark"
                      }`}
                    >
                      {n.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
