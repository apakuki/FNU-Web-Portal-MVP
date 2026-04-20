"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface Document {
  id: string;
  filename: string;
  document_type: string;
  size_bytes: number;
}

interface ApplicationDetail {
  id: string;
  application_number: string;
  applicant_email: string;
  applicant_phone: string | null;
  payload: {
    personal_details?: {
      first_name?: string;
      last_name?: string;
      date_of_birth?: string;
      gender?: string;
      nationality?: string;
      address?: string;
    };
    prior_qualifications?: Array<{
      institution: string;
      qualification: string;
      year_completed: number;
      grade: string;
    }>;
    programme_preference?: string;
    campus_preference?: string;
  };
  status: string;
  status_reason: string | null;
  is_conditional: boolean;
  submitted_at: string;
  decided_at: string | null;
  documents: Document[];
}

const STATUS_ACTIONS = [
  { value: "under_review", label: "Mark Under Review", requiresReason: false },
  {
    value: "awaiting_documents",
    label: "Request Documents",
    requiresReason: true,
  },
  { value: "approved", label: "Approve", requiresReason: false },
  {
    value: "conditionally_approved",
    label: "Approve (Conditional)",
    requiresReason: false,
  },
  { value: "rejected", label: "Reject", requiresReason: true },
];

export default function ApplicationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [app, setApp] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [selectedAction, setSelectedAction] = useState("");
  const [reason, setReason] = useState("");
  const [isConditional, setIsConditional] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [updateError, setUpdateError] = useState("");

  const fetchApplication = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<ApplicationDetail>(
        `/api/admin/applications/${id}`,
      );
      setApp(data);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to load application");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchApplication();
  }, [fetchApplication]);

  async function handleStatusUpdate() {
    if (!selectedAction) return;
    setUpdateError("");
    setUpdating(true);

    try {
      const data = await apiFetch<ApplicationDetail>(
        `/api/admin/applications/${id}/status`,
        {
          method: "PUT",
          body: JSON.stringify({
            status: selectedAction,
            reason: reason || null,
            is_conditional:
              selectedAction === "conditionally_approved" || isConditional,
          }),
        },
      );
      setApp(data);
      setSelectedAction("");
      setReason("");
    } catch (err) {
      if (err instanceof ApiError) setUpdateError(err.message);
      else setUpdateError("Failed to update status");
    } finally {
      setUpdating(false);
    }
  }

  if (loading) {
    return <p className="py-8 text-center text-gray">Loading...</p>;
  }

  if (error || !app) {
    return (
      <p className="py-8 text-center text-danger">{error || "Not found"}</p>
    );
  }

  const pd = app.payload.personal_details;

  return (
    <div>
      <button
        onClick={() => router.push("/admin/applications")}
        className="mb-4 text-sm text-fnu-blue hover:underline"
      >
        &larr; Back to Applications
      </button>

      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark">
            {app.application_number}
          </h1>
          <p className="text-sm text-gray">
            Submitted {new Date(app.submitted_at).toLocaleString()}
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-sm font-medium ${
            app.status === "approved" || app.status === "conditionally_approved"
              ? "bg-success/10 text-success"
              : app.status === "rejected"
                ? "bg-danger/10 text-danger"
                : "bg-fnu-blue/10 text-fnu-blue"
          }`}
        >
          {app.status.replace(/_/g, " ")}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Applicant Details */}
        <section className="rounded-lg border bg-white p-5">
          <h2 className="mb-3 font-bold text-fnu-blue">Applicant</h2>
          <dl className="space-y-2 text-sm">
            <DetailRow label="Name" value={pd ? `${pd.first_name} ${pd.last_name}` : "—"} />
            <DetailRow label="Email" value={app.applicant_email} />
            <DetailRow label="Phone" value={app.applicant_phone || "—"} />
            <DetailRow label="DOB" value={pd?.date_of_birth || "—"} />
            <DetailRow label="Gender" value={pd?.gender || "—"} />
            <DetailRow label="Nationality" value={pd?.nationality || "—"} />
            <DetailRow label="Address" value={pd?.address || "—"} />
          </dl>
        </section>

        {/* Programme */}
        <section className="rounded-lg border bg-white p-5">
          <h2 className="mb-3 font-bold text-fnu-blue">Programme</h2>
          <dl className="space-y-2 text-sm">
            <DetailRow
              label="Programme"
              value={app.payload.programme_preference || "—"}
            />
            <DetailRow
              label="Campus"
              value={app.payload.campus_preference || "—"}
            />
            <DetailRow
              label="Conditional"
              value={app.is_conditional ? "Yes" : "No"}
            />
          </dl>

          <h3 className="mb-2 mt-4 font-medium text-dark">Qualifications</h3>
          {app.payload.prior_qualifications?.map((q, i) => (
            <div key={i} className="mb-2 rounded bg-surface p-2 text-sm">
              {q.qualification} — {q.institution} ({q.year_completed})
              {q.grade && `, Grade: ${q.grade}`}
            </div>
          )) || <p className="text-sm text-gray">None provided</p>}
        </section>

        {/* Documents */}
        <section className="rounded-lg border bg-white p-5">
          <h2 className="mb-3 font-bold text-fnu-blue">Documents</h2>
          {app.documents.length > 0 ? (
            <ul className="space-y-2">
              {app.documents.map((doc) => (
                <li
                  key={doc.id}
                  className="flex items-center justify-between rounded bg-surface px-3 py-2 text-sm"
                >
                  <span>
                    {doc.filename}{" "}
                    <span className="text-gray">
                      ({doc.document_type},{" "}
                      {(doc.size_bytes / 1024).toFixed(0)} KB)
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray">No documents uploaded</p>
          )}
        </section>

        {/* Actions */}
        <section className="rounded-lg border bg-white p-5">
          <h2 className="mb-3 font-bold text-fnu-blue">Actions</h2>

          {app.status_reason && (
            <div className="mb-3 rounded bg-surface p-3 text-sm">
              <span className="font-medium">Previous reason:</span>{" "}
              {app.status_reason}
            </div>
          )}

          <div className="space-y-3">
            <select
              value={selectedAction}
              onChange={(e) => setSelectedAction(e.target.value)}
              className="input-field"
            >
              <option value="">Select action...</option>
              {STATUS_ACTIONS.map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>

            {selectedAction && (
              <>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder={
                    STATUS_ACTIONS.find((a) => a.value === selectedAction)
                      ?.requiresReason
                      ? "Reason (required)"
                      : "Reason (optional)"
                  }
                  className="input-field"
                  rows={3}
                />

                {updateError && (
                  <p className="text-sm text-danger">{updateError}</p>
                )}

                <button
                  onClick={handleStatusUpdate}
                  disabled={updating}
                  className={`w-full rounded px-4 py-2 text-sm font-medium text-white ${
                    selectedAction === "rejected"
                      ? "bg-danger hover:bg-danger/90"
                      : "bg-success hover:bg-success/90"
                  } disabled:opacity-50`}
                >
                  {updating ? "Updating..." : "Confirm"}
                </button>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex">
      <dt className="w-24 text-gray">{label}</dt>
      <dd className="text-dark">{value}</dd>
    </div>
  );
}
