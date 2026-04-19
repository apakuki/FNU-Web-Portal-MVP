"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session } = useSession();
  const user = session?.user as any;

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b bg-fnu-blue text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <Link href="/dashboard" className="text-lg font-bold">
            FNU Portal
          </Link>
          <div className="flex items-center gap-4">
            {user && (
              <span className="text-sm">
                {user.name} ({user.role})
              </span>
            )}
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="rounded bg-white/10 px-3 py-1 text-sm transition hover:bg-white/20"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
    </div>
  );
}
