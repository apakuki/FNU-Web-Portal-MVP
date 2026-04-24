"use client";

import { KpiDashboard } from "@/components/kpi-dashboard";

export default function MyKpisPage() {
  return (
    <KpiDashboard
      view="me"
      title="My KPIs"
      subtitle="Your individual performance for the selected period."
    />
  );
}
