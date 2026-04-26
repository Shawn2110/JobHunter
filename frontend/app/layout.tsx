import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "JobHunt",
  description: "Single-user, self-hosted, AI-augmented job hunt.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
