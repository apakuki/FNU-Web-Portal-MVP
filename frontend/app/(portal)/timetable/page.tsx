import { getServerSession } from "next-auth/next";
import { authOptions } from "@/lib/auth";

interface TimetableEntry {
  offering_id: string;
  course_code: string;
  course_name: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
  room: string;
  campus: string;
  lecturer_name: string | null;
}

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

const DAY_COLORS: Record<string, string> = {
  Monday: "bg-blue-50 border-blue-200",
  Tuesday: "bg-amber-50 border-amber-200",
  Wednesday: "bg-green-50 border-green-200",
  Thursday: "bg-purple-50 border-purple-200",
  Friday: "bg-rose-50 border-rose-200",
};

async function getTimetable(token: string): Promise<TimetableEntry[]> {
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/timetable`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function TimetablePage() {
  const session = await getServerSession(authOptions);
  const token = (session?.user as { accessToken?: string })?.accessToken ?? "";
  const entries = await getTimetable(token);

  const byDay: Record<string, TimetableEntry[]> = {};
  for (const entry of entries) {
    byDay[entry.day_of_week] = [...(byDay[entry.day_of_week] ?? []), entry];
  }
  for (const day of DAYS) {
    byDay[day]?.sort((a, b) => a.start_time.localeCompare(b.start_time));
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark">My Timetable</h1>
          <p className="text-sm text-gray">Semester 1, 2026</p>
        </div>
        {entries.length > 0 && (
          <a
            href="/api/timetable.ics"
            className="rounded border border-fnu-blue px-4 py-2 text-sm font-medium text-fnu-blue transition hover:bg-fnu-blue hover:text-white"
          >
            Export to Calendar (.ics)
          </a>
        )}
      </div>

      {entries.length === 0 ? (
        <div className="rounded-lg border bg-white p-8 text-center">
          <p className="text-gray">No classes registered yet.</p>
          <a
            href="/register"
            className="mt-3 inline-block text-sm font-medium text-fnu-blue hover:underline"
          >
            Register for courses →
          </a>
        </div>
      ) : (
        <div className="space-y-4">
          {DAYS.map((day) => {
            const dayEntries = byDay[day] ?? [];
            return (
              <div
                key={day}
                className={`rounded-lg border ${DAY_COLORS[day] ?? "bg-white border-gray-200"}`}
              >
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <h2 className="font-semibold text-dark">{day}</h2>
                  {dayEntries.length === 0 && (
                    <span className="text-sm text-gray">No classes</span>
                  )}
                </div>
                {dayEntries.length > 0 && (
                  <div className="divide-y">
                    {dayEntries.map((entry) => (
                      <div
                        key={entry.offering_id}
                        className="flex flex-wrap items-center gap-x-6 gap-y-1 px-4 py-3"
                      >
                        <span className="w-28 font-mono text-sm font-medium text-dark">
                          {entry.start_time}–{entry.end_time}
                        </span>
                        <div className="flex-1">
                          <span className="font-medium text-fnu-blue">
                            {entry.course_code}
                          </span>{" "}
                          <span className="text-dark">{entry.course_name}</span>
                        </div>
                        <div className="text-sm text-gray">
                          {entry.room} · {entry.campus}
                        </div>
                        <div className="text-sm text-gray">
                          {entry.lecturer_name ?? "Lecturer TBA"}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
