import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";

interface RegisteredCourse {
  offering_id: string;
  course_code: string;
  course_name: string;
  credits: number;
  day_of_week: string;
  start_time: string;
  end_time: string;
  room: string;
  campus: string;
  lecturer_name: string | null;
}

async function getMyCourses(token: string): Promise<RegisteredCourse[]> {
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/my-courses`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function CoursesPage() {
  const session = await getServerSession(authOptions);
  const token = (session?.user as { accessToken?: string })?.accessToken ?? "";
  const courses = await getMyCourses(token);

  const totalCredits = courses.reduce((sum, c) => sum + c.credits, 0);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-dark">My Courses</h1>
        <p className="text-sm text-gray">
          Semester 1, 2026
          {courses.length > 0 && ` · ${courses.length} courses · ${totalCredits} credits`}
        </p>
      </div>

      {courses.length === 0 ? (
        <div className="rounded-lg border bg-white p-8 text-center">
          <p className="text-gray">No courses registered yet.</p>
          <a
            href="/register"
            className="mt-3 inline-block text-sm font-medium text-fnu-blue hover:underline"
          >
            Register for courses →
          </a>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {courses.map((course) => (
            <div
              key={course.offering_id}
              className="rounded-lg border bg-white p-5 shadow-sm"
            >
              <div className="mb-3 flex items-start justify-between">
                <div>
                  <h2 className="font-bold text-fnu-blue">{course.course_code}</h2>
                  <p className="text-sm font-medium text-dark">{course.course_name}</p>
                </div>
                <span className="rounded bg-fnu-blue/10 px-2 py-1 text-xs font-medium text-fnu-blue">
                  {course.credits} credits
                </span>
              </div>

              <dl className="space-y-1 text-sm">
                <div className="flex gap-2">
                  <dt className="w-20 text-gray">Schedule</dt>
                  <dd className="text-dark">
                    {course.day_of_week}, {course.start_time}–{course.end_time}
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-20 text-gray">Room</dt>
                  <dd className="text-dark">
                    {course.room} · {course.campus}
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-20 text-gray">Lecturer</dt>
                  <dd className="text-dark">{course.lecturer_name ?? "TBA"}</dd>
                </div>
              </dl>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
