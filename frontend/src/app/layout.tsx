import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "doyoularp // Resume Evidence Verification",
  description: "Brutal, evidence-backed sanity checks on resumes. Stalking GitHub, verifying receipts, exposing resume fiction.",
  icons: {
    icon: "/larp.jpg",
    shortcut: "/larp.jpg",
    apple: "/larp.jpg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-zinc-100 antialiased selection:bg-red-600 selection:text-white">
        {children}
      </body>
    </html>
  );
}
