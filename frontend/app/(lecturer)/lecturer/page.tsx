"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api-client";

interface CourseSummary {
  offering_id: string;
  course_code: string;
  course_name: string;
  semester: string;
  year: number;
  campus: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
  room: string;
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

export default function LecturerDashboardPage() {
  const [data, setData] = useState<RostersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<RostersResponse>("/api/lecturer/rosters")
      .then(setData)
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Failed to load rosters");
      })
      .finally(() => setLoading(false));
  }, []);

  const courses = data?.courses ?? [];
  const totalStudents = courses.reduce((n, c) => n + c.student_count, 0);
  const pendingOfferings = courses.filter(
    (c) =>
      c.student_count > 0 &&
      c.draft_count + c.submitted_count > 0 &&
      c.finalised_count < c.student_count,
  ).length;

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-fnu-blue">
        Lecturer Dashboard
      </h1>
      <p className="mb-6 text-sm text-gray">
        {data ? `Semester ${data.semester} ${data.year}` : ""}
      </p>

      {error && (
        <p className="mb-4 text-sm text-danger" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <p className="text-sm text-gray">My Courses</p>
          <p className="mt-1 text-2xl font-bold text-dark">
            {loading ? "…" : courses.length}
          </p>
        </div>
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <p className="text-sm text-gray">Students Taught</p>
          <p className="mt-1 text-2xl font-bold text-dark">
            {loading ? "…" : totalStudents}
          </p>
        </div>
        <div className="rounded-lg border bg-white p-6 shadow-sm">
          <p className="text-sm text-gray">Grading in Progress</p>
          <p className="mt-1 text-2xl font-bold text-dark">
            {loading ? "…" : pendingOfferings}
          </p>
        </div>
      </div>

      <div className="mt-8 rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-bold text-dark">Quick actions</h2>
        <ul className="space-y-2 text-sm">
          <li>
            <Link
              href="/lecturer/courses"
              className="text-fnu-blue hover:underline"
            >
              View my courses &amp; rosters →
            </Link>
          </li>
          <li>
            <Link
              href="/lecturer/grades"
              className="text-fnu-blue hover:underline"
            >
              Enter grades →
            </Link>
          </li>
        </ul>
      </div>
    </div>
  );
}
