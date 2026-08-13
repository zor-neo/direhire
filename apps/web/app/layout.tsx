import type { Metadata } from "next";
import "./styles.css";
import { ShellRouter } from "./components/shell-router";

export const metadata: Metadata = {
  title: "DireHire",
  description: "Calm, focused job discovery and tracking.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">Skip to main content</a>
        <ShellRouter>{children}</ShellRouter>
      </body>
    </html>
  );
}
