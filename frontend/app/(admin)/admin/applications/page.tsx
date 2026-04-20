"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface ApplicationItem {
  id: string;
  application_number: string;
  applicant_email: string;
  status: string;
  programme: string | null;
  campus: string | null;
  submitted_at: string;
  decided_at: string | null;
}

interface ApplicationListResponse {
  items: ApplicationItem[];
  total: number;
  page: number;
  per_page: number;
}

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "submitted", label: "Submitted" },
  { value: "under_review", label: "Under Review" },
  { value: "awaiting_documents", label: "Awaiting Documents" },
  { value: "approved", label: "Approved" },
  { value: "conditionally_approved", label: "Conditionally Approved" },
  { value: "rejected", label: "Rejected" },
];

const STATUS_BADGES: Record<string, string> = {
  submitted: "bg-fnu-blue/10 text-fnu-blue",
  under_review: "bg-warning/10 text-warning",
  awaiting_documents: "bg-fnu-gold/20 text-dark",
  approved: "bg-success/10 text-success",
  conditionally_approved: "bg-success/10 text-success",
  rejected: "bg-danger/10 text-danger",
};

export default function ApplicationsQueuePage() {
  const [applications, setApplications] = useState<ApplicationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchApplications = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("per_page", "20");
      if (statusFilter) params.set("status", statusFilter);

      const data = await apiFetch<ApplicationListResponse>(
        `/api/admin/applications?${params}`,
      );
      setApplications(data.items);
      setTotal(data.total);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to load applications");
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter]);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  const totalPages = Math.ceil(total / 20);

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-dark">Applications</h1>
        <span className="text-sm text-gray">{total} total</span>
      </div>

      <div className="mb-4">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="rounded border border-gray/30 px-3 py-2 text-sm"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="mb-4 text-sm text-danger" role="alert">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b bg-surface">
            <tr>
              <th className="px-4 py-3 font-medium text-gray">App #</th>
              <th className="px-4 py-3 font-medium text-gray">Email</th>
              <th className="px-4 py-3 font-medium text-gray">Programme</th>
              <th className="px-4 py-3 font-medium text-gray">Campus</th>
              <th className="px-4 py-3 font-medium text-gray">Status</th>
              <th className="px-4 py-3 font-medium text-gray">Submitted</th>
              <th className="px-4 py-3 font-medium text-gray"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray">
                  Loading...
                </td>
              </tr>
            ) : applications.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray">
                  No applications found
                </td>
              </tr>
            ) : (
              applications.map((app) => (
                <tr key={app.id} className="border-b last:border-0">
                  <td className="px-4 py-3 font-medium">
                    {app.application_number}
                  </td>
                  <td className="px-4 py-3">{app.applicant_email}</td>
                  <td className="px-4 py-3">{app.programme || "—"}</td>
                  <td className="px-4 py-3">{app.campus || "—"}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        STATUS_BADGES[app.status] || "bg-gray/10 text-gray"
                      }`}
                    >
                      {app.status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray">
                    {new Date(app.submitted_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/applications/${app.id}`}
                      className="text-fnu-blue hover:underline"
                    >
                      Review
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="rounded border px-3 py-1 text-sm disabled:opacity-50"
          >
            Previous
          </button>
          <span className="text-sm text-gray">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded border px-3 py-1 text-sm disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
