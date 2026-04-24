"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";

const VIEWS = [
  {
    href: "/admin/kpi/vc",
    title: "VC / SLT",
    description:
      "Institution-wide enrolment, processing, service, and finance KPIs.",
    roles: ["vc", "admin"],
  },
  {
    href: "/admin/kpi/dean",
    title: "Dean / Manager",
    description: "College performance — applications, service, academic.",
    roles: ["manager", "vc", "admin"],
  },
  {
    href: "/admin/kpi/section-head",
    title: "Section Head",
    description:
      "Team workload and manual KPI entry (training hours, satisfaction).",
    roles: ["manager", "admin"],
  },
  {
    href: "/admin/kpi/finance",
    title: "Finance",
    description:
      "Revenue collected, confirmed payments, outstanding receivables, CSV export.",
    roles: ["finance", "admin"],
  },
  {
    href: "/admin/kpi/me",
    title: "My KPIs",
    description: "Your individual performance for the period.",
    roles: ["staff", "manager", "finance", "lecturer", "vc", "admin"],
  },
  {
    href: "/admin/kpi/targets",
    title: "KPI Targets",
    description: "Configure KPI targets. Admin only.",
    roles: ["admin"],
  },
];

export default function KpiHubPage() {
  const { data: session } = useSession();
  const role = (session?.user as any)?.role as string | undefined;

  const visible = VIEWS.filter((v) => (role ? v.roles.includes(role) : false));

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-dark">KPI Dashboards</h1>
      <p className="mb-4 text-sm text-gray">
        Pick a view appropriate for your role. Access is enforced on the
        backend; unauthorised views will return 403.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        {visible.map((v) => (
          <Link
            key={v.href}
            href={v.href}
            className="rounded-lg border bg-white p-5 shadow-sm transition hover:border-fnu-blue"
          >
            <p className="text-lg font-semibold text-dark">{v.title}</p>
            <p className="mt-1 text-sm text-gray">{v.description}</p>
          </Link>
        ))}
        {visible.length === 0 && (
          <p className="text-sm text-gray">
            No dashboards available for your role.
          </p>
        )}
      </div>
    </div>
  );
}
