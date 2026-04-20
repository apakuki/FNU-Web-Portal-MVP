import Link from "next/link";
import { ApplicationForm } from "./application-form";

export const metadata = {
  title: "Apply — FNU Student Portal",
  description: "Apply to Fiji National University",
};

export default function ApplyPage() {
  return (
    <main className="min-h-screen bg-surface">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4">
          <h1 className="text-xl font-bold text-fnu-blue">
            FNU — New Student Application
          </h1>
          <Link
            href="/"
            className="text-sm text-fnu-blue underline hover:no-underline"
          >
            Back to Home
          </Link>
        </div>
      </header>
      <div className="mx-auto max-w-3xl px-4 py-8">
        <ApplicationForm />
      </div>
    </main>
  );
}
