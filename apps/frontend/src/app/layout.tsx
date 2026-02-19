import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "MCC Frontend",
  description: "Frontend UI for MCC pilot"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
