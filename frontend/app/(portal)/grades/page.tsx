import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";

interface GradeEntry {
  course_code: string;
  course_name: string;
  credits: number;
  grade: string;
  grade_points: number | null;
  semester: string;
  year: number;
}

interface GradesResponse {
  grades: GradeEntry[];
  cumulative_gpa: number;
  semester_gpas: Record<string, number>;
}

const GRADE_COLORS: Record<string, string> = {
  "A+": "text-success",
  A: "text-success",
  "A-": "text-success",
  "B+": "text-fnu-blue",
  B: "text-fnu-blue",
  "B-": "text-fnu-blue",
  "C+": "text-fnu-gold",
  C: "text-fnu-gold",
  "C-": "text-fnu-gold",
  D: "text-danger",
  E: "text-danger",
  F: "text-danger",
};

async function getGrades(token: string): Promise<GradesResponse | null> {
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/grades`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function GradesPage() {
  const session = await getServerSession(authOptions);
  const token = (session?.user as { accessToken?: string })?.accessToken ?? "";
  const data = await getGrades(token);

  if (!data) {
    return (
      <div className="py-8 text-center text-danger">
        Failed to load grades. Please try again.
      </div>
    );
  }

  const bySemester: Record<string, GradeEntry[]> = {};
  for (const g of data.grades) {
    const key = `${g.year}-${g.semester}`;
    bySemester[key] = [...(bySemester[key] ?? []), g];
  }
  const semesterKeys = Object.keys(bySemester).sort().reverse();

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-dark">My Grades</h1>
        <p className="text-sm text-gray">Academic transcript</p>
      </div>

      {/* GPA summary */}
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <div className="rounded-lg border bg-white p-4 text-center shadow-sm">
          <p className="text-sm text-gray">Cumulative GPA</p>
          <p className="mt-1 text-3xl font-bold text-fnu-blue">
            {data.cumulative_gpa.toFixed(2)}
          </p>
          <p className="text-xs text-gray">out of 4.00</p>
        </div>
        {semesterKeys.slice(0, 2).map((key) => (
          <div key={key} className="rounded-lg border bg-white p-4 text-center shadow-sm">
            <p className="text-sm text-gray">{key} GPA</p>
            <p className="mt-1 text-3xl font-bold text-fnu-blue">
              {(data.semester_gpas[key] ?? 0).toFixed(2)}
            </p>
            <p className="text-xs text-gray">{bySemester[key].length} courses</p>
          </div>
        ))}
      </div>

      {data.grades.length === 0 ? (
        <div className="rounded-lg border bg-white p-8 text-center">
          <p className="text-gray">No grades recorded yet.</p>
        </div>
      ) : (
        <div className="space-y-6">
          {semesterKeys.map((key) => (
            <div key={key} className="rounded-lg border bg-white">
              <div className="flex items-center justify-between border-b bg-surface px-4 py-3">
                <h2 className="font-semibold text-dark">{key}</h2>
                <span className="text-sm text-gray">
                  GPA: {(data.semester_gpas[key] ?? 0).toFixed(2)}
                </span>
              </div>
              <table className="w-full text-sm">
                <thead className="border-b">
                  <tr className="text-left text-gray">
                    <th className="px-4 py-2 font-medium">Course</th>
                    <th className="px-4 py-2 font-medium">Name</th>
                    <th className="px-4 py-2 font-medium">Credits</th>
                    <th className="px-4 py-2 font-medium">Grade</th>
                    <th className="px-4 py-2 font-medium">Points</th>
                  </tr>
                </thead>
                <tbody>
                  {bySemester[key].map((g) => (
                    <tr key={g.course_code} className="border-b last:border-0">
                      <td className="px-4 py-2 font-medium text-fnu-blue">
                        {g.course_code}
                      </td>
                      <td className="px-4 py-2 text-dark">{g.course_name}</td>
                      <td className="px-4 py-2 text-gray">{g.credits}</td>
                      <td
                        className={`px-4 py-2 font-bold ${GRADE_COLORS[g.grade] ?? "text-dark"}`}
                      >
                        {g.grade}
                      </td>
                      <td className="px-4 py-2 text-gray">
                        {g.grade_points !== null ? g.grade_points.toFixed(1) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
