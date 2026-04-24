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

function statusBadge(course: CourseSummary) {
  if (course.student_count === 0) {
    return { label: "No roster", tone: "bg-gray/10 text-gray" };
  }
  if (course.finalised_count === course.student_count) {
    return { label: "Finalised", tone: "bg-success/10 text-success" };
  }
  if (course.submitted_count > 0) {
    return { label: "Submitted", tone: "bg-warning/10 text-warning" };
  }
  if (course.draft_count > 0) {
    return { label: "Draft", tone: "bg-fnu-blue/10 text-fnu-blue" };
  }
  return { label: "Not started", tone: "bg-gray/10 text-gray" };
}

export default function LecturerCoursesPage() {
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

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-fnu-blue">My Courses</h1>
          <p className="text-sm text-gray">
            {data ? `Semester ${data.semester} ${data.year}` : ""}
          </p>
        </div>
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
              <th className="px-4 py-3 font-medium text-gray">Course</th>
              <th className="px-4 py-3 font-medium text-gray">Schedule</th>
              <th className="px-4 py-3 font-medium text-gray">Campus / Room</th>
              <th className="px-4 py-3 font-medium text-gray">Students</th>
              <th className="px-4 py-3 font-medium text-gray">Grading</th>
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
            ) : courses.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray">
                  You are not assigned to any courses this semester.
                </td>
              </tr>
            ) : (
              courses.map((c) => {
                const badge = statusBadge(c);
                return (
                  <tr key={c.offering_id} className="border-b last:border-0">
                    <td className="px-4 py-3">
                      <div className="font-medium">{c.course_code}</div>
                      <div className="text-xs text-gray">{c.course_name}</div>
                    </td>
                    <td className="px-4 py-3">
                      {c.day_of_week} {c.start_time}–{c.end_time}
                    </td>
                    <td className="px-4 py-3">
                      {c.campus}
                      <div className="text-xs text-gray">{c.room}</div>
                    </td>
                    <td className="px-4 py-3">{c.student_count}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${badge.tone}`}
                      >
                        {badge.label}
                      </span>
                      {c.student_count > 0 && (
                        <div className="mt-1 text-xs text-gray">
                          {c.finalised_count}/{c.student_count} finalised
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/lecturer/courses/${encodeURIComponent(c.offering_id)}`}
                        className="text-fnu-blue hover:underline"
                      >
                        Roster &amp; grades
                      </Link>
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
