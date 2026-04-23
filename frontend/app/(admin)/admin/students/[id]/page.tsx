"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface StudentProfile {
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  country: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  emergency_contact_relationship: string | null;
}

interface StudentBanner {
  programme_code: string | null;
  campus: string | null;
  enrolment_status: string | null;
  gpa: number | null;
}

interface CompletedCourse {
  course_code: string;
  course_name: string;
  grade: string;
  credits: number;
  semester: string;
  year: number;
}

interface Registration {
  offering_id: string;
  course_code: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
}

interface InvoiceSummary {
  invoice_id: string;
  total_cents: number;
  paid_cents: number;
  balance_cents: number;
  status: string;
}

interface PaymentSummary {
  id: string;
  method: string;
  amount_cents: number;
  status: string;
  created_at: string;
}

interface ApplicationSummary {
  id: string;
  application_number: string;
  status: string;
  submitted_at: string;
  decided_at: string | null;
}

interface OverrideRecord {
  id: number;
  override_type: string;
  reason: string;
  subject: string | null;
  actor_user_id: string | null;
  applied_at: string;
}

interface StudentDetail {
  id: string;
  banner_id: string | null;
  email: string;
  full_name: string;
  phone: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  profile: StudentProfile | null;
  banner: StudentBanner | null;
  completed_courses: CompletedCourse[];
  current_registrations: Registration[];
  invoices: InvoiceSummary[];
  recent_payments: PaymentSummary[];
  applications: ApplicationSummary[];
  overrides: OverrideRecord[];
}

const OVERRIDE_TYPES = [
  { value: "prereq_waiver", label: "Prerequisite Waiver" },
  { value: "late_registration", label: "Late Registration" },
  { value: "overload", label: "Course Overload" },
];

export default function AdminStudentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [data, setData] = useState<StudentDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [overrideType, setOverrideType] = useState("prereq_waiver");
  const [overrideSubject, setOverrideSubject] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideError, setOverrideError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const d = await apiFetch<StudentDetail>(`/api/admin/students/${id}`);
      setData(d);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load student");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function submitOverride() {
    setOverrideError("");
    if (overrideReason.trim().length < 10) {
      setOverrideError("Reason must be at least 10 characters");
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch(`/api/admin/students/${id}/overrides`, {
        method: "POST",
        body: JSON.stringify({
          override_type: overrideType,
          reason: overrideReason,
          subject: overrideSubject || null,
        }),
      });
      setOverrideSubject("");
      setOverrideReason("");
      await load();
    } catch (err) {
      setOverrideError(
        err instanceof ApiError ? err.message : "Failed to apply override",
      );
    } finally {
      setSubmitting(false);
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
        onClick={() => router.push("/admin/students")}
        className="mb-4 text-sm text-fnu-blue hover:underline"
      >
        &larr; Back to Students
      </button>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-dark">{data.full_name}</h1>
          <p className="text-sm text-gray">
            {data.banner_id || "No Banner ID"} · {data.email}
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-sm ${
            data.banner?.enrolment_status === "active" || data.is_active
              ? "bg-success/10 text-success"
              : "bg-gray/10 text-gray"
          }`}
        >
          {data.banner?.enrolment_status || (data.is_active ? "active" : "inactive")}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Personal">
          <Row label="Name" value={data.full_name} />
          <Row label="Email" value={data.email} />
          <Row label="Phone" value={data.phone || "—"} />
          <Row label="Country" value={data.profile?.country || "—"} />
          <Row
            label="Address"
            value={
              [data.profile?.address_line1, data.profile?.address_line2, data.profile?.city]
                .filter(Boolean)
                .join(", ") || "—"
            }
          />
          <Row
            label="Emergency"
            value={
              data.profile?.emergency_contact_name
                ? `${data.profile.emergency_contact_name} (${data.profile.emergency_contact_relationship || "—"}) ${data.profile.emergency_contact_phone || ""}`
                : "—"
            }
          />
        </Section>

        <Section title="Programme">
          <Row label="Programme" value={data.banner?.programme_code || "—"} />
          <Row label="Campus" value={data.banner?.campus || "—"} />
          <Row
            label="GPA"
            value={data.banner?.gpa != null ? data.banner.gpa.toFixed(2) : "—"}
          />
          <Row
            label="Registered"
            value={`${data.current_registrations.length} course(s) this semester`}
          />
        </Section>

        <Section title="Current registrations (2026 S1)">
          {data.current_registrations.length === 0 ? (
            <p className="text-sm text-gray">No active registrations</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {data.current_registrations.map((r) => (
                <li key={r.offering_id}>
                  <span className="font-medium">{r.course_code}</span>{" "}
                  <span className="text-gray">
                    {r.day_of_week} {r.start_time}–{r.end_time}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Completed courses">
          {data.completed_courses.length === 0 ? (
            <p className="text-sm text-gray">None on file</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {data.completed_courses.map((c) => (
                <li key={`${c.course_code}-${c.year}-${c.semester}`}>
                  <span className="font-medium">{c.course_code}</span>{" "}
                  {c.course_name}{" "}
                  <span className="ml-2 rounded bg-surface px-1.5 text-xs">
                    {c.grade}
                  </span>{" "}
                  <span className="text-gray">
                    {c.year} {c.semester}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Invoices">
          {data.invoices.length === 0 ? (
            <p className="text-sm text-gray">No invoices</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {data.invoices.map((inv) => (
                <li key={inv.invoice_id}>
                  <span className="font-medium">{inv.invoice_id}</span>{" "}
                  FJ${(inv.total_cents / 100).toFixed(2)} — {inv.status}{" "}
                  <span className="text-gray">
                    (bal FJ${(inv.balance_cents / 100).toFixed(2)})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Recent payments">
          {data.recent_payments.length === 0 ? (
            <p className="text-sm text-gray">No payments recorded</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {data.recent_payments.map((p) => (
                <li key={p.id}>
                  {new Date(p.created_at).toLocaleDateString()} — {p.method} —
                  FJ${(p.amount_cents / 100).toFixed(2)} —{" "}
                  <span className="text-gray">{p.status}</span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Applications / letters">
          {data.applications.length === 0 ? (
            <p className="text-sm text-gray">No application records</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {data.applications.map((a) => (
                <li key={a.id}>
                  <span className="font-medium">{a.application_number}</span>{" "}
                  — {a.status}{" "}
                  <span className="text-gray">
                    ({new Date(a.submitted_at).toLocaleDateString()})
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Overrides applied">
          {data.overrides.length === 0 ? (
            <p className="text-sm text-gray">None</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.overrides.map((o) => (
                <li key={o.id} className="rounded bg-surface p-2">
                  <p className="font-medium">
                    {o.override_type.replace(/_/g, " ")}
                    {o.subject ? ` · ${o.subject}` : ""}
                  </p>
                  <p className="text-gray">{o.reason}</p>
                  <p className="text-xs text-gray">
                    {new Date(o.applied_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <section className="rounded-lg border bg-white p-5 lg:col-span-2">
          <h2 className="mb-3 font-bold text-fnu-blue">Apply manual override</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <select
              value={overrideType}
              onChange={(e) => setOverrideType(e.target.value)}
              className="input-field"
              aria-label="Override type"
            >
              {OVERRIDE_TYPES.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <input
              value={overrideSubject}
              onChange={(e) => setOverrideSubject(e.target.value)}
              placeholder="Subject (e.g. ACC201) — optional"
              className="input-field"
              aria-label="Override subject"
            />
          </div>
          <textarea
            value={overrideReason}
            onChange={(e) => setOverrideReason(e.target.value)}
            placeholder="Reason (required, min 10 chars)"
            rows={3}
            className="input-field mt-3"
            aria-label="Override reason"
          />
          {overrideError && (
            <p className="mt-2 text-sm text-danger">{overrideError}</p>
          )}
          <button
            onClick={submitOverride}
            disabled={submitting}
            className="mt-3 rounded bg-fnu-blue px-4 py-2 text-sm font-medium text-white hover:bg-fnu-blue/90 disabled:opacity-50"
          >
            {submitting ? "Applying..." : "Apply override"}
          </button>
        </section>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-white p-5">
      <h2 className="mb-3 font-bold text-fnu-blue">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-1 flex text-sm">
      <dt className="w-28 shrink-0 text-gray">{label}</dt>
      <dd className="text-dark">{value}</dd>
    </div>
  );
}
