"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api-client";

interface RosterEntry {
  banner_student_id: string;
  student_name: string;
  email: string;
  attendance_pct: number | null;
  grade: string | null;
  status: string;
  submitted_at: string | null;
  finalised_at: string | null;
  updated_at: string | null;
}

interface RosterDetail {
  offering_id: string;
  course_code: string;
  course_name: string;
  semester: string;
  year: number;
  campus: string;
  lecturer_name: string | null;
  room: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
  entries: RosterEntry[];
}

const GRADE_OPTIONS = [
  "",
  "A+", "A", "A-",
  "B+", "B", "B-",
  "C+", "C", "C-",
  "D", "E", "F", "WD",
];

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function LecturerOfferingPage() {
  const params = useParams<{ offeringId: string }>();
  const offeringId = decodeURIComponent(params.offeringId ?? "");

  const [detail, setDetail] = useState<RosterDetail | null>(null);
  const [grades, setGrades] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">(
    "idle",
  );
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState("");

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<Record<string, string>>({});

  const load = useCallback(async () => {
    if (!offeringId) return;
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch<RosterDetail>(
        `/api/lecturer/rosters/${encodeURIComponent(offeringId)}`,
      );
      setDetail(data);
      const next: Record<string, string> = {};
      for (const e of data.entries) {
        next[e.banner_student_id] = e.grade ?? "";
      }
      setGrades(next);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to load roster",
      );
    } finally {
      setLoading(false);
    }
  }, [offeringId]);

  useEffect(() => {
    load();
  }, [load]);

  const flushSave = useCallback(async () => {
    const bucket = pending.current;
    pending.current = {};
    const entries = Object.entries(bucket).map(
      ([banner_student_id, grade]) => ({
        banner_student_id,
        grade: grade || null,
      }),
    );
    if (entries.length === 0) return;
    setSaveState("saving");
    try {
      await apiFetch<{ saved: number }>("/api/lecturer/grades", {
        method: "POST",
        body: JSON.stringify({
          offering_id: offeringId,
          assessment_period: "final",
          entries,
        }),
      });
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 1200);
    } catch (err) {
      setSaveState("error");
      setError(
        err instanceof ApiError ? err.message : "Autosave failed",
      );
    }
  }, [offeringId]);

  const scheduleSave = useCallback(() => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      flushSave();
    }, 700);
  }, [flushSave]);

  const handleGradeChange = (bid: string, value: string) => {
    setGrades((prev) => ({ ...prev, [bid]: value }));
    pending.current[bid] = value;
    scheduleSave();
  };

  const anyEditable = useMemo(
    () => detail?.entries.some((e) => e.status === "draft") ?? false,
    [detail],
  );
  const anySubmitted = useMemo(
    () => detail?.entries.some((e) => e.status === "submitted") ?? false,
    [detail],
  );

  const allGradesPresent = useMemo(() => {
    if (!detail) return false;
    return detail.entries.every(
      (e) => (grades[e.banner_student_id] ?? e.grade ?? "").trim() !== "",
    );
  }, [detail, grades]);

  const handleSubmit = async () => {
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
    }
    await flushSave();
    setBusy(true);
    setError("");
    setFlash("");
    try {
      const res = await apiFetch<{ affected: number; message: string }>(
        `/api/lecturer/grades/${encodeURIComponent(offeringId)}/submit`,
        { method: "POST" },
      );
      setFlash(res.message);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Submit failed");
    } finally {
      setBusy(false);
    }
  };

  const handleFinalise = async () => {
    if (
      !window.confirm(
        "Finalising writes these grades to Banner and locks them. Continue?",
      )
    ) {
      return;
    }
    setBusy(true);
    setError("");
    setFlash("");
    try {
      const res = await apiFetch<{ affected: number; message: string }>(
        `/api/lecturer/grades/${encodeURIComponent(offeringId)}/finalise`,
        { method: "POST" },
      );
      setFlash(res.message);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Finalise failed");
    } finally {
      setBusy(false);
    }
  };

  const handleExport = async (format: "csv" | "xlsx" | "pdf") => {
    setError("");
    try {
      const session = (await import("next-auth/react")).getSession;
      const s = await session();
      const token = (s?.user as { accessToken?: string } | undefined)
        ?.accessToken;
      const res = await fetch(
        `/api/lecturer/rosters/${encodeURIComponent(offeringId)}/export?format=${format}`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        },
      );
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `Export failed (${res.status})`);
      }
      const blob = await res.blob();
      const ext = format === "xlsx" ? "csv" : format;
      download(
        blob,
        `roster_${detail?.course_code ?? offeringId}.${ext}`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  };

  if (loading) {
    return <p className="py-12 text-center text-gray">Loading roster...</p>;
  }

  if (!detail) {
    return (
      <div>
        <p className="mb-4 text-sm text-danger" role="alert">
          {error || "Roster not available"}
        </p>
        <Link href="/lecturer/courses" className="text-sm text-fnu-blue hover:underline">
          ← Back to my courses
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <Link
          href="/lecturer/courses"
          className="text-sm text-fnu-blue hover:underline"
        >
          ← Back to my courses
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-fnu-blue">
          {detail.course_code} — {detail.course_name}
        </h1>
        <p className="text-sm text-gray">
          {detail.semester} {detail.year} · {detail.campus} · {detail.day_of_week}{" "}
          {detail.start_time}–{detail.end_time} · Room {detail.room}
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-gray">
          {detail.entries.length} student{detail.entries.length === 1 ? "" : "s"} ·{" "}
          {saveState === "saving"
            ? "Saving…"
            : saveState === "saved"
              ? "Saved"
              : saveState === "error"
                ? "Save error"
                : "Autosave enabled"}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => handleExport("csv")}
            className="rounded border border-gray/30 bg-white px-3 py-2 text-xs hover:bg-surface"
          >
            Export CSV
          </button>
          <button
            type="button"
            onClick={() => handleExport("xlsx")}
            className="rounded border border-gray/30 bg-white px-3 py-2 text-xs hover:bg-surface"
          >
            Export Excel
          </button>
          <button
            type="button"
            onClick={() => handleExport("pdf")}
            className="rounded border border-gray/30 bg-white px-3 py-2 text-xs hover:bg-surface"
          >
            Export PDF
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={busy || !anyEditable || !allGradesPresent}
            className="rounded bg-fnu-blue px-3 py-2 text-xs font-medium text-white hover:bg-fnu-blue/90 disabled:opacity-50"
          >
            Submit for review
          </button>
          <button
            type="button"
            onClick={handleFinalise}
            disabled={busy || !anySubmitted}
            className="rounded bg-success px-3 py-2 text-xs font-medium text-white hover:bg-success/90 disabled:opacity-50"
          >
            Finalise &amp; write to Banner
          </button>
        </div>
      </div>

      {flash && (
        <p
          className="mb-4 rounded border border-success/30 bg-success/5 p-3 text-sm text-success"
          role="status"
        >
          {flash}
        </p>
      )}
      {error && (
        <p className="mb-4 text-sm text-danger" role="alert">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b bg-surface">
            <tr>
              <th className="px-4 py-3 font-medium text-gray">Banner ID</th>
              <th className="px-4 py-3 font-medium text-gray">Student</th>
              <th className="px-4 py-3 font-medium text-gray">Email</th>
              <th className="px-4 py-3 font-medium text-gray">Attendance</th>
              <th className="px-4 py-3 font-medium text-gray">Grade</th>
              <th className="px-4 py-3 font-medium text-gray">Status</th>
            </tr>
          </thead>
          <tbody>
            {detail.entries.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray">
                  No students enrolled in this offering
                </td>
              </tr>
            ) : (
              detail.entries.map((e) => {
                const locked = e.status !== "draft";
                return (
                  <tr
                    key={e.banner_student_id}
                    className="border-b last:border-0"
                  >
                    <td className="px-4 py-3 font-mono text-xs">
                      {e.banner_student_id}
                    </td>
                    <td className="px-4 py-3 font-medium">{e.student_name}</td>
                    <td className="px-4 py-3">{e.email}</td>
                    <td className="px-4 py-3">
                      {e.attendance_pct === null
                        ? "—"
                        : `${e.attendance_pct.toFixed(1)}%`}
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={grades[e.banner_student_id] ?? e.grade ?? ""}
                        onChange={(ev) =>
                          handleGradeChange(e.banner_student_id, ev.target.value)
                        }
                        disabled={locked || busy}
                        className="input-field py-1"
                        aria-label={`Grade for ${e.student_name}`}
                      >
                        {GRADE_OPTIONS.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt || "—"}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          e.status === "finalised"
                            ? "bg-success/10 text-success"
                            : e.status === "submitted"
                              ? "bg-warning/10 text-warning"
                              : "bg-gray/10 text-gray"
                        }`}
                      >
                        {e.status}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
