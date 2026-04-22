"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

type Method = "mpaisa" | "mycash" | "bank_transfer";

interface Invoice {
  invoice_id: string;
  semester: string;
  year: number;
  total_cents: number;
  paid_cents: number;
  balance_cents: number;
  due_date: string | null;
  status: string;
}

interface InitiateResponse {
  payment_id: string;
  gateway_reference: string;
  redirect_url: string | null;
  status: string;
  extra: Record<string, unknown>;
}

interface PaymentHistoryItem {
  id: string;
  invoice_id: string;
  method: string;
  amount_cents: number;
  currency: string;
  gateway_reference: string | null;
  status: string;
  created_at: string;
}

interface Instalment {
  due_date: string;
  amount_cents: number;
  status: string;
}

interface AccountSummary {
  balance_cents: number;
  currency: string;
  payment_history: PaymentHistoryItem[];
  instalment_schedule: Instalment[];
}

const METHOD_LABELS: Record<Method, string> = {
  mpaisa: "M-PAiSA (Vodafone)",
  mycash: "MyCash (Digicel)",
  bank_transfer: "Bank Transfer",
};

function fmt(cents: number) {
  return `FJ$${(cents / 100).toFixed(2)}`;
}

function STATUS_STYLE(status: string) {
  if (status === "confirmed") return "bg-success/10 text-success";
  if (status === "failed") return "bg-danger/10 text-danger";
  if (status === "pending" || status === "initiated") return "bg-amber-100 text-amber-700";
  return "bg-gray/10 text-gray";
}

export default function PayPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [account, setAccount] = useState<AccountSummary | null>(null);
  const [selectedInvoice, setSelectedInvoice] = useState<string>("");
  const [method, setMethod] = useState<Method>("mpaisa");
  const [amountMode, setAmountMode] = useState<"full" | "partial">("full");
  const [partialAmount, setPartialAmount] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string>("");
  const [initiated, setInitiated] = useState<InitiateResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [inv, acct] = await Promise.all([
        apiFetch<Invoice[]>("/api/invoices"),
        apiFetch<AccountSummary>("/api/account"),
      ]);
      const unpaid = inv.filter((i) => i.balance_cents > 0);
      setInvoices(unpaid);
      setAccount(acct);
      if (unpaid.length > 0 && !selectedInvoice) {
        setSelectedInvoice(unpaid[0].invoice_id);
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load account data");
    } finally {
      setLoading(false);
    }
  }, [selectedInvoice]);

  useEffect(() => {
    load();
  }, [load]);

  const currentInvoice = invoices.find((i) => i.invoice_id === selectedInvoice);
  const maxCents = currentInvoice?.balance_cents ?? 0;

  function parsedAmountCents(): number | null {
    if (amountMode === "full") return maxCents;
    const dollars = Number(partialAmount);
    if (!Number.isFinite(dollars) || dollars <= 0) return null;
    return Math.round(dollars * 100);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInitiated(null);

    const amount = parsedAmountCents();
    if (!selectedInvoice || !amount || amount <= 0) {
      setError("Enter a valid amount");
      return;
    }
    if (amount > maxCents) {
      setError(`Amount exceeds outstanding balance (${fmt(maxCents)})`);
      return;
    }

    setSubmitting(true);
    try {
      const res = await apiFetch<InitiateResponse>("/api/payments/initiate", {
        method: "POST",
        body: JSON.stringify({
          invoice_id: selectedInvoice,
          method,
          amount_cents: amount,
        }),
      });
      setInitiated(res);
      if (res.redirect_url) {
        window.location.href = res.redirect_url;
      } else {
        load();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Payment failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <p className="text-gray">Loading payment options…</p>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-dark">Make a Payment</h1>
        <p className="text-sm text-gray">
          Pay an invoice using M-PAiSA, MyCash, or bank transfer
        </p>
      </div>

      {account && (
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm text-gray">Total Outstanding</span>
            <span
              className={`text-xl font-bold ${account.balance_cents > 0 ? "text-danger" : "text-success"}`}
            >
              {fmt(account.balance_cents)}
            </span>
          </div>
        </div>
      )}

      {invoices.length === 0 ? (
        <div className="rounded-lg border bg-white p-8 text-center">
          <p className="text-gray">No outstanding invoices.</p>
        </div>
      ) : (
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-lg border bg-white p-6 shadow-sm"
        >
          <div>
            <label htmlFor="invoice" className="block text-sm font-medium text-dark">
              Invoice
            </label>
            <select
              id="invoice"
              value={selectedInvoice}
              onChange={(e) => {
                setSelectedInvoice(e.target.value);
                setAmountMode("full");
                setPartialAmount("");
              }}
              className="mt-1 w-full rounded border px-3 py-2 text-sm"
            >
              {invoices.map((inv) => (
                <option key={inv.invoice_id} value={inv.invoice_id}>
                  {inv.invoice_id} — {inv.semester} {inv.year} · {fmt(inv.balance_cents)} due
                </option>
              ))}
            </select>
          </div>

          <fieldset>
            <legend className="text-sm font-medium text-dark">Payment Method</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
              {(Object.keys(METHOD_LABELS) as Method[]).map((m) => (
                <label
                  key={m}
                  className={`flex cursor-pointer items-center gap-2 rounded border px-3 py-2 text-sm transition ${
                    method === m
                      ? "border-fnu-blue bg-fnu-blue/5"
                      : "border-gray/20 hover:border-fnu-blue/40"
                  }`}
                >
                  <input
                    type="radio"
                    name="method"
                    value={m}
                    checked={method === m}
                    onChange={() => setMethod(m)}
                    className="accent-fnu-blue"
                  />
                  {METHOD_LABELS[m]}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="text-sm font-medium text-dark">Amount</legend>
            <div className="mt-2 space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="amount_mode"
                  checked={amountMode === "full"}
                  onChange={() => setAmountMode("full")}
                  className="accent-fnu-blue"
                />
                Full balance ({fmt(maxCents)})
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name="amount_mode"
                  checked={amountMode === "partial"}
                  onChange={() => setAmountMode("partial")}
                  className="accent-fnu-blue"
                />
                Partial
              </label>
              {amountMode === "partial" && (
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray">FJ$</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    max={(maxCents / 100).toFixed(2)}
                    value={partialAmount}
                    onChange={(e) => setPartialAmount(e.target.value)}
                    placeholder="0.00"
                    className="w-32 rounded border px-3 py-2 text-sm"
                  />
                </div>
              )}
            </div>
          </fieldset>

          {error && (
            <div className="rounded border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded bg-fnu-gold px-4 py-2.5 font-medium text-dark transition hover:bg-fnu-gold/90 disabled:opacity-50 sm:w-auto"
          >
            {submitting ? "Processing…" : `Pay ${fmt(parsedAmountCents() ?? 0)}`}
          </button>
        </form>
      )}

      {initiated && !initiated.redirect_url && (
        <div className="rounded-lg border border-fnu-blue/30 bg-fnu-blue/5 p-4">
          <h2 className="font-semibold text-dark">Payment Initiated</h2>
          <p className="mt-1 text-sm text-gray">
            Reference: <code className="rounded bg-white px-1">{initiated.gateway_reference}</code>
          </p>
          {method === "bank_transfer" && initiated.extra && (
            <div className="mt-3 space-y-1 text-sm">
              <p className="font-medium text-dark">Bank deposit details:</p>
              <p>Bank: {String(initiated.extra.bank_name)}</p>
              <p>Account Name: {String(initiated.extra.account_name)}</p>
              <p>Account Number: {String(initiated.extra.account_number)}</p>
              <p>
                Reference (required on deposit slip):{" "}
                <code className="rounded bg-white px-1">
                  {String(initiated.extra.deposit_reference)}
                </code>
              </p>
              <p className="text-gray">
                Your payment will be confirmed by finance once the deposit is received (1–2
                business days).
              </p>
            </div>
          )}
        </div>
      )}

      {account && account.payment_history.length > 0 && (
        <div className="rounded-lg border bg-white shadow-sm">
          <h2 className="border-b px-4 py-3 font-semibold text-dark">Recent Payments</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-gray">
              <tr>
                <th className="px-4 py-2 font-medium">Date</th>
                <th className="px-4 py-2 font-medium">Invoice</th>
                <th className="px-4 py-2 font-medium">Method</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {account.payment_history.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="px-4 py-2 text-dark">
                    {new Date(p.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-dark">{p.invoice_id}</td>
                  <td className="px-4 py-2 text-dark">
                    {METHOD_LABELS[p.method as Method] ?? p.method}
                  </td>
                  <td className="px-4 py-2 text-right text-dark">{fmt(p.amount_cents)}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE(p.status)}`}>
                      {p.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {account && account.instalment_schedule.length > 0 && (
        <div className="rounded-lg border bg-white shadow-sm">
          <h2 className="border-b px-4 py-3 font-semibold text-dark">Payment Plan</h2>
          <table className="w-full text-sm">
            <thead className="text-left text-gray">
              <tr>
                <th className="px-4 py-2 font-medium">Due Date</th>
                <th className="px-4 py-2 text-right font-medium">Amount</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {account.instalment_schedule.map((inst, idx) => (
                <tr key={idx} className="border-t">
                  <td className="px-4 py-2 text-dark">{inst.due_date}</td>
                  <td className="px-4 py-2 text-right text-dark">{fmt(inst.amount_cents)}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${STATUS_STYLE(inst.status)}`}>
                      {inst.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
