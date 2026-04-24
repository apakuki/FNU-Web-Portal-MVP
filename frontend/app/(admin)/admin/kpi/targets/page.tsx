"use client";

import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface KpiDef {
  code: string;
  name: string;
  category: string;
  unit: string;
  target_default: number | null;
  direction: string;
  source: string;
  description: string | null;
}

export default function KpiTargetsPage() {
  const [defs, setDefs] = useState<KpiDef[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const rows = await apiFetch<KpiDef[]>("/api/admin/kpi/definitions");
      setDefs(rows);
      setEdits(
        Object.fromEntries(
          rows.map((r) => [
            r.code,
            r.target_default != null ? String(r.target_default) : "",
          ]),
        ),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(code: string) {
    setError("");
    setMessage("");
    const raw = edits[code];
    const parsed = raw === "" ? null : Number(raw);
    if (parsed !== null && !Number.isFinite(parsed)) {
      setError(`Target for ${code} must be a number`);
      return;
    }
    try {
      await apiFetch(`/api/admin/kpi/definitions/${code}/target`, {
        method: "PUT",
        body: JSON.stringify({ target_default: parsed }),
      });
      setMessage(`Updated target for ${code}`);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Update failed");
    }
  }

  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold text-dark">KPI Targets</h1>
      <p className="mb-4 text-sm text-gray">
        Set the default target value per KPI. Changes are audit-logged.
      </p>
      {error && (
        <p className="mb-3 text-sm text-danger" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="mb-3 text-sm text-success" role="status">
          {message}
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border bg-white shadow-sm">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-surface text-xs uppercase tracking-wide text-gray">
            <tr>
              <th className="px-4 py-3">KPI</th>
              <th className="px-4 py-3">Category</th>
              <th className="px-4 py-3">Unit</th>
              <th className="px-4 py-3">Direction</th>
              <th className="px-4 py-3">Target</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {defs.map((d) => (
              <tr key={d.code} className="border-t">
                <td className="px-4 py-3">
                  <p className="font-medium text-dark">{d.name}</p>
                  <p className="text-xs text-gray">{d.code}</p>
                </td>
                <td className="px-4 py-3 text-gray">{d.category}</td>
                <td className="px-4 py-3 text-gray">{d.unit}</td>
                <td className="px-4 py-3 text-gray">
                  {d.direction === "lower_better" ? "Lower better" : "Higher better"}
                </td>
                <td className="px-4 py-3">
                  <input
                    type="number"
                    step="any"
                    value={edits[d.code] ?? ""}
                    onChange={(e) =>
                      setEdits({ ...edits, [d.code]: e.target.value })
                    }
                    className="input-field min-h-[36px] w-28 rounded border px-2 py-1"
                  />
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => save(d.code)}
                    className="min-h-[36px] rounded bg-dark px-3 py-1 text-sm text-white"
                  >
                    Save
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
