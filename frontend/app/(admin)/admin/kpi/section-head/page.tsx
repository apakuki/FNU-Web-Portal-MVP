"use client";

import { useEffect, useState } from "react";
import { KpiDashboard } from "@/components/kpi-dashboard";
import { apiFetch, ApiError } from "@/lib/api-client";

interface KpiDef {
  code: string;
  name: string;
  unit: string;
  source: string;
  description: string | null;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function firstOfMonthIso(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}

export default function SectionHeadPage() {
  const [defs, setDefs] = useState<KpiDef[]>([]);
  const [code, setCode] = useState("");
  const [value, setValue] = useState("");
  const [from, setFrom] = useState(firstOfMonthIso());
  const [to, setTo] = useState(todayIso());
  const [college, setCollege] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<KpiDef[]>("/api/admin/kpi/definitions")
      .then((rows) => {
        const manual = rows.filter((r) => r.source === "manual");
        setDefs(manual);
        if (manual[0]) setCode(manual[0].code);
      })
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Failed to load KPIs"),
      );
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const numericValue = Number(value);
      if (!Number.isFinite(numericValue)) {
        setError("Value must be a number");
        setBusy(false);
        return;
      }
      await apiFetch("/api/admin/kpi/manual", {
        method: "POST",
        body: JSON.stringify({
          kpi_code: code,
          value: numericValue,
          period_start: from,
          period_end: to,
          college: college || null,
        }),
      });
      setMessage("Saved manual KPI entry");
      setValue("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  const selectedDef = defs.find((d) => d.code === code);

  return (
    <KpiDashboard
      view="section-head"
      title="Section Head Dashboard"
      subtitle="Team workload plus manual KPI entry (targeting under 5 min/day)."
    >
      <section className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-dark">
          Record manual KPI value
        </h2>
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
        <form
          onSubmit={submit}
          className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
        >
          <label className="flex flex-col text-sm text-dark">
            KPI
            <select
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="input-field mt-1 min-h-[40px] rounded border px-2 py-1"
              required
            >
              {defs.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name} ({d.unit})
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-sm text-dark">
            Value
            <input
              type="number"
              step="any"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="input-field mt-1 min-h-[40px] rounded border px-2 py-1"
              required
            />
          </label>
          <label className="flex flex-col text-sm text-dark">
            College (optional)
            <input
              type="text"
              value={college}
              onChange={(e) => setCollege(e.target.value)}
              placeholder="e.g. CBHTS"
              className="input-field mt-1 min-h-[40px] rounded border px-2 py-1"
            />
          </label>
          <label className="flex flex-col text-sm text-dark">
            From
            <input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="input-field mt-1 min-h-[40px] rounded border px-2 py-1"
              required
            />
          </label>
          <label className="flex flex-col text-sm text-dark">
            To
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="input-field mt-1 min-h-[40px] rounded border px-2 py-1"
              required
            />
          </label>
          <div className="flex items-end">
            <button
              type="submit"
              disabled={busy || !code}
              className="min-h-[40px] w-full rounded bg-dark px-3 py-2 text-sm text-white disabled:opacity-60"
            >
              {busy ? "Saving…" : "Save entry"}
            </button>
          </div>
        </form>
        {selectedDef?.description && (
          <p className="mt-3 text-xs text-gray">{selectedDef.description}</p>
        )}
      </section>
    </KpiDashboard>
  );
}
