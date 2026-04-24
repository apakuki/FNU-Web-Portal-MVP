"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          padding: "3rem 1.5rem",
          color: "#0A1F33",
          maxWidth: "40rem",
          margin: "0 auto",
        }}
      >
        <h1 style={{ fontSize: "1.5rem", color: "#003A70" }}>
          The portal is temporarily unavailable
        </h1>
        <p style={{ marginTop: "0.75rem", color: "#6B7280" }}>
          A system error occurred. Please refresh the page or try again in a
          few minutes. If the problem persists, contact FNU Student Services.
        </p>
        {error.digest ? (
          <p style={{ marginTop: "0.5rem", fontSize: "0.75rem", color: "#6B7280" }}>
            Reference: {error.digest}
          </p>
        ) : null}
        <button
          type="button"
          onClick={reset}
          style={{
            marginTop: "1.5rem",
            background: "#003A70",
            color: "white",
            padding: "0.5rem 1rem",
            border: "none",
            borderRadius: "0.25rem",
            cursor: "pointer",
          }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
