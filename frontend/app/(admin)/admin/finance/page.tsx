"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface ReconciliationEntry {
  payment_id: string;
  student_banner_id: string | null;
  invoice_id: string;
  method: string;
  amount_cents: number;
  status: string;
  gateway_reference: string | null;
  created_at: string;
}

interface ReconciliationReport {
  period_from: string;
  period_to: string;
  total_confirmed_cents: number;
  by_method: Record<string, number>;
  entries: ReconciliationEntry[];
}

const METHOD_OPTIONS = [
  { value: "", label: "All Methods" },
  { value: "mpaisa", label: "M-PAiSA" },
  { value: "mycash", label: "MyCash" },
  { value: "bank_transfer", label: "Bank Transfer" },
];

const METHOD_LABEL: Record<string, string> = {
  mpaisa: "M-PAiSA",
  mycash: "MyCash",
  bank_transfer: "Bank Transfer",
};

const STATUS_STYLE: Record<string, string> = {
  confirmed: "bg-success/10 text-success",
  failed: "bg-danger/10 text-danger",
  pending: "bg-amber-100 text-amber-700",
  initiated: "bg-amber-100 text-amber-700",
  refunded: "bg-gray/10 text-gray",
};

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoISO(days: number) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

function fmt(cents: number) {
  return `FJ$${(cents / 100).toFixed(2)}`;
}

export default function FinanceDashboardPage() {
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [dateFrom, setDateFrom] = useState(daysAgoISO(30));
  const [dateTo, setDateTo] = useState(todayISO());
  const [method, setMethod] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [confirmPaymentId, setConfirmPaymentId] = useState("");
  const [confirmReference, setConfirmReference] = useState("");
  const [confirmAmount, setConfirmAmount] = useState("");
  const [confirmMsg, setConfirmMsg] = useState("");
  const [confirmErr, setConfirmErr] = useState("");
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        date_from: `${dateFrom}T00:00:00`,
        date_to: `${dateTo}T23:59:59`,
      });
      if (method) params.set("method", method);
      const data = await apiFetch<ReconciliationReport>(
        `/api/payments/reconciliation?${params}`,
      );
      setReport(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, method]);

  useEffect(() => {
    load();
  }, [load]);

  function downloadCsv() {
    const params = new URLSearchParams({
      date_from: `${dateFrom}T00:00:00`,
      date_to: `${dateTo}T23:59:59`,
      format: "csv",
    });
    if (method) params.set("method", method);
    const base = process.env.NEXT_PUBLIC_API_URL ?? "";
    window.open(`${base}/api/payments/reconciliation?${params}`, "_blank");
  }

  async function handleBankConfirm(e: React.FormEvent) {
    e.preventDefault();
    setConfirmErr("");
    setConfirmMsg("");
    const dollars = Number(confirmAmount);
    if (!Number.isFinite(dollars) || dollars <= 0) {
      setConfirmErr("Enter a valid amount");
      return;
    }
    setConfirming(true);
    try {
      const res = await apiFetch<{ detail: string; payment_id: string }>(
        "/api/payments/bank-confirm",
        {
          method: "POST",
          body: JSON.stringify({
            payment_id: confirmPaymentId.trim(),
            bank_reference: confirmReference.trim(),
            amount_cents: Math.round(dollars * 100),
          }),
        },
      );
      setConfirmMsg(`${res.detail} (payment ${res.payment_id})`);
      setConfirmPaymentId("");
      setConfirmReference("");
      setConfirmAmount("");
      load();
    } catch (err) {
      setConfirmErr(err instanceof ApiError ? err.message : "Confirmation failed");
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-dark">Finance — Payments</h1>
        <p className="text-sm text-gray">
          Review received payments, reconcile daily totals, and confirm bank transfers
        </p>
      </div>

      <section className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold text-dark">Filters</h2>
        <div className="grid gap-3 sm:grid-cols-4">
          <label className="text-sm">
            <span className="text-gray">From</span>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="text-gray">To</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
            />
          </label>
          <label className="text-sm">
            <span className="text-gray">Method</span>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
            >
              {METHOD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-end gap-2">
            <button
              onClick={load}
              className="rounded bg-fnu-blue px-3 py-1.5 text-sm font-medium text-white"
            >
              Apply
            </button>
            <button
              onClick={downloadCsv}
              className="rounded border border-fnu-blue px-3 py-1.5 text-sm font-medium text-fnu-blue"
            >
              Export CSV
            </button>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-gray">Loading…</p>
      ) : report ? (
        <>
          <section className="grid gap-4 sm:grid-cols-4">
            <div className="rounded-lg border bg-white p-4 shadow-sm">
              <p className="text-sm text-gray">Total Confirmed</p>
              <p className="mt-1 text-2xl font-bold text-success">
                {fmt(report.total_confirmed_cents)}
              </p>
            </div>
            {Object.entries(report.by_method).map(([m, cents]) => (
              <div key={m} className="rounded-lg border bg-white p-4 shadow-sm">
                <p className="text-sm text-gray">{METHOD_LABEL[m] ?? m}</p>
                <p className="mt-1 text-xl font-semibold text-dark">{fmt(cents)}</p>
              </div>
            ))}
          </section>

          <section className="rounded-lg border bg-white shadow-sm">
            <h2 className="border-b px-4 py-3 font-semibold text-dark">
              Payments ({report.entries.length})
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-gray">
                  <tr>
                    <th className="px-4 py-2 font-medium">Date</th>
                    <th className="px-4 py-2 font-medium">Student</th>
                    <th className="px-4 py-2 font-medium">Invoice</th>
                    <th className="px-4 py-2 font-medium">Method</th>
                    <th className="px-4 py-2 text-right font-medium">Amount</th>
                    <th className="px-4 py-2 font-medium">Reference</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {report.entries.map((e) => (
                    <tr key={e.payment_id} className="border-t">
                      <td className="px-4 py-2 text-dark">
                        {new Date(e.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-dark">
                        {e.student_banner_id ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-dark">{e.invoice_id}</td>
                      <td className="px-4 py-2 text-dark">
                        {METHOD_LABEL[e.method] ?? e.method}
                      </td>
                      <td className="px-4 py-2 text-right text-dark">
                        {fmt(e.amount_cents)}
                      </td>
                      <td className="px-4 py-2 text-xs text-gray">
                        {e.gateway_reference ?? "—"}
                      </td>
                      <td className="px-4 py-2">
                        <span
                          className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE[e.status] ?? "bg-gray/10 text-gray"}`}
                        >
                          {e.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {report.entries.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-gray">
                        No payments in this range.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}

      <section className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold text-dark">Confirm Bank Transfer</h2>
        <p className="mb-3 text-sm text-gray">
          When a deposit lands in the FNU account, enter the payment ID (student-initiated
          bank transfer), the bank reference, and confirmed amount.
        </p>
        <form onSubmit={handleBankConfirm} className="grid gap-3 sm:grid-cols-3">
          <label className="text-sm sm:col-span-1">
            <span className="text-gray">Payment ID</span>
            <input
              type="text"
              value={confirmPaymentId}
              onChange={(e) => setConfirmPaymentId(e.target.value)}
              required
              className="mt-1 block w-full rounded border px-2 py-1.5 text-sm font-mono"
              placeholder="uuid"
            />
          </label>
          <label className="text-sm sm:col-span-1">
            <span className="text-gray">Bank Reference</span>
            <input
              type="text"
              value={confirmReference}
              onChange={(e) => setConfirmReference(e.target.value)}
              required
              className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
            />
          </label>
          <label className="text-sm sm:col-span-1">
            <span className="text-gray">Amount (FJD)</span>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={confirmAmount}
              onChange={(e) => setConfirmAmount(e.target.value)}
              required
              className="mt-1 block w-full rounded border px-2 py-1.5 text-sm"
            />
          </label>
          <div className="sm:col-span-3 flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={confirming}
              className="rounded bg-fnu-blue px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {confirming ? "Confirming…" : "Confirm Deposit"}
            </button>
            {confirmMsg && <span className="text-sm text-success">{confirmMsg}</span>}
            {confirmErr && <span className="text-sm text-danger">{confirmErr}</span>}
          </div>
        </form>
      </section>
    </div>
  );
}
