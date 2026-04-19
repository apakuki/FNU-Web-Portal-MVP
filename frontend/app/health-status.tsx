"use client";

interface HealthData {
  status: string;
  postgres: string;
  banner: string;
}

export function HealthStatus({ health }: { health: HealthData | null }) {
  if (!health) {
    return (
      <div className="rounded-lg border border-danger/20 bg-danger/5 px-6 py-4 text-danger">
        Backend unavailable
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-success/20 bg-success/5 px-6 py-4">
      <div className="grid grid-cols-3 gap-4 text-sm">
        <div>
          <span className="text-gray">API</span>
          <p className="font-medium text-success">{health.status}</p>
        </div>
        <div>
          <span className="text-gray">Postgres</span>
          <p className="font-medium text-success">{health.postgres}</p>
        </div>
        <div>
          <span className="text-gray">Banner</span>
          <p className="font-medium text-fnu-blue">{health.banner}</p>
        </div>
      </div>
    </div>
  );
}
