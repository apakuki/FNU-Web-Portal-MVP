"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface EnquiryDetail {
  id: string;
  subject: string;
  body: string;
  source: string;
  status: string;
  student_identifier: string | null;
  student_user_id: string | null;
  assigned_staff_id: string | null;
  assigned_staff_name: string | null;
  resolution_note: string | null;
  student_feedback: number | null;
  opened_at: string;
  resolved_at: string | null;
}

const STATUS_OPTIONS = ["open", "in_progress", "resolved", "closed"];

export default function AdminEnquiryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [data, setData] = useState<EnquiryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newStatus, setNewStatus] = useState("");
  const [resolutionNote, setResolutionNote] = useState("");
  const [feedback, setFeedback] = useState<number | "">("");
  const [actionError, setActionError] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiFetch<EnquiryDetail>(`/api/admin/enquiries/${id}`);
      setData(d);
      setNewStatus(d.status);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load enquiry");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function saveChanges() {
    if (!data) return;
    setActionError("");
    setSaving(true);
    const payload: Record<string, unknown> = {};
    if (newStatus !== data.status) payload.status = newStatus;
    if (!data.resolution_note && resolutionNote.trim()) {
      payload.resolution_note = resolutionNote.trim();
    }
    if (Object.keys(payload).length === 0) {
      setSaving(false);
      return;
    }
    try {
      const updated = await apiFetch<EnquiryDetail>(
        `/api/admin/enquiries/${id}`,
        { method: "PUT", body: JSON.stringify(payload) },
      );
      setData(updated);
      setNewStatus(updated.status);
      setResolutionNote("");
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Failed to save changes",
      );
    } finally {
      setSaving(false);
    }
  }

  async function assignSelf() {
    setActionError("");
    setSaving(true);
    try {
      const me = await apiFetch<{ user: { id: string } }>("/api/auth/me");
      const updated = await apiFetch<EnquiryDetail>(
        `/api/admin/enquiries/${id}`,
        {
          method: "PUT",
          body: JSON.stringify({ assigned_staff_id: me.user.id }),
        },
      );
      setData(updated);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Failed to assign",
      );
    } finally {
      setSaving(false);
    }
  }

  async function submitFeedback() {
    if (!feedback) return;
    setActionError("");
    setSaving(true);
    try {
      const updated = await apiFetch<EnquiryDetail>(
        `/api/admin/enquiries/${id}/feedback`,
        { method: "POST", body: JSON.stringify({ rating: feedback }) },
      );
      setData(updated);
      setFeedback("");
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Failed to record feedback",
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="py-8 text-center text-gray">Loading...</p>;
  }
  if (error || !data) {
    return (
      <p className="py-8 text-center text-danger">{error || "Not found"}</p>
    );
  }

  return (
    <div>
      <button
        onClick={() => router.push("/admin/enquiries")}
        className="mb-4 text-sm text-fnu-blue hover:underline"
      >
        &larr; Back to Enquiries
      </button>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-dark">{data.subject}</h1>
          <p className="text-sm text-gray">
            {data.source} · {new Date(data.opened_at).toLocaleString()}
          </p>
        </div>
        <span className="rounded-full bg-fnu-blue/10 px-3 py-1 text-sm text-fnu-blue">
          {data.status.replace(/_/g, " ")}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border bg-white p-5 lg:col-span-2">
          <h2 className="mb-3 font-bold text-fnu-blue">Message</h2>
          <p className="whitespace-pre-wrap text-sm text-dark">{data.body}</p>
          <p className="mt-4 text-xs text-gray">
            Student: {data.student_identifier || "unknown"}
          </p>
        </section>

        <section className="rounded-lg border bg-white p-5">
          <h2 className="mb-3 font-bold text-fnu-blue">Assignment</h2>
          <p className="mb-3 text-sm">
            {data.assigned_staff_name
              ? `Assigned to ${data.assigned_staff_name}`
              : "Unassigned"}
          </p>
          <button
            onClick={assignSelf}
            disabled={saving}
            className="rounded border px-3 py-2 text-sm hover:bg-surface disabled:opacity-50"
          >
            Assign to me
          </button>
        </section>

        <section className="rounded-lg border bg-white p-5">
          <h2 className="mb-3 font-bold text-fnu-blue">Status</h2>
          <select
            value={newStatus}
            onChange={(e) => setNewStatus(e.target.value)}
            className="input-field"
            aria-label="Status"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </section>

        <section className="rounded-lg border bg-white p-5 lg:col-span-2">
          <h2 className="mb-3 font-bold text-fnu-blue">Resolution note</h2>
          {data.resolution_note ? (
            <p className="rounded bg-surface p-3 text-sm">
              {data.resolution_note}
            </p>
          ) : (
            <textarea
              value={resolutionNote}
              onChange={(e) => setResolutionNote(e.target.value)}
              rows={4}
              placeholder="Describe how the enquiry was resolved (required before marking resolved)"
              className="input-field"
            />
          )}
          {!data.resolution_note && (
            <p className="mt-2 text-xs text-gray">
              Once saved, the resolution note cannot be edited.
            </p>
          )}
        </section>

        {(data.status === "resolved" || data.status === "closed") && (
          <section className="rounded-lg border bg-white p-5 lg:col-span-2">
            <h2 className="mb-3 font-bold text-fnu-blue">Student feedback</h2>
            {data.student_feedback ? (
              <p className="text-sm">
                Rating recorded: {data.student_feedback} / 5
              </p>
            ) : (
              <div className="flex items-center gap-3">
                <select
                  value={feedback}
                  onChange={(e) =>
                    setFeedback(e.target.value ? Number(e.target.value) : "")
                  }
                  className="input-field max-w-[10rem]"
                  aria-label="Rating"
                >
                  <option value="">Rating…</option>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
                <button
                  onClick={submitFeedback}
                  disabled={saving || !feedback}
                  className="rounded bg-fnu-blue px-3 py-2 text-sm text-white disabled:opacity-50"
                >
                  Record feedback
                </button>
              </div>
            )}
          </section>
        )}
      </div>

      {actionError && (
        <p className="mt-4 text-sm text-danger" role="alert">
          {actionError}
        </p>
      )}

      <div className="mt-6 flex justify-end">
        <button
          onClick={saveChanges}
          disabled={saving}
          className="rounded bg-success px-4 py-2 text-sm font-medium text-white hover:bg-success/90 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save changes"}
        </button>
      </div>
    </div>
  );
}
