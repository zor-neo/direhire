import type { Metadata } from "next";
import "./styles.css";
import { AppShell } from "./components/app-shell";

export const metadata: Metadata = {
  title: "DireHire",
  description: "Calm, focused job discovery and tracking.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">Skip to main content</a>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
