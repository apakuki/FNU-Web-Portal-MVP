"use client";

import { useSession } from "next-auth/react";

export default function DashboardPage() {
  const { data: session } = useSession();
  const user = session?.user as any;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-fnu-blue">Dashboard</h1>
      {user && (
        <p className="mb-4 text-gray">
          Welcome, {user.name}. You are logged in as {user.role}.
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[
          "My Account",
          "My Timetable",
          "My Courses",
          "My Grades",
          "Profile",
          "Make a Payment",
        ].map((title) => (
          <div
            key={title}
            className="rounded-lg border bg-white p-6 shadow-sm"
          >
            <h2 className="font-medium text-dark">{title}</h2>
            <p className="mt-1 text-sm text-gray">Coming soon</p>
          </div>
        ))}
      </div>
    </div>
  );
}
