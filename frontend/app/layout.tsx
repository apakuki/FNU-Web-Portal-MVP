import type { Metadata } from "next";
import { SessionProvider } from "@/lib/session-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "FNU Student Portal",
  description: "Fiji National University Student Services Portal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-surface text-dark antialiased">
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
