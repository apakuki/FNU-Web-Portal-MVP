"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface ConversationRow {
  id: string;
  session_key: string;
  user_id: string | null;
  escalated: boolean;
  resolved: boolean;
  category: string | null;
  message_count: number;
  last_message_preview: string;
  created_at: string;
  updated_at: string;
}

interface ConversationsList {
  total: number;
  conversations: ConversationRow[];
}

interface ConversationMessage {
  role: string;
  content: string;
  timestamp: string | null;
}

interface ConversationDetail {
  id: string;
  session_key: string;
  user_id: string | null;
  escalated: boolean;
  resolved: boolean;
  category: string | null;
  messages: ConversationMessage[];
  created_at: string;
  updated_at: string;
}

const PAGE_SIZE = 25;

export default function ChatbotConversationsPage() {
  const [data, setData] = useState<ConversationsList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [escalatedOnly, setEscalatedOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [selectLoading, setSelectLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        offset: String(offset),
      });
      if (q.trim()) params.set("q", q.trim());
      if (escalatedOnly) params.set("escalated", "true");
      const res = await apiFetch<ConversationsList>(
        `/api/admin/chatbot/conversations?${params}`,
      );
      setData(res);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load conversations",
      );
    } finally {
      setLoading(false);
    }
  }, [escalatedOnly, offset, q]);

  useEffect(() => {
    load();
  }, [load]);

  async function openConversation(id: string) {
    setSelectLoading(true);
    setError("");
    try {
      const res = await apiFetch<ConversationDetail>(
        `/api/admin/chatbot/conversations/${id}`,
      );
      setSelected(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    } finally {
      setSelectLoading(false);
    }
  }

  const totalPages =
    data && data.total > 0 ? Math.ceil(data.total / PAGE_SIZE) : 1;
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-dark">Chatbot Conversations</h1>
        <p className="text-sm text-gray">
          Review chatbot sessions. PII is masked in previews and message views.
        </p>
      </div>

      <section className="rounded-lg border bg-white p-4 shadow-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setOffset(0);
            load();
          }}
          className="flex flex-wrap items-end gap-3"
        >
          <label className="text-sm">
            <span className="text-gray">Search (session or category)</span>
            <input
              type="text"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="mt-1 block w-64 rounded border px-2 py-1.5 text-sm"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-dark">
            <input
              type="checkbox"
              checked={escalatedOnly}
              onChange={(e) => {
                setEscalatedOnly(e.target.checked);
                setOffset(0);
              }}
            />
            Escalated only
          </label>
          <button
            type="submit"
            className="rounded bg-fnu-blue px-3 py-1.5 text-sm font-medium text-white"
          >
            Apply
          </button>
        </form>
      </section>

      {error && (
        <div className="rounded border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      <section className="rounded-lg border bg-white shadow-sm">
        <div className="border-b px-4 py-3 text-sm text-gray">
          {data ? `${data.total} conversations` : "Loading…"}
        </div>
        {loading ? (
          <p className="px-4 py-6 text-gray">Loading…</p>
        ) : !data || data.conversations.length === 0 ? (
          <p className="px-4 py-6 text-gray">No conversations yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-gray">
                <tr>
                  <th className="px-4 py-2 font-medium">Updated</th>
                  <th className="px-4 py-2 font-medium">Session</th>
                  <th className="px-4 py-2 font-medium">User</th>
                  <th className="px-4 py-2 font-medium">Category</th>
                  <th className="px-4 py-2 font-medium">Msgs</th>
                  <th className="px-4 py-2 font-medium">Preview</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.conversations.map((c) => (
                  <tr
                    key={c.id}
                    className="cursor-pointer border-t hover:bg-gray/5"
                    onClick={() => openConversation(c.id)}
                  >
                    <td className="px-4 py-2 text-dark">
                      {new Date(c.updated_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-dark">
                      {c.session_key.slice(0, 12)}…
                    </td>
                    <td className="px-4 py-2 text-dark">
                      {c.user_id ? c.user_id.slice(0, 8) : "anon"}
                    </td>
                    <td className="px-4 py-2 text-dark">
                      {c.category ?? "—"}
                    </td>
                    <td className="px-4 py-2 text-dark">{c.message_count}</td>
                    <td className="px-4 py-2 text-gray">
                      {c.last_message_preview || "—"}
                    </td>
                    <td className="px-4 py-2">
                      {c.escalated ? (
                        <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                          escalated
                        </span>
                      ) : c.resolved ? (
                        <span className="rounded bg-success/10 px-2 py-0.5 text-xs text-success">
                          resolved
                        </span>
                      ) : (
                        <span className="rounded bg-gray/10 px-2 py-0.5 text-xs text-gray">
                          open
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-between border-t px-4 py-2 text-sm text-gray">
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              className="rounded border px-3 py-1 disabled:opacity-50"
            >
              Prev
            </button>
            <button
              disabled={!data || offset + PAGE_SIZE >= data.total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
              className="rounded border px-3 py-1 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </section>

      {selected && (
        <div
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setSelected(null)}
        >
          <div
            className="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-lg bg-white shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b px-4 py-3">
              <div>
                <p className="font-semibold text-dark">Conversation</p>
                <p className="font-mono text-xs text-gray">
                  {selected.session_key}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="rounded border px-3 py-1 text-sm text-dark"
              >
                Close
              </button>
            </div>
            <div className="flex-1 space-y-2 overflow-y-auto bg-[#F4F6F9] p-4">
              {selected.messages.map((m, i) => (
                <div
                  key={i}
                  className={
                    m.role === "user"
                      ? "max-w-[85%] self-end rounded-lg bg-fnu-blue px-3 py-2 text-sm text-white shadow-sm"
                      : "max-w-[85%] self-start rounded-lg border bg-white px-3 py-2 text-sm text-dark shadow-sm"
                  }
                >
                  <p className="mb-0.5 text-[10px] uppercase text-gray-400">
                    {m.role} {m.timestamp ? `· ${new Date(m.timestamp).toLocaleString()}` : ""}
                  </p>
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {selectLoading && (
        <p className="text-sm text-gray">Loading conversation…</p>
      )}
    </div>
  );
}
