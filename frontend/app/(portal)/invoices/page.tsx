import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";
import Link from "next/link";

interface InvoiceItem {
  code: string;
  description: string;
  amount_cents: number;
  fee_type: string;
}

interface Invoice {
  invoice_id: string;
  semester: string;
  year: number;
  items: InvoiceItem[];
  total_cents: number;
  paid_cents: number;
  balance_cents: number;
  due_date: string | null;
  status: string;
}

const STATUS_STYLES: Record<string, string> = {
  paid: "bg-success/10 text-success",
  partially_paid: "bg-amber-100 text-amber-700",
  unpaid: "bg-danger/10 text-danger",
  overdue: "bg-danger/20 text-danger font-semibold",
};

async function getInvoices(token: string): Promise<Invoice[]> {
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/invoices`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

function fmtCents(cents: number) {
  return `FJ$${(cents / 100).toFixed(2)}`;
}

export default async function InvoicesPage() {
  const session = await getServerSession(authOptions);
  const token = (session?.user as { accessToken?: string })?.accessToken ?? "";
  const invoices = await getInvoices(token);

  const totalBalance = invoices.reduce((sum, i) => sum + i.balance_cents, 0);

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark">My Invoices</h1>
          <p className="text-sm text-gray">Fee statements and payment records</p>
        </div>
        {totalBalance > 0 && (
          <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-2 text-right">
            <p className="text-xs text-gray">Total Outstanding</p>
            <p className="font-bold text-danger">{fmtCents(totalBalance)}</p>
          </div>
        )}
      </div>

      {invoices.length === 0 ? (
        <div className="rounded-lg border bg-white p-8 text-center">
          <p className="text-gray">No invoices found.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {invoices.map((inv) => {
            const statusLabel = inv.status.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
            return (
              <div key={inv.invoice_id} className="rounded-lg border bg-white shadow-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
                  <div>
                    <h2 className="font-semibold text-dark">{inv.invoice_id}</h2>
                    <p className="text-sm text-gray">
                      {inv.semester} {inv.year}
                      {inv.due_date && ` · Due ${inv.due_date}`}
                    </p>
                  </div>
                  <span
                    className={`rounded px-2 py-1 text-xs ${STATUS_STYLES[inv.status] ?? "bg-gray/10 text-gray"}`}
                  >
                    {statusLabel}
                  </span>
                </div>

                <div className="px-4 py-3">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray">
                        <th className="pb-2 font-medium">Description</th>
                        <th className="pb-2 text-right font-medium">Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inv.items.map((item) => (
                        <tr key={item.code} className="border-t">
                          <td className="py-1.5 text-dark">
                            {item.description}
                            {item.fee_type !== "tuition" && (
                              <span className="ml-1 text-xs text-gray">({item.fee_type})</span>
                            )}
                          </td>
                          <td className="py-1.5 text-right text-dark">
                            {fmtCents(item.amount_cents)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot>
                      <tr className="border-t-2 border-dark/20 font-semibold">
                        <td className="pt-2">Total</td>
                        <td className="pt-2 text-right">{fmtCents(inv.total_cents)}</td>
                      </tr>
                      <tr className="text-gray">
                        <td className="pt-1">Paid</td>
                        <td className="pt-1 text-right text-success">
                          − {fmtCents(inv.paid_cents)}
                        </td>
                      </tr>
                      <tr className="font-bold">
                        <td className="pt-1">Balance Due</td>
                        <td
                          className={`pt-1 text-right ${inv.balance_cents > 0 ? "text-danger" : "text-success"}`}
                        >
                          {fmtCents(inv.balance_cents)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>

                <div className="flex items-center justify-between border-t px-4 py-3">
                  <a
                    href={`/api/invoices/${inv.invoice_id}.pdf`}
                    className="text-sm font-medium text-fnu-blue hover:underline"
                  >
                    Download PDF
                  </a>
                  {inv.balance_cents > 0 && (
                    <Link
                      href="/pay"
                      className="rounded bg-fnu-gold px-4 py-1.5 text-sm font-medium text-dark transition hover:bg-fnu-gold/90"
                    >
                      Pay Now
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
