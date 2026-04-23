"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface DashboardSummary {
  pending_applications: number;
  applications_awaiting_documents: number;
  open_enquiries: number;
  escalated_enquiries: number;
  avg_application_decision_hours: number | null;
  avg_enquiry_resolution_hours: number | null;
  active_students: number;
}

function fmtHours(v: number | null): string {
  if (v == null) return "—";
  if (v < 1) return `${Math.round(v * 60)} min`;
  if (v < 48) return `${v.toFixed(1)} hrs`;
  return `${(v / 24).toFixed(1)} days`;
}

export default function AdminDashboardPage() {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<DashboardSummary>("/api/admin/dashboard/summary")
      .then(setData)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Failed to load stats"),
      )
      .finally(() => setLoading(false));
  }, []);

  const cards = data
    ? [
        {
          title: "Pending applications",
          value: String(data.pending_applications),
          href: "/admin/applications?status=submitted",
          sub: `${data.applications_awaiting_documents} awaiting documents`,
        },
        {
          title: "Open enquiries",
          value: String(data.open_enquiries),
          href: "/admin/enquiries?status=open",
          sub: `${data.escalated_enquiries} from chatbot escalations`,
        },
        {
          title: "Active students",
          value: String(data.active_students),
          href: "/admin/students",
        },
        {
          title: "Avg. application decision",
          value: fmtHours(data.avg_application_decision_hours),
          sub: "Receipt → decision timestamp",
        },
        {
          title: "Avg. enquiry resolution",
          value: fmtHours(data.avg_enquiry_resolution_hours),
          sub: "Open → resolved timestamp",
        },
      ]
    : [];

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-dark">Admin Dashboard</h1>

      {loading && <p className="text-sm text-gray">Loading...</p>}
      {error && (
        <p className="mb-4 text-sm text-danger" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => {
          const body = (
            <>
              <p className="text-sm text-gray">{c.title}</p>
              <p className="mt-1 text-2xl font-bold text-dark">{c.value}</p>
              {c.sub && <p className="mt-1 text-xs text-gray">{c.sub}</p>}
            </>
          );
          return c.href ? (
            <Link
              key={c.title}
              href={c.href}
              className="rounded-lg border bg-white p-6 shadow-sm transition hover:border-fnu-blue"
            >
              {body}
            </Link>
          ) : (
            <div
              key={c.title}
              className="rounded-lg border bg-white p-6 shadow-sm"
            >
              {body}
            </div>
          );
        })}
      </div>
    </div>
  );
}
