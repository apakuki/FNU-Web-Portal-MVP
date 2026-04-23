"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface StudentItem {
  id: string;
  banner_id: string | null;
  email: string;
  full_name: string;
  phone: string | null;
  is_active: boolean;
  programme_code: string | null;
  campus: string | null;
  enrolment_status: string | null;
}

interface StudentListResponse {
  items: StudentItem[];
  total: number;
  page: number;
  per_page: number;
}

const PROGRAMMES = ["", "BCOM", "BSCI", "BNUR", "DIT", "CEDU"];
const CAMPUSES = ["", "Nasinu", "Suva", "Lautoka", "Labasa", "Nausori", "Ba"];
const STATUSES = ["", "active", "suspended", "graduated", "deregistered"];

export default function AdminStudentsPage() {
  const [rows, setRows] = useState<StudentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [programme, setProgramme] = useState("");
  const [campus, setCampus] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const perPage = 25;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("per_page", String(perPage));
      if (q) params.set("q", q);
      if (programme) params.set("programme", programme);
      if (campus) params.set("campus", campus);
      if (status) params.set("status", status);

      const data = await apiFetch<StudentListResponse>(
        `/api/admin/students?${params}`,
      );
      setRows(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load students");
    } finally {
      setLoading(false);
    }
  }, [page, q, programme, campus, status]);

  useEffect(() => {
    load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-dark">Students</h1>
        <span className="text-sm text-gray">{total} matching</span>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
          placeholder="Search by name, email, Banner ID"
          className="input-field"
          aria-label="Search"
        />
        <select
          value={programme}
          onChange={(e) => {
            setProgramme(e.target.value);
            setPage(1);
          }}
          className="input-field"
          aria-label="Programme"
        >
          {PROGRAMMES.map((p) => (
            <option key={p} value={p}>
              {p || "All programmes"}
            </option>
          ))}
        </select>
        <select
          value={campus}
          onChange={(e) => {
            setCampus(e.target.value);
            setPage(1);
          }}
          className="input-field"
          aria-label="Campus"
        >
          {CAMPUSES.map((c) => (
            <option key={c} value={c}>
              {c || "All campuses"}
            </option>
          ))}
        </select>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          className="input-field"
          aria-label="Enrolment status"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s || "All enrolment statuses"}
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
              <th className="px-4 py-3 font-medium text-gray">Name</th>
              <th className="px-4 py-3 font-medium text-gray">Banner ID</th>
              <th className="px-4 py-3 font-medium text-gray">Email</th>
              <th className="px-4 py-3 font-medium text-gray">Programme</th>
              <th className="px-4 py-3 font-medium text-gray">Campus</th>
              <th className="px-4 py-3 font-medium text-gray">Status</th>
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
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray">
                  No students match these filters
                </td>
              </tr>
            ) : (
              rows.map((s) => (
                <tr key={s.id} className="border-b last:border-0">
                  <td className="px-4 py-3 font-medium">{s.full_name}</td>
                  <td className="px-4 py-3">{s.banner_id || "—"}</td>
                  <td className="px-4 py-3">{s.email}</td>
                  <td className="px-4 py-3">{s.programme_code || "—"}</td>
                  <td className="px-4 py-3">{s.campus || "—"}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        s.enrolment_status === "active"
                          ? "bg-success/10 text-success"
                          : "bg-gray/10 text-gray"
                      }`}
                    >
                      {s.enrolment_status || (s.is_active ? "active" : "inactive")}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/admin/students/${s.id}`}
                      className="text-fnu-blue hover:underline"
                    >
                      View
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
