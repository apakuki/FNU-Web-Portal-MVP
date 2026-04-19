"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";

const WIDGETS = [
  {
    title: "Course Registration",
    description: "Register for upcoming semester courses",
    href: "/register",
    color: "border-l-fnu-blue",
  },
  {
    title: "My Timetable",
    description: "View your class schedule",
    href: "/timetable",
    color: "border-l-fnu-gold",
  },
  {
    title: "My Courses",
    description: "View enrolled courses and materials",
    href: "/courses",
    color: "border-l-success",
  },
  {
    title: "My Grades",
    description: "Check grades and GPA",
    href: "/grades",
    color: "border-l-fnu-blue",
  },
  {
    title: "Make a Payment",
    description: "Pay tuition and fees online",
    href: "/pay",
    color: "border-l-fnu-gold",
  },
  {
    title: "Student ID",
    description: "Access your digital student ID card",
    href: "/id-card",
    color: "border-l-success",
  },
];

export default function DashboardPage() {
  const { data: session } = useSession();
  const user = session?.user as any;

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold text-fnu-blue">Dashboard</h1>
      {user && (
        <p className="mb-6 text-gray">
          Welcome back, {user.name}.
        </p>
      )}

      <section aria-label="Quick actions">
        <h2 className="mb-4 text-lg font-semibold text-dark">Quick Actions</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {WIDGETS.map((w) => (
            <Link
              key={w.href}
              href={w.href}
              className={`block rounded-lg border border-l-4 ${w.color} bg-white p-5 shadow-sm transition hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-fnu-blue`}
            >
              <h3 className="font-medium text-dark">{w.title}</h3>
              <p className="mt-1 text-sm text-gray">{w.description}</p>
            </Link>
          ))}
        </div>
      </section>

      <section aria-label="Announcements" className="mt-8">
        <h2 className="mb-4 text-lg font-semibold text-dark">Announcements</h2>
        <div className="rounded-lg border bg-white p-5 shadow-sm">
          <p className="text-sm text-gray">No announcements at this time.</p>
        </div>
      </section>
    </div>
  );
}
