"use client";

import { useEffect } from "react";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Route error:", error);
  }, [error]);

  return (
    <div className="mx-auto max-w-lg px-6 py-16">
      <h1 className="text-2xl font-semibold text-primary">
        Something went wrong
      </h1>
      <p className="mt-3 text-sm text-gray-600">
        We couldn&apos;t load this page. Please try again, or contact FNU
        Student Services if the problem persists.
      </p>
      {error.digest ? (
        <p className="mt-2 text-xs text-gray-500">Reference: {error.digest}</p>
      ) : null}
      <button
        type="button"
        onClick={reset}
        className="mt-6 rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}
