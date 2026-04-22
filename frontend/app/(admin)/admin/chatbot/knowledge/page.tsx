"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface KnowledgeEntry {
  id: string;
  kind: string;
  title: string;
  content: string;
  tags: string[];
  is_active: boolean;
  updated_at: string;
}

interface DraftEntry {
  id: string | null;
  title: string;
  content: string;
  kind: string;
  tags: string;
  is_active: boolean;
}

const EMPTY_DRAFT: DraftEntry = {
  id: null,
  title: "",
  content: "",
  kind: "faq",
  tags: "",
  is_active: true,
};

export default function ChatbotKnowledgePage() {
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState<DraftEntry>(EMPTY_DRAFT);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const qs = includeInactive ? "?include_inactive=true" : "";
      const data = await apiFetch<KnowledgeEntry[]>(
        `/api/admin/chatbot/knowledge${qs}`,
      );
      setEntries(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load FAQ");
    } finally {
      setLoading(false);
    }
  }, [includeInactive]);

  useEffect(() => {
    load();
  }, [load]);

  function editEntry(entry: KnowledgeEntry) {
    setDraft({
      id: entry.id,
      title: entry.title,
      content: entry.content,
      kind: entry.kind,
      tags: entry.tags.join(", "),
      is_active: entry.is_active,
    });
    setMessage("");
    setError("");
  }

  async function saveDraft(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const payload = {
        title: draft.title.trim(),
        content: draft.content.trim(),
        kind: draft.kind.trim() || "faq",
        tags: draft.tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        is_active: draft.is_active,
      };
      if (draft.id) {
        await apiFetch(`/api/admin/chatbot/knowledge/${draft.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        setMessage("Entry updated");
      } else {
        await apiFetch("/api/admin/chatbot/knowledge", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setMessage("Entry created");
      }
      setDraft(EMPTY_DRAFT);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(id: string) {
    if (!confirm("Deactivate this FAQ entry?")) return;
    setError("");
    try {
      await apiFetch(`/api/admin/chatbot/knowledge/${id}`, {
        method: "DELETE",
      });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-dark">Chatbot FAQ</h1>
        <p className="text-sm text-gray">
          Manage the knowledge base the chatbot draws answers from.
        </p>
      </div>

      <section className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold text-dark">
          {draft.id ? "Edit Entry" : "Add Entry"}
        </h2>
        <form onSubmit={saveDraft} className="space-y-3">
          <label className="block text-sm">
            <span className="text-gray">Title</span>
            <input
              type="text"
              value={draft.title}
              onChange={(e) =>
                setDraft((d) => ({ ...d, title: e.target.value }))
              }
              required
              minLength={1}
              maxLength={200}
              className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-gray">Content</span>
            <textarea
              value={draft.content}
              onChange={(e) =>
                setDraft((d) => ({ ...d, content: e.target.value }))
              }
              required
              minLength={1}
              maxLength={20000}
              rows={5}
              className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm">
              <span className="text-gray">Kind</span>
              <input
                type="text"
                value={draft.kind}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, kind: e.target.value }))
                }
                maxLength={40}
                className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
              />
            </label>
            <label className="sm:col-span-2 text-sm">
              <span className="text-gray">Tags (comma separated)</span>
              <input
                type="text"
                value={draft.tags}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, tags: e.target.value }))
                }
                className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
              />
            </label>
          </div>
          <label className="flex items-center gap-2 text-sm text-dark">
            <input
              type="checkbox"
              checked={draft.is_active}
              onChange={(e) =>
                setDraft((d) => ({ ...d, is_active: e.target.checked }))
              }
            />
            Active (available to the chatbot)
          </label>
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving}
              className="rounded bg-fnu-blue px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {saving ? "Saving…" : draft.id ? "Update" : "Create"}
            </button>
            {draft.id && (
              <button
                type="button"
                onClick={() => setDraft(EMPTY_DRAFT)}
                className="rounded border px-4 py-2 text-sm text-dark"
              >
                Cancel
              </button>
            )}
            {message && (
              <span className="self-center text-sm text-success">{message}</span>
            )}
            {error && (
              <span className="self-center text-sm text-danger">{error}</span>
            )}
          </div>
        </form>
      </section>

      <section className="rounded-lg border bg-white shadow-sm">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-semibold text-dark">
            Entries ({entries.length})
          </h2>
          <label className="flex items-center gap-2 text-sm text-gray">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
            />
            Show inactive
          </label>
        </div>
        {loading ? (
          <p className="px-4 py-6 text-gray">Loading…</p>
        ) : entries.length === 0 ? (
          <p className="px-4 py-6 text-gray">No entries yet.</p>
        ) : (
          <ul className="divide-y">
            {entries.map((entry) => (
              <li key={entry.id} className="px-4 py-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 font-medium text-dark">
                      {entry.title}
                      {!entry.is_active && (
                        <span className="rounded bg-gray/10 px-1.5 text-xs text-gray">
                          inactive
                        </span>
                      )}
                    </p>
                    <p className="mt-1 line-clamp-2 text-sm text-gray">
                      {entry.content}
                    </p>
                    {entry.tags.length > 0 && (
                      <p className="mt-1 text-xs text-gray">
                        Tags: {entry.tags.join(", ")}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <button
                      onClick={() => editEntry(entry)}
                      className="rounded border px-3 py-1 text-sm text-dark hover:bg-dark/5"
                    >
                      Edit
                    </button>
                    {entry.is_active && (
                      <button
                        onClick={() => deactivate(entry.id)}
                        className="rounded border border-danger/30 px-3 py-1 text-sm text-danger hover:bg-danger/5"
                      >
                        Deactivate
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
