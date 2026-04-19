"use client";

import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { useState } from "react";

import { OutstandingFeesBanner } from "@/components/outstanding-fees-banner";
import { PortalNav } from "@/components/portal-nav";

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { data: session } = useSession();
  const user = session?.user as any;
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b bg-fnu-blue text-white">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="min-h-[44px] min-w-[44px] rounded p-2 transition hover:bg-white/10 lg:hidden"
              aria-label={sidebarOpen ? "Close menu" : "Open menu"}
              aria-expanded={sidebarOpen}
            >
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                {sidebarOpen ? (
                  <path d="M6 6l12 12M6 18L18 6" />
                ) : (
                  <path d="M3 6h18M3 12h18M3 18h18" />
                )}
              </svg>
            </button>
            <Link href="/dashboard" className="text-lg font-bold">
              FNU Portal
            </Link>
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <span className="hidden text-sm sm:inline">
                {user.name}{" "}
                <span className="rounded bg-white/10 px-1.5 py-0.5 text-xs">
                  {user.role}
                </span>
              </span>
            )}
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="min-h-[44px] rounded bg-white/10 px-3 py-2 text-sm transition hover:bg-white/20"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <div className="flex">
        {sidebarOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/30 lg:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}

        <aside
          className={`fixed left-0 top-[57px] z-40 h-[calc(100vh-57px)] w-64 overflow-y-auto border-r bg-white p-4 transition-transform lg:static lg:z-auto lg:translate-x-0 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <PortalNav onNavigate={() => setSidebarOpen(false)} />
        </aside>

        <main className="min-h-[calc(100vh-57px)] flex-1 px-4 py-6 lg:px-8">
          <div className="mx-auto max-w-5xl">
            <OutstandingFeesBanner balanceCents={null} />
            <div className="mt-4">{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
