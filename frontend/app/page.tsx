import { HealthStatus } from "./health-status";

async function getHealth() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/api/health`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function Home() {
  const health = await getHealth();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <h1 className="mb-2 text-4xl font-bold text-fnu-blue">
        FNU Student Portal
      </h1>
      <p className="mb-8 text-gray">
        Fiji National University Student Services
      </p>
      <HealthStatus health={health} />
    </main>
  );
}
