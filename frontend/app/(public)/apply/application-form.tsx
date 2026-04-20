"use client";

import Link from "next/link";
import { FormEvent, useCallback, useState } from "react";
import { z } from "zod";

const personalDetailsSchema = z.object({
  first_name: z.string().min(1, "First name is required").max(100),
  last_name: z.string().min(1, "Last name is required").max(100),
  date_of_birth: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/, "Use format YYYY-MM-DD"),
  gender: z.string().min(1, "Gender is required"),
  nationality: z.string().min(1, "Nationality is required").max(60),
  address: z.string().min(1, "Address is required").max(500),
});

const qualificationSchema = z.object({
  institution: z.string().min(1, "Institution is required"),
  qualification: z.string().min(1, "Qualification is required"),
  year_completed: z.coerce
    .number()
    .min(1950, "Year must be after 1950")
    .max(2030),
  grade: z.string().max(20),
});

const applicationSchema = z.object({
  applicant_email: z.string().email("Valid email required"),
  applicant_phone: z.string().max(20).optional(),
  personal_details: personalDetailsSchema,
  prior_qualifications: z
    .array(qualificationSchema)
    .min(1, "At least one qualification required"),
  programme_preference: z.string().min(1, "Programme is required"),
  campus_preference: z.string().min(1, "Campus is required"),
});

type ApplicationData = z.infer<typeof applicationSchema>;

const PROGRAMMES = [
  { code: "BCOM", name: "Bachelor of Commerce" },
  { code: "BSCI", name: "Bachelor of Science" },
  { code: "BNUR", name: "Bachelor of Nursing" },
  { code: "DIT", name: "Diploma in Information Technology" },
  { code: "CEDU", name: "Certificate in Education" },
];

const CAMPUSES = ["Nasinu", "Lautoka", "Labasa", "Nausori", "Ba", "Suva"];
const GENDERS = ["Male", "Female", "Other", "Prefer not to say"];

const STEPS = ["Contact", "Personal", "Qualifications", "Programme", "Review"];

export function ApplicationForm() {
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<{
    application_number: string;
  } | null>(null);

  const [data, setData] = useState({
    applicant_email: "",
    applicant_phone: "",
    first_name: "",
    last_name: "",
    date_of_birth: "",
    gender: "",
    nationality: "Fijian",
    address: "",
    qualifications: [
      { institution: "", qualification: "", year_completed: "", grade: "" },
    ],
    programme_preference: "",
    campus_preference: "",
  });

  function updateField(field: string, value: string) {
    setData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }

  function updateQualification(
    index: number,
    field: string,
    value: string,
  ) {
    setData((prev) => {
      const quals = [...prev.qualifications];
      quals[index] = { ...quals[index], [field]: value };
      return { ...prev, qualifications: quals };
    });
  }

  function addQualification() {
    setData((prev) => ({
      ...prev,
      qualifications: [
        ...prev.qualifications,
        { institution: "", qualification: "", year_completed: "", grade: "" },
      ],
    }));
  }

  function removeQualification(index: number) {
    if (data.qualifications.length <= 1) return;
    setData((prev) => ({
      ...prev,
      qualifications: prev.qualifications.filter((_, i) => i !== index),
    }));
  }

  function validateStep(): boolean {
    const newErrors: Record<string, string> = {};

    if (step === 0) {
      if (!data.applicant_email) newErrors.applicant_email = "Email is required";
      else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.applicant_email))
        newErrors.applicant_email = "Invalid email";
    }

    if (step === 1) {
      if (!data.first_name) newErrors.first_name = "First name is required";
      if (!data.last_name) newErrors.last_name = "Last name is required";
      if (!data.date_of_birth)
        newErrors.date_of_birth = "Date of birth is required";
      else if (!/^\d{4}-\d{2}-\d{2}$/.test(data.date_of_birth))
        newErrors.date_of_birth = "Use format YYYY-MM-DD";
      if (!data.gender) newErrors.gender = "Gender is required";
      if (!data.address) newErrors.address = "Address is required";
    }

    if (step === 2) {
      data.qualifications.forEach((q, i) => {
        if (!q.institution)
          newErrors[`qual_${i}_institution`] = "Institution is required";
        if (!q.qualification)
          newErrors[`qual_${i}_qualification`] = "Qualification is required";
        if (!q.year_completed)
          newErrors[`qual_${i}_year`] = "Year is required";
      });
    }

    if (step === 3) {
      if (!data.programme_preference)
        newErrors.programme_preference = "Programme is required";
      if (!data.campus_preference)
        newErrors.campus_preference = "Campus is required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }

  function nextStep() {
    if (validateStep()) setStep((s) => Math.min(s + 1, STEPS.length - 1));
  }

  function prevStep() {
    setStep((s) => Math.max(s - 1, 0));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError("");

    const payload: ApplicationData = {
      applicant_email: data.applicant_email,
      applicant_phone: data.applicant_phone || undefined,
      personal_details: {
        first_name: data.first_name,
        last_name: data.last_name,
        date_of_birth: data.date_of_birth,
        gender: data.gender,
        nationality: data.nationality,
        address: data.address,
      },
      prior_qualifications: data.qualifications.map((q) => ({
        institution: q.institution,
        qualification: q.qualification,
        year_completed: parseInt(q.year_completed) || 0,
        grade: q.grade,
      })),
      programme_preference: data.programme_preference,
      campus_preference: data.campus_preference,
    };

    const result = applicationSchema.safeParse(payload);
    if (!result.success) {
      setSubmitError("Please fix the validation errors and try again.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch("/api/applications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Submission failed");
      }
      const responseData = await res.json();
      setSuccess({
        application_number: responseData.application_number,
      });
    } catch (err: any) {
      setSubmitError(err.message || "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="rounded-lg border bg-white p-8 text-center">
        <div className="mb-4 text-4xl">&#10003;</div>
        <h2 className="mb-2 text-2xl font-bold text-success">
          Application Submitted
        </h2>
        <p className="mb-4 text-gray">
          Your application number is{" "}
          <strong className="text-dark">{success.application_number}</strong>
        </p>
        <p className="text-sm text-gray">
          A confirmation email has been sent to {data.applicant_email}. You
          will be notified when your application is reviewed.
        </p>
        <Link
          href="/"
          className="mt-6 inline-block rounded bg-fnu-blue px-6 py-2 text-white hover:bg-fnu-blue/90"
        >
          Return Home
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      {/* Step indicators */}
      <div className="mb-8 flex items-center justify-between">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                i <= step
                  ? "bg-fnu-blue text-white"
                  : "bg-gray/20 text-gray"
              }`}
            >
              {i + 1}
            </div>
            <span
              className={`ml-2 hidden text-sm sm:inline ${
                i <= step ? "text-dark font-medium" : "text-gray"
              }`}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <div className="mx-2 h-px w-8 bg-gray/30 sm:w-12" />
            )}
          </div>
        ))}
      </div>

      <div className="rounded-lg border bg-white p-6">
        {/* Step 0: Contact */}
        {step === 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-fnu-blue">
              Contact Information
            </h2>
            <FieldGroup
              label="Email Address"
              required
              error={errors.applicant_email}
            >
              <input
                type="email"
                value={data.applicant_email}
                onChange={(e) => updateField("applicant_email", e.target.value)}
                className="input-field"
                autoComplete="email"
              />
            </FieldGroup>
            <FieldGroup label="Phone Number">
              <input
                type="tel"
                value={data.applicant_phone}
                onChange={(e) =>
                  updateField("applicant_phone", e.target.value)
                }
                className="input-field"
                placeholder="+679 ..."
              />
            </FieldGroup>
          </div>
        )}

        {/* Step 1: Personal Details */}
        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-fnu-blue">
              Personal Details
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <FieldGroup
                label="First Name"
                required
                error={errors.first_name}
              >
                <input
                  type="text"
                  value={data.first_name}
                  onChange={(e) => updateField("first_name", e.target.value)}
                  className="input-field"
                />
              </FieldGroup>
              <FieldGroup
                label="Last Name"
                required
                error={errors.last_name}
              >
                <input
                  type="text"
                  value={data.last_name}
                  onChange={(e) => updateField("last_name", e.target.value)}
                  className="input-field"
                />
              </FieldGroup>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <FieldGroup
                label="Date of Birth"
                required
                error={errors.date_of_birth}
              >
                <input
                  type="date"
                  value={data.date_of_birth}
                  onChange={(e) =>
                    updateField("date_of_birth", e.target.value)
                  }
                  className="input-field"
                />
              </FieldGroup>
              <FieldGroup label="Gender" required error={errors.gender}>
                <select
                  value={data.gender}
                  onChange={(e) => updateField("gender", e.target.value)}
                  className="input-field"
                >
                  <option value="">Select...</option>
                  {GENDERS.map((g) => (
                    <option key={g} value={g.toLowerCase()}>
                      {g}
                    </option>
                  ))}
                </select>
              </FieldGroup>
            </div>
            <FieldGroup label="Nationality" required>
              <input
                type="text"
                value={data.nationality}
                onChange={(e) => updateField("nationality", e.target.value)}
                className="input-field"
              />
            </FieldGroup>
            <FieldGroup label="Address" required error={errors.address}>
              <textarea
                value={data.address}
                onChange={(e) => updateField("address", e.target.value)}
                className="input-field"
                rows={2}
              />
            </FieldGroup>
          </div>
        )}

        {/* Step 2: Qualifications */}
        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-fnu-blue">
              Prior Qualifications
            </h2>
            {data.qualifications.map((q, i) => (
              <div
                key={i}
                className="rounded border bg-surface p-4"
              >
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-sm font-medium text-dark">
                    Qualification {i + 1}
                  </span>
                  {data.qualifications.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeQualification(i)}
                      className="text-sm text-danger hover:underline"
                    >
                      Remove
                    </button>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <FieldGroup
                    label="Institution"
                    required
                    error={errors[`qual_${i}_institution`]}
                  >
                    <input
                      type="text"
                      value={q.institution}
                      onChange={(e) =>
                        updateQualification(i, "institution", e.target.value)
                      }
                      className="input-field"
                    />
                  </FieldGroup>
                  <FieldGroup
                    label="Qualification"
                    required
                    error={errors[`qual_${i}_qualification`]}
                  >
                    <input
                      type="text"
                      value={q.qualification}
                      onChange={(e) =>
                        updateQualification(
                          i,
                          "qualification",
                          e.target.value,
                        )
                      }
                      className="input-field"
                    />
                  </FieldGroup>
                  <FieldGroup
                    label="Year Completed"
                    required
                    error={errors[`qual_${i}_year`]}
                  >
                    <input
                      type="number"
                      value={q.year_completed}
                      onChange={(e) =>
                        updateQualification(
                          i,
                          "year_completed",
                          e.target.value,
                        )
                      }
                      className="input-field"
                      min={1950}
                      max={2030}
                    />
                  </FieldGroup>
                  <FieldGroup label="Grade">
                    <input
                      type="text"
                      value={q.grade}
                      onChange={(e) =>
                        updateQualification(i, "grade", e.target.value)
                      }
                      className="input-field"
                    />
                  </FieldGroup>
                </div>
              </div>
            ))}
            <button
              type="button"
              onClick={addQualification}
              className="text-sm font-medium text-fnu-blue hover:underline"
            >
              + Add another qualification
            </button>
          </div>
        )}

        {/* Step 3: Programme */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-fnu-blue">
              Programme Selection
            </h2>
            <FieldGroup
              label="Programme"
              required
              error={errors.programme_preference}
            >
              <select
                value={data.programme_preference}
                onChange={(e) =>
                  updateField("programme_preference", e.target.value)
                }
                className="input-field"
              >
                <option value="">Select a programme...</option>
                {PROGRAMMES.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.name} ({p.code})
                  </option>
                ))}
              </select>
            </FieldGroup>
            <FieldGroup
              label="Preferred Campus"
              required
              error={errors.campus_preference}
            >
              <select
                value={data.campus_preference}
                onChange={(e) =>
                  updateField("campus_preference", e.target.value)
                }
                className="input-field"
              >
                <option value="">Select a campus...</option>
                {CAMPUSES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </FieldGroup>
          </div>
        )}

        {/* Step 4: Review */}
        {step === 4 && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-fnu-blue">
              Review Your Application
            </h2>

            <ReviewSection title="Contact">
              <ReviewItem label="Email" value={data.applicant_email} />
              <ReviewItem
                label="Phone"
                value={data.applicant_phone || "—"}
              />
            </ReviewSection>

            <ReviewSection title="Personal Details">
              <ReviewItem
                label="Name"
                value={`${data.first_name} ${data.last_name}`}
              />
              <ReviewItem label="DOB" value={data.date_of_birth} />
              <ReviewItem label="Gender" value={data.gender} />
              <ReviewItem label="Nationality" value={data.nationality} />
              <ReviewItem label="Address" value={data.address} />
            </ReviewSection>

            <ReviewSection title="Qualifications">
              {data.qualifications.map((q, i) => (
                <div key={i} className="text-sm">
                  {q.qualification} from {q.institution} ({q.year_completed})
                  {q.grade && ` — Grade: ${q.grade}`}
                </div>
              ))}
            </ReviewSection>

            <ReviewSection title="Programme">
              <ReviewItem
                label="Programme"
                value={
                  PROGRAMMES.find(
                    (p) => p.code === data.programme_preference,
                  )?.name || data.programme_preference
                }
              />
              <ReviewItem label="Campus" value={data.campus_preference} />
            </ReviewSection>

            {submitError && (
              <p className="text-sm text-danger" role="alert">
                {submitError}
              </p>
            )}
          </div>
        )}

        {/* Navigation */}
        <div className="mt-6 flex justify-between">
          {step > 0 ? (
            <button
              type="button"
              onClick={prevStep}
              className="rounded border border-gray/30 px-6 py-2 text-sm font-medium text-dark hover:bg-surface"
            >
              Back
            </button>
          ) : (
            <div />
          )}

          {step < STEPS.length - 1 ? (
            <button
              type="button"
              onClick={nextStep}
              className="rounded bg-fnu-blue px-6 py-2 text-sm font-medium text-white hover:bg-fnu-blue/90"
            >
              Next
            </button>
          ) : (
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-success px-6 py-2 text-sm font-medium text-white hover:bg-success/90 disabled:opacity-50"
            >
              {submitting ? "Submitting..." : "Submit Application"}
            </button>
          )}
        </div>
      </div>
    </form>
  );
}

function FieldGroup({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-dark">
        {label}
        {required && <span className="text-danger"> *</span>}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}

function ReviewSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded border bg-surface p-4">
      <h3 className="mb-2 text-sm font-bold text-fnu-blue">{title}</h3>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function ReviewItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex text-sm">
      <span className="w-28 text-gray">{label}:</span>
      <span className="text-dark">{value}</span>
    </div>
  );
}
