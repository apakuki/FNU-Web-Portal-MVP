"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const STUDENT_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/register", label: "Register" },
  { href: "/timetable", label: "Timetable" },
  { href: "/courses", label: "My Courses" },
  { href: "/grades", label: "My Grades" },
  { href: "/invoices", label: "Invoices" },
  { href: "/pay", label: "Make a Payment" },
  { href: "/id-card", label: "Student ID" },
  { href: "/profile", label: "Profile" },
];

export function PortalNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav aria-label="Portal navigation">
      <ul className="space-y-1">
        {STUDENT_LINKS.map((link) => {
          const active = pathname === link.href;
          return (
            <li key={link.href}>
              <Link
                href={link.href}
                onClick={onNavigate}
                className={`block min-h-[44px] rounded px-3 py-2.5 text-sm font-medium transition ${
                  active
                    ? "bg-fnu-blue text-white"
                    : "text-dark hover:bg-fnu-blue/5"
                }`}
                aria-current={active ? "page" : undefined}
              >
                {link.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
