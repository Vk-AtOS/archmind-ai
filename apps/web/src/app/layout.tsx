import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ArchMind",
  description: "Plot and brief to a checked house design with a build cost.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
