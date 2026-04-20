"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

interface OfferDetail {
  programme: string;
  campus: string;
  applicant_name: string;
  is_conditional: boolean;
  conditions: string | null;
  issued_at: string;
  accepted_at: string | null;
  declined_at: string | null;
}

export default function OfferPage() {
  const params = useParams();
  const token = params.token as string;

  const [offer, setOffer] = useState<OfferDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionResult, setActionResult] = useState<string | null>(null);
  const [acting, setActing] = useState(false);

  const fetchOffer = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/offers/${token}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Offer not found");
      }
      setOffer(await res.json());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchOffer();
  }, [fetchOffer]);

  async function handleAction(action: "accept" | "decline") {
    setActing(true);
    try {
      const res = await fetch(`/api/offers/${token}/${action}`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Action failed");
      }
      const data = await res.json();
      setActionResult(data.detail);
      await fetchOffer();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActing(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface">
        <p className="text-gray">Loading offer...</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-surface p-4">
        <div className="w-full max-w-md rounded-lg border bg-white p-8 text-center">
          <h1 className="mb-4 text-xl font-bold text-danger">Offer Error</h1>
          <p className="text-gray">{error}</p>
          <Link
            href="/"
            className="mt-4 inline-block text-sm text-fnu-blue hover:underline"
          >
            Return Home
          </Link>
        </div>
      </main>
    );
  }

  if (!offer) return null;

  const alreadyResponded = offer.accepted_at || offer.declined_at;

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface p-4">
      <div className="w-full max-w-lg rounded-lg border bg-white p-8">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-fnu-blue">
            Fiji National University
          </h1>
          <p className="text-sm text-gray">Offer of Admission</p>
        </div>

        <div className="mb-6 space-y-3">
          <p className="text-dark">
            Dear <strong>{offer.applicant_name}</strong>,
          </p>
          <p className="text-dark">
            We are pleased to offer you admission to the{" "}
            <strong>{offer.programme}</strong> programme at our{" "}
            <strong>{offer.campus}</strong> campus.
          </p>
          {offer.is_conditional && offer.conditions && (
            <div className="rounded bg-warning/10 p-3">
              <p className="text-sm font-medium text-dark">
                Conditional Offer
              </p>
              <p className="text-sm text-gray">{offer.conditions}</p>
            </div>
          )}
          <p className="text-xs text-gray">
            Issued on{" "}
            {new Date(offer.issued_at).toLocaleDateString("en-FJ", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>

        {actionResult && (
          <div className="mb-4 rounded bg-success/10 p-3 text-center">
            <p className="font-medium text-success">{actionResult}</p>
            {actionResult.includes("accepted") && (
              <Link
                href="/login"
                className="mt-2 inline-block rounded bg-fnu-blue px-4 py-2 text-sm text-white hover:bg-fnu-blue/90"
              >
                Sign In to Your Account
              </Link>
            )}
          </div>
        )}

        {alreadyResponded && !actionResult && (
          <div className="rounded bg-surface p-3 text-center text-sm text-gray">
            {offer.accepted_at
              ? "This offer has been accepted."
              : "This offer has been declined."}
          </div>
        )}

        {!alreadyResponded && !actionResult && (
          <div className="flex gap-3">
            <button
              onClick={() => handleAction("accept")}
              disabled={acting}
              className="flex-1 rounded bg-success py-3 font-medium text-white hover:bg-success/90 disabled:opacity-50"
            >
              {acting ? "Processing..." : "Accept Offer"}
            </button>
            <button
              onClick={() => handleAction("decline")}
              disabled={acting}
              className="flex-1 rounded border border-danger py-3 font-medium text-danger hover:bg-danger/5 disabled:opacity-50"
            >
              Decline
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
