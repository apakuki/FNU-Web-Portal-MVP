import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-lg px-6 py-16 text-center">
      <h1 className="text-2xl font-semibold text-primary">Page not found</h1>
      <p className="mt-3 text-sm text-gray-600">
        The page you are looking for does not exist or has moved.
      </p>
      <Link
        href="/"
        className="mt-6 inline-block rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        Go to home
      </Link>
    </div>
  );
}
