"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface EnquiryItem {
  id: string;
  subject: string;
  source: string;
  status: string;
  student_identifier: string | null;
  student_user_id: string | null;
  assigned_staff_id: string | null;
  opened_at: string;
  resolved_at: string | null;
}

interface EnquiryListResponse {
  items: EnquiryItem[];
  total: number;
  page: number;
  per_page: number;
}

const STATUS_FILTERS = ["", "open", "in_progress", "resolved", "closed"];
const SOURCE_FILTERS = ["", "chatbot", "phone", "email", "walk_in", "staff"];

const STATUS_BADGE: Record<string, string> = {
  open: "bg-warning/10 text-warning",
  in_progress: "bg-fnu-blue/10 text-fnu-blue",
  resolved: "bg-success/10 text-success",
  closed: "bg-gray/10 text-gray",
};

export default function AdminEnquiriesPage() {
  const [items, setItems] = useState<EnquiryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("open");
  const [source, setSource] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showNew, setShowNew] = useState(false);
  const [newSubject, setNewSubject] = useState("");
  const [newBody, setNewBody] = useState("");
  const [newSource, setNewSource] = useState("phone");
  const [newStudentId, setNewStudentId] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const perPage = 25;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("per_page", String(perPage));
      if (status) params.set("status", status);
      if (source) params.set("source", source);
      if (q) params.set("q", q);
      const data = await apiFetch<EnquiryListResponse>(
        `/api/admin/enquiries?${params}`,
      );
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load enquiries");
    } finally {
      setLoading(false);
    }
  }, [page, status, source, q]);

  useEffect(() => {
    load();
  }, [load]);

  async function createEnquiry() {
    setCreateError("");
    if (!newSubject.trim() || !newBody.trim()) {
      setCreateError("Subject and body are required");
      return;
    }
    setCreating(true);
    try {
      await apiFetch("/api/admin/enquiries", {
        method: "POST",
        body: JSON.stringify({
          subject: newSubject,
          body: newBody,
          source: newSource,
          student_identifier: newStudentId || null,
        }),
      });
      setShowNew(false);
      setNewSubject("");
      setNewBody("");
      setNewStudentId("");
      await load();
    } catch (err) {
      setCreateError(
        err instanceof ApiError ? err.message : "Failed to create enquiry",
      );
    } finally {
      setCreating(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-dark">Enquiries</h1>
        <button
          onClick={() => setShowNew((v) => !v)}
          className="rounded bg-fnu-blue px-3 py-2 text-sm font-medium text-white hover:bg-fnu-blue/90"
        >
          {showNew ? "Cancel" : "Log enquiry"}
        </button>
      </div>

      {showNew && (
        <div className="mb-6 rounded-lg border bg-white p-5">
          <h2 className="mb-3 font-bold text-fnu-blue">Log a new enquiry</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className="input-field"
              placeholder="Subject"
              value={newSubject}
              onChange={(e) => setNewSubject(e.target.value)}
            />
            <select
              className="input-field"
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
            >
              <option value="phone">Phone</option>
              <option value="email">Email</option>
              <option value="walk_in">Walk-in</option>
              <option value="staff">Staff</option>
            </select>
          </div>
          <input
            className="input-field mt-3"
            placeholder="Student identifier (Banner ID / email) — optional"
            value={newStudentId}
            onChange={(e) => setNewStudentId(e.target.value)}
          />
          <textarea
            className="input-field mt-3"
            rows={4}
            placeholder="Describe the enquiry"
            value={newBody}
            onChange={(e) => setNewBody(e.target.value)}
          />
          {createError && (
            <p className="mt-2 text-sm text-danger">{createError}</p>
          )}
          <button
            onClick={createEnquiry}
            disabled={creating}
            className="mt-3 rounded bg-success px-4 py-2 text-sm font-medium text-white hover:bg-success/90 disabled:opacity-50"
          >
            {creating ? "Saving..." : "Save enquiry"}
          </button>
        </div>
      )}

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Search subject or body"
          className="input-field"
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="input-field"
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s || "All statuses"}
            </option>
          ))}
        </select>
        <select
          value={source}
          onChange={(e) => {
            setSource(e.target.value);
            setPage(1);
          }}
          className="input-field"
        >
          {SOURCE_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s || "All sources"}
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
              <th className="px-4 py-3 font-medium text-gray">Subject</th>
              <th className="px-4 py-3 font-medium text-gray">Student</th>
              <th className="px-4 py-3 font-medium text-gray">Source</th>
              <th className="px-4 py-3 font-medium text-gray">Status</th>
              <th className="px-4 py-3 font-medium text-gray">Opened</th>
              <th className="px-4 py-3 font-medium text-gray"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray">
                  Loading...
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray">
                  No enquiries match these filters
                </td>
              </tr>
            ) : (
              items.map((e) => (
                <tr key={e.id} className="border-b last:border-0">
                  <td className="px-4 py-3 font-medium">{e.subject}</td>
                  <td className="px-4 py-3">{e.student_identifier || "—"}</td>
                  <td className="px-4 py-3">{e.source}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        STATUS_BADGE[e.status] || "bg-gray/10 text-gray"
                      }`}
                    >
                      {e.status.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray">
                    {new Date(e.opened_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/enquiries/${e.id}`}
                      className="text-fnu-blue hover:underline"
                    >
                      Open
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
