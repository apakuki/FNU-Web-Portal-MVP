"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";

interface OfferingOut {
  id: string;
  course_code: string;
  course_name: string;
  credits: number;
  day_of_week: string;
  start_time: string;
  end_time: string;
  room: string;
  campus: string;
  lecturer_name: string | null;
  capacity: number;
  enrolled: number;
  available: boolean;
  prereqs_met: boolean;
  prereq_issues: string[];
}

interface ProgrammeResponse {
  code: string;
  name: string;
  level: string;
  college: string;
  total_credits: number;
  completed_credits: number;
  courses: OfferingOut[];
}

interface ClashInfo {
  offering_id_1: string;
  offering_id_2: string;
  course_1: string;
  course_2: string;
  day: string;
  overlap: string;
}

interface ConfirmResponse {
  success: boolean;
  registered_courses: string[];
  invoice_id: string | null;
  total_fee_cents: number;
  clashes: ClashInfo[];
  message: string;
}

export default function RegisterPage() {
  const [programme, setProgramme] = useState<ProgrammeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [clashes, setClashes] = useState<ClashInfo[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [result, setResult] = useState<ConfirmResponse | null>(null);

  const fetchProgramme = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<ProgrammeResponse>("/api/programme");
      setProgramme(data);
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Failed to load programme data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProgramme();
  }, [fetchProgramme]);

  function toggleOffering(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setClashes([]);
  }

  function detectClientClashes(): ClashInfo[] {
    if (!programme) return [];
    const selectedOfferings = programme.courses.filter((c) => selected.has(c.id));
    const found: ClashInfo[] = [];
    for (let i = 0; i < selectedOfferings.length; i++) {
      for (let j = i + 1; j < selectedOfferings.length; j++) {
        const a = selectedOfferings[i];
        const b = selectedOfferings[j];
        if (a.day_of_week !== b.day_of_week) continue;
        const aStart = timeToMin(a.start_time);
        const aEnd = timeToMin(a.end_time);
        const bStart = timeToMin(b.start_time);
        const bEnd = timeToMin(b.end_time);
        if (aStart < bEnd && bStart < aEnd) {
          found.push({
            offering_id_1: a.id,
            offering_id_2: b.id,
            course_1: a.course_code,
            course_2: b.course_code,
            day: a.day_of_week,
            overlap: `${a.day_of_week} overlap`,
          });
        }
      }
    }
    return found;
  }

  async function handleConfirm() {
    const clientClashes = detectClientClashes();
    if (clientClashes.length > 0) {
      setClashes(clientClashes);
      return;
    }

    setConfirming(true);
    setError("");
    try {
      const data = await apiFetch<ConfirmResponse>(
        "/api/registration/confirm",
        {
          method: "POST",
          body: JSON.stringify({
            offering_ids: Array.from(selected),
            semester: "S1",
            year: 2026,
          }),
        },
      );
      if (data.clashes && data.clashes.length > 0) {
        setClashes(data.clashes);
      } else {
        setResult(data);
      }
    } catch (err) {
      if (err instanceof ApiError) setError(err.message);
      else setError("Registration failed");
    } finally {
      setConfirming(false);
    }
  }

  const selectedOfferings = programme?.courses.filter((c) => selected.has(c.id)) ?? [];
  const totalCredits = selectedOfferings.reduce((sum, c) => sum + c.credits, 0);

  if (result?.success) {
    return (
      <div className="mx-auto max-w-2xl py-8 text-center">
        <div className="rounded-lg border border-success/30 bg-success/5 p-8">
          <h1 className="mb-4 text-2xl font-bold text-success">
            Registration Confirmed
          </h1>
          <p className="mb-2 text-dark">
            You have been registered for {result.registered_courses.length} courses:
          </p>
          <ul className="mb-4 space-y-1">
            {result.registered_courses.map((code) => (
              <li key={code} className="font-medium">{code}</li>
            ))}
          </ul>
          {result.invoice_id && (
            <p className="text-sm text-gray">
              Invoice {result.invoice_id} created — Total: FJ$
              {(result.total_fee_cents / 100).toFixed(2)}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (loading) {
    return <p className="py-8 text-center text-gray">Loading programme data...</p>;
  }

  if (error && !programme) {
    return <p className="py-8 text-center text-danger">{error}</p>;
  }

  if (!programme) {
    return <p className="py-8 text-center text-gray">No programme found</p>;
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-dark">Course Registration</h1>
        <p className="text-sm text-gray">
          {programme.name} ({programme.code}) — {programme.completed_credits}/
          {programme.total_credits} credits completed
        </p>
      </div>

      {error && (
        <div className="mb-4 rounded border border-danger/30 bg-danger/5 p-3 text-sm text-danger">
          {error}
        </div>
      )}

      {clashes.length > 0 && (
        <div className="mb-4 rounded border border-danger/30 bg-danger/5 p-3">
          <p className="mb-1 font-medium text-danger">Timetable Clashes Detected</p>
          {clashes.map((clash, i) => (
            <p key={i} className="text-sm text-danger">
              {clash.course_1} and {clash.course_2} clash on {clash.day}
            </p>
          ))}
        </div>
      )}

      <div className="mb-6 overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b bg-surface">
            <tr>
              <th className="px-4 py-3 font-medium text-gray">Select</th>
              <th className="px-4 py-3 font-medium text-gray">Course</th>
              <th className="px-4 py-3 font-medium text-gray">Day / Time</th>
              <th className="px-4 py-3 font-medium text-gray">Room</th>
              <th className="px-4 py-3 font-medium text-gray">Lecturer</th>
              <th className="px-4 py-3 font-medium text-gray">Seats</th>
              <th className="px-4 py-3 font-medium text-gray">Status</th>
            </tr>
          </thead>
          <tbody>
            {programme.courses.map((offering) => {
              const blocked = !offering.prereqs_met || !offering.available;
              return (
                <tr
                  key={offering.id}
                  className={`border-b last:border-0 ${blocked ? "opacity-60" : ""}`}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={selected.has(offering.id)}
                      onChange={() => toggleOffering(offering.id)}
                      disabled={blocked}
                      className="h-4 w-4"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium">{offering.course_code}</span>
                    <br />
                    <span className="text-gray">{offering.course_name}</span>
                    <br />
                    <span className="text-xs text-gray">
                      {offering.credits} credits
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {offering.day_of_week}
                    <br />
                    {offering.start_time} - {offering.end_time}
                  </td>
                  <td className="px-4 py-3">{offering.room}</td>
                  <td className="px-4 py-3">
                    {offering.lecturer_name || "TBA"}
                  </td>
                  <td className="px-4 py-3">
                    {offering.enrolled}/{offering.capacity}
                  </td>
                  <td className="px-4 py-3">
                    {!offering.prereqs_met ? (
                      <span className="text-xs text-danger">
                        Prereqs not met
                        {offering.prereq_issues.map((issue, i) => (
                          <span key={i} className="block">{issue}</span>
                        ))}
                      </span>
                    ) : !offering.available ? (
                      <span className="text-xs text-danger">Full</span>
                    ) : (
                      <span className="text-xs text-success">Available</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selected.size > 0 && (
        <div className="rounded-lg border bg-white p-5">
          <h2 className="mb-3 font-bold text-fnu-blue">
            Selected Courses ({selected.size})
          </h2>
          <ul className="mb-3 space-y-1 text-sm">
            {selectedOfferings.map((o) => (
              <li key={o.id}>
                {o.course_code} — {o.course_name} ({o.day_of_week}{" "}
                {o.start_time}-{o.end_time})
              </li>
            ))}
          </ul>
          <p className="mb-4 text-sm text-gray">
            Total credits: {totalCredits}
          </p>
          <button
            onClick={handleConfirm}
            disabled={confirming}
            className="rounded bg-fnu-blue px-6 py-2 text-sm font-medium text-white hover:bg-fnu-blue/90 disabled:opacity-50"
          >
            {confirming ? "Registering..." : "Confirm Registration"}
          </button>
        </div>
      )}
    </div>
  );
}

function timeToMin(t: string): number {
  const [h, m] = t.split(":");
  return parseInt(h) * 60 + parseInt(m);
}
