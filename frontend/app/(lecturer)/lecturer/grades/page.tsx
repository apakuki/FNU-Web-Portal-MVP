"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api-client";

interface CourseSummary {
  offering_id: string;
  course_code: string;
  course_name: string;
  student_count: number;
  draft_count: number;
  submitted_count: number;
  finalised_count: number;
}

interface RostersResponse {
  semester: string;
  year: number;
  courses: CourseSummary[];
}

export default function LecturerGradesPage() {
  const [data, setData] = useState<RostersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<RostersResponse>("/api/lecturer/rosters")
      .then(setData)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load courses");
      })
      .finally(() => setLoading(false));
  }, []);

  const courses = data?.courses ?? [];

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-fnu-blue">Enter Grades</h1>
      <p className="mb-6 text-sm text-gray">
        {data
          ? `Semester ${data.semester} ${data.year} — pick a course to enter or review grades`
          : ""}
      </p>

      {error && (
        <p className="mb-4 text-sm text-danger" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          <p className="text-sm text-gray">Loading…</p>
        ) : courses.length === 0 ? (
          <p className="text-sm text-gray">
            You are not assigned to any courses this semester.
          </p>
        ) : (
          courses.map((c) => {
            const remaining = c.student_count - c.finalised_count;
            return (
              <Link
                key={c.offering_id}
                href={`/lecturer/courses/${encodeURIComponent(c.offering_id)}`}
                className="block rounded-lg border bg-white p-5 shadow-sm transition hover:border-fnu-blue"
              >
                <div className="text-xs font-medium text-gray">
                  {c.course_code}
                </div>
                <div className="mt-1 text-lg font-bold text-dark">
                  {c.course_name}
                </div>
                <div className="mt-3 text-sm text-gray">
                  {c.student_count} student{c.student_count === 1 ? "" : "s"} ·{" "}
                  {c.finalised_count}/{c.student_count} finalised
                </div>
                <div className="mt-1 text-xs text-gray">
                  {remaining > 0
                    ? `${remaining} grade${remaining === 1 ? "" : "s"} outstanding`
                    : "All grades finalised"}
                </div>
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}
