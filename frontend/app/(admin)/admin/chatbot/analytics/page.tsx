"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface Analytics {
  total_conversations: number;
  escalated_conversations: number;
  resolved_conversations: number;
  escalation_rate: number;
  resolution_rate: number;
  active_knowledge_entries: number;
  top_categories: { category: string; count: number }[];
}

const DAY_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
];

function pct(v: number) {
  return `${(v * 100).toFixed(1)}%`;
}

export default function ChatbotAnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch<Analytics>(
        `/api/admin/chatbot/analytics?days=${days}`,
      );
      setData(res);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load analytics",
      );
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-dark">Chatbot Analytics</h1>
          <p className="text-sm text-gray">Usage summary for the selected window.</p>
        </div>
        <div className="flex gap-2">
          {DAY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={`rounded border px-3 py-1.5 text-sm ${
                days === opt.value
                  ? "border-fnu-blue bg-fnu-blue text-white"
                  : "text-dark"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="rounded border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      {loading || !data ? (
        <p className="text-gray">Loading…</p>
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                label: "Total conversations",
                value: data.total_conversations.toString(),
              },
              {
                label: "Escalated",
                value: `${data.escalated_conversations} (${pct(data.escalation_rate)})`,
              },
              {
                label: "Resolved",
                value: `${data.resolved_conversations} (${pct(data.resolution_rate)})`,
              },
              {
                label: "Active FAQ entries",
                value: data.active_knowledge_entries.toString(),
              },
            ].map((c) => (
              <div
                key={c.label}
                className="rounded-lg border bg-white p-4 shadow-sm"
              >
                <p className="text-sm text-gray">{c.label}</p>
                <p className="mt-1 text-2xl font-bold text-dark">{c.value}</p>
              </div>
            ))}
          </section>

          <section className="rounded-lg border bg-white shadow-sm">
            <h2 className="border-b px-4 py-3 font-semibold text-dark">
              Top escalation categories
            </h2>
            {data.top_categories.length === 0 ? (
              <p className="px-4 py-6 text-gray">
                No escalations recorded in this window.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-left text-gray">
                  <tr>
                    <th className="px-4 py-2 font-medium">Category</th>
                    <th className="px-4 py-2 font-medium text-right">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_categories.map((row) => (
                    <tr key={row.category} className="border-t">
                      <td className="px-4 py-2 text-dark">{row.category}</td>
                      <td className="px-4 py-2 text-right text-dark">
                        {row.count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </div>
  );
}
