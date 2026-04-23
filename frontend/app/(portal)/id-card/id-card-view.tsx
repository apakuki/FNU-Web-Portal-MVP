"use client";

import { useEffect, useState } from "react";

import { apiFetch } from "@/lib/api-client";

type IdCard = {
  user_id: string;
  banner_id: string;
  full_name: string;
  qr_payload: string;
  expires_at: string;
  verify_url: string;
  has_photo: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export function IdCardView() {
  const [card, setCard] = useState<IdCard | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<IdCard>("/api/id-card")
      .then(setCard)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!card) return;
    let cancelled = false;
    import("qrcode")
      .then((QRCode) =>
        QRCode.toDataURL(card.verify_url, { margin: 1, width: 240 }),
      )
      .then((url) => {
        if (!cancelled) setQrDataUrl(url);
      })
      .catch(() => {
        if (!cancelled) setError("Failed to render QR code");
      });
    return () => {
      cancelled = true;
    };
  }, [card]);

  if (error)
    return (
      <p role="alert" className="text-sm text-danger">
        {error}
      </p>
    );
  if (!card) return <p className="text-sm text-dark/60">Loading ID card…</p>;

  const expiryDate = new Date(card.expires_at).toLocaleDateString("en-FJ", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <article
      className="mx-auto max-w-md overflow-hidden rounded-xl shadow-lg ring-1 ring-dark/10"
      aria-label="Student ID card"
    >
      <header className="bg-fnu-blue p-4 text-white">
        <p className="text-xs uppercase tracking-wide opacity-80">
          Fiji National University
        </p>
        <p className="text-lg font-semibold">Student ID</p>
      </header>
      <div className="flex gap-4 bg-white p-4">
        <div className="h-28 w-28 shrink-0 overflow-hidden rounded bg-surface ring-1 ring-dark/10">
          {card.has_photo ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={`${API_BASE}/api/profile/photo/me`}
              alt={`Photo of ${card.full_name}`}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-dark/50">
              No photo
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-lg font-semibold text-dark">
            {card.full_name}
          </p>
          <p className="mt-1 text-xs text-dark/60">Banner ID</p>
          <p className="font-mono text-sm text-dark">{card.banner_id}</p>
          <p className="mt-2 text-xs text-dark/60">Valid until</p>
          <p className="text-sm text-dark">{expiryDate}</p>
        </div>
      </div>
      <div className="flex flex-col items-center gap-2 bg-surface/50 p-4">
        {qrDataUrl ? (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={qrDataUrl}
            alt="Scan to verify"
            className="h-60 w-60"
            width={240}
            height={240}
          />
        ) : (
          <div className="flex h-60 w-60 items-center justify-center text-xs text-dark/50">
            Rendering QR…
          </div>
        )}
        <p className="text-center text-xs text-dark/60">
          Scan to verify at {card.verify_url.replace(/^https?:\/\//, "")}
        </p>
      </div>
    </article>
  );
}
