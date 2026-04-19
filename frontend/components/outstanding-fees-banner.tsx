"use client";

export function OutstandingFeesBanner({
  balanceCents,
}: {
  balanceCents: number | null;
}) {
  if (!balanceCents || balanceCents <= 0) return null;

  const formatted = new Intl.NumberFormat("en-FJ", {
    style: "currency",
    currency: "FJD",
  }).format(balanceCents / 100);

  return (
    <div
      className="rounded border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-dark"
      role="alert"
    >
      <span className="font-medium">Outstanding fees:</span> You have{" "}
      {formatted} in unpaid fees.{" "}
      <a href="/pay" className="font-medium text-fnu-blue underline">
        Make a payment
      </a>
    </div>
  );
}
