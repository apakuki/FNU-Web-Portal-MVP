"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

export interface KpiCard {
  code: string;
  name: string;
  category: string;
  unit: string;
  direction: string;
  value: number;
  target: number | null;
  status: string;
}

export interface KpiDashboardResponse {
  view: string;
  period_start: string;
  period_end: string;
  generated_at: string;
  cards: KpiCard[];
}

type Preset = "current_semester" | "ytd" | "custom";

const STATUS_STYLES: Record<string, string> = {
  green: "bg-success/10 text-success border-success/30",
  amber: "bg-warning/10 text-warning border-warning/30",
  red: "bg-danger/10 text-danger border-danger/30",
  grey: "bg-gray/10 text-gray border-gray/30",
};

function formatValue(card: KpiCard): string {
  const v = card.value;
  if (card.unit === "percent") return `${v.toFixed(1)}%`;
  if (card.unit === "hours") return `${v.toFixed(1)} hrs`;
  if (card.unit === "currency") {
    return `FJ$${v.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  if (card.unit === "score") return v.toFixed(1);
  return Math.round(v).toLocaleString();
}

function formatTarget(card: KpiCard): string {
  if (card.target == null) return "No target set";
  const arrow = card.direction === "lower_better" ? "≤" : "≥";
  if (card.unit === "currency") {
    return `Target ${arrow} FJ$${Number(card.target).toLocaleString()}`;
  }
  if (card.unit === "percent") return `Target ${arrow} ${card.target}%`;
  if (card.unit === "hours") return `Target ${arrow} ${card.target} hrs`;
  return `Target ${arrow} ${card.target}`;
}

interface Props {
  view: "vc" | "dean" | "section-head" | "finance" | "me";
  title: string;
  subtitle?: string;
  allowExport?: boolean;
  allowRecompute?: boolean;
  children?: React.ReactNode;
}

export function KpiDashboard({
  view,
  title,
  subtitle,
  allowExport,
  allowRecompute,
  children,
}: Props) {
  const [preset, setPreset] = useState<Preset>("current_semester");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [data, setData] = useState<KpiDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [recomputing, setRecomputing] = useState(false);
  const [message, setMessage] = useState("");

  const query = useMemo(() => {
    const params = new URLSearchParams({ preset });
    if (preset === "custom" && from && to) {
      params.set("period_start", from);
      params.set("period_end", to);
    }
    return params.toString();
  }, [preset, from, to]);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch<KpiDashboardResponse>(
        `/api/admin/kpi/dashboard/${view}?${query}`,
      );
      setData(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load KPIs");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (preset !== "custom" || (from && to)) {
      load();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  async function recompute() {
    setRecomputing(true);
    setMessage("");
    try {
      await apiFetch(`/api/admin/kpi/compute?${query}`, { method: "POST" });
      setMessage("Recompute complete");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Recompute failed");
    } finally {
      setRecomputing(false);
    }
  }

  async function exportCsv() {
    const session = await (await import("next-auth/react")).getSession();
    const token = (session?.user as any)?.accessToken;
    const res = await fetch(`/api/admin/kpi/dashboard/finance/export?${query}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      setError("Export failed");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `finance_kpi_${data?.period_start}_${data?.period_end}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-dark">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-gray">{subtitle}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-sm text-gray" htmlFor="preset">
            Period
          </label>
          <select
            id="preset"
            value={preset}
            onChange={(e) => setPreset(e.target.value as Preset)}
            className="input-field min-h-[40px] rounded border px-2 py-1 text-sm"
          >
            <option value="current_semester">Current semester</option>
            <option value="ytd">Year to date</option>
            <option value="custom">Custom range</option>
          </select>
          {preset === "custom" && (
            <>
              <input
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
                className="input-field min-h-[40px] rounded border px-2 py-1 text-sm"
                aria-label="From"
              />
              <input
                type="date"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                className="input-field min-h-[40px] rounded border px-2 py-1 text-sm"
                aria-label="To"
              />
            </>
          )}
          {allowRecompute && (
            <button
              type="button"
              onClick={recompute}
              disabled={recomputing}
              className="min-h-[40px] rounded bg-dark px-3 py-1 text-sm text-white disabled:opacity-60"
            >
              {recomputing ? "Recomputing…" : "Recompute"}
            </button>
          )}
          {allowExport && (
            <button
              type="button"
              onClick={exportCsv}
              className="min-h-[40px] rounded border bg-white px-3 py-1 text-sm text-dark hover:border-dark"
            >
              Export CSV
            </button>
          )}
        </div>
      </div>

      {error && (
        <p className="mb-4 text-sm text-danger" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="mb-4 text-sm text-success" role="status">
          {message}
        </p>
      )}

      {data && (
        <p className="mb-4 text-xs text-gray">
          Period {data.period_start} → {data.period_end}. Generated{" "}
          {new Date(data.generated_at).toLocaleString()}.
        </p>
      )}

      {loading && <p className="text-sm text-gray">Loading KPIs…</p>}

      {data && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.cards.map((card) => (
            <div
              key={card.code}
              className={`rounded-lg border bg-white p-5 shadow-sm ${STATUS_STYLES[card.status] ?? ""}`}
            >
              <div className="flex items-center justify-between">
                <p className="text-xs uppercase tracking-wide text-gray">
                  {card.category}
                </p>
                <span className="rounded bg-white/60 px-2 py-0.5 text-xs font-semibold">
                  {card.status.toUpperCase()}
                </span>
              </div>
              <p className="mt-2 text-sm font-medium text-dark">{card.name}</p>
              <p className="mt-1 text-3xl font-bold text-dark">
                {formatValue(card)}
              </p>
              <p className="mt-1 text-xs text-gray">{formatTarget(card)}</p>
            </div>
          ))}
          {data.cards.length === 0 && (
            <p className="text-sm text-gray">No data for this period yet.</p>
          )}
        </div>
      )}

      {children}
    </div>
  );
}
