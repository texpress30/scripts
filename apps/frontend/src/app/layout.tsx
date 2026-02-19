import "./globals.css";
import type { Metadata } from "next";

import { ThemeProvider } from "@/components/ThemeProvider";

export const metadata: Metadata = {
  title: "MCC Frontend",
  description: "Frontend UI for MCC pilot"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem disableTransitionOnChange>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
