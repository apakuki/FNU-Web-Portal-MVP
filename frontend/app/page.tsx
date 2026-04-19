import Link from "next/link";
import { HealthStatus } from "./health-status";

async function getHealth() {
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function Home() {
  const health = await getHealth();

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <span className="text-xl font-bold text-fnu-blue">
            Fiji National University
          </span>
          <nav className="flex items-center gap-4">
            <Link
              href="/apply"
              className="text-sm font-medium text-dark hover:text-fnu-blue"
            >
              Apply
            </Link>
            <Link
              href="/login"
              className="rounded bg-fnu-blue px-4 py-2 text-sm font-medium text-white transition hover:bg-fnu-blue/90"
            >
              Sign In
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="bg-fnu-blue py-20 text-white">
          <div className="mx-auto max-w-6xl px-4 text-center">
            <h1 className="mb-4 text-4xl font-bold sm:text-5xl">
              Student Services Portal
            </h1>
            <p className="mx-auto mb-8 max-w-2xl text-lg text-white/80">
              Apply for admission, register for courses, manage your fees, view
              your timetable and grades — all in one place.
            </p>
            <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/apply"
                className="min-h-[44px] min-w-[44px] rounded bg-fnu-gold px-6 py-3 font-medium text-dark transition hover:bg-fnu-gold/90"
              >
                Apply Now
              </Link>
              <Link
                href="/login"
                className="min-h-[44px] min-w-[44px] rounded border border-white/30 px-6 py-3 font-medium text-white transition hover:bg-white/10"
              >
                Current Students
              </Link>
            </div>
          </div>
        </section>

        <section className="py-16">
          <div className="mx-auto max-w-6xl px-4">
            <h2 className="mb-8 text-center text-2xl font-bold text-dark">
              What You Can Do
            </h2>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {[
                {
                  title: "Online Application",
                  description:
                    "Submit your application, upload documents, and track your status online.",
                },
                {
                  title: "Course Registration",
                  description:
                    "Browse programmes, select courses, and register with prerequisite and clash checking.",
                },
                {
                  title: "Fee Payments",
                  description:
                    "Pay fees via M-PAiSA, MyCash, or bank transfer. Set up instalment plans.",
                },
                {
                  title: "Timetable and Grades",
                  description:
                    "View your class schedule, export to calendar, and check your grades and GPA.",
                },
                {
                  title: "AI Assistant",
                  description:
                    "Get instant answers about admissions, fees, deadlines, and more.",
                },
                {
                  title: "Digital Student ID",
                  description:
                    "Access your digital student ID card with QR verification.",
                },
              ].map((item) => (
                <div
                  key={item.title}
                  className="rounded-lg border bg-white p-6 shadow-sm"
                >
                  <h3 className="mb-2 font-semibold text-fnu-blue">
                    {item.title}
                  </h3>
                  <p className="text-sm text-gray">{item.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t bg-white py-8">
          <div className="mx-auto max-w-6xl px-4">
            <h2 className="mb-4 text-center text-lg font-semibold text-dark">
              System Status
            </h2>
            <div className="flex justify-center">
              <HealthStatus health={health} />
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t bg-dark py-6 text-sm text-white/60">
        <div className="mx-auto max-w-6xl px-4 text-center">
          Fiji National University Student Services Portal
        </div>
      </footer>
    </div>
  );
}
