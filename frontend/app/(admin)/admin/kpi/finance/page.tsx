"use client";

import { KpiDashboard } from "@/components/kpi-dashboard";

export default function FinanceDashboardPage() {
  return (
    <KpiDashboard
      view="finance"
      title="Finance Dashboard"
      subtitle="Revenue, confirmed payments, and outstanding receivables."
      allowExport
    />
  );
}
