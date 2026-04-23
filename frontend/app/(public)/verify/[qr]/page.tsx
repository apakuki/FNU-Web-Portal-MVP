import { notFound } from "next/navigation";

type VerifyResponse = {
  valid: boolean;
  full_name: string | null;
  banner_id: string | null;
  programme: string | null;
  photo_url: string | null;
  expires_at: string | null;
  reason: string | null;
};

async function verify(qr: string): Promise<VerifyResponse | null> {
  const apiUrl = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(
      `${apiUrl}/api/verify/${encodeURIComponent(qr)}`,
      { cache: "no-store" },
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export const dynamic = "force-dynamic";

export default async function VerifyPage({
  params,
}: {
  params: Promise<{ qr: string }>;
}) {
  const { qr } = await params;
  const data = await verify(qr);
  if (!data) notFound();

  return (
    <main className="mx-auto max-w-md px-4 py-10">
      <header className="rounded-t bg-fnu-blue p-4 text-white">
        <p className="text-xs uppercase tracking-wide opacity-80">
          Fiji National University
        </p>
        <p className="text-lg font-semibold">ID Verification</p>
      </header>

      {data.valid ? (
        <section
          className="rounded-b bg-white p-6 ring-1 ring-success/40"
          aria-live="polite"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded bg-success/10 px-3 py-1 text-sm font-medium text-success">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true">
              <path d="M5 13l4 4L19 7" />
            </svg>
            Valid student
          </div>
          <div className="flex items-start gap-4">
            {data.photo_url && (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src={data.photo_url}
                alt={`Photo of ${data.full_name ?? "student"}`}
                className="h-24 w-24 rounded object-cover ring-1 ring-dark/10"
              />
            )}
            <dl className="text-sm">
              <dt className="text-dark/60">Name</dt>
              <dd className="font-semibold text-dark">{data.full_name ?? "—"}</dd>

              <dt className="mt-2 text-dark/60">Banner ID</dt>
              <dd className="font-mono text-dark">{data.banner_id ?? "—"}</dd>

              {data.programme && (
                <>
                  <dt className="mt-2 text-dark/60">Programme</dt>
                  <dd className="text-dark">{data.programme}</dd>
                </>
              )}

              {data.expires_at && (
                <>
                  <dt className="mt-2 text-dark/60">Valid until</dt>
                  <dd className="text-dark">
                    {new Date(data.expires_at).toLocaleDateString("en-FJ", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </dd>
                </>
              )}
            </dl>
          </div>
          <p className="mt-4 text-xs text-dark/60">
            This verification only confirms enrolment and identity. It does not
            expose grades, contact details, or financial information.
          </p>
        </section>
      ) : (
        <section
          className="rounded-b bg-white p-6 ring-1 ring-danger/40"
          aria-live="polite"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded bg-danger/10 px-3 py-1 text-sm font-medium text-danger">
            Invalid
          </div>
          <p className="text-sm text-dark">
            {data.reason ?? "This ID card could not be verified."}
          </p>
        </section>
      )}
    </main>
  );
}
