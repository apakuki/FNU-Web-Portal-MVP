"use client";

import { KpiDashboard } from "@/components/kpi-dashboard";

export default function VcDashboardPage() {
  return (
    <KpiDashboard
      view="vc"
      title="VC / SLT Dashboard"
      subtitle="Institution-wide performance at a glance."
      allowRecompute
    />
  );
}
