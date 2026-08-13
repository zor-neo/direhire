"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { ApiError, apiRequest, displayError } from "../lib/api";
import { AppShell, type ProductSession } from "./app-shell";

const publicPaths = new Set(["/"]);

export function ShellRouter({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [session, setSession] = useState<ProductSession | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (publicPaths.has(pathname)) return;

    let active = true;
    apiRequest<ProductSession>("/auth/session")
      .then((value) => {
        if (active) setSession(value);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        if (reason instanceof ApiError && reason.code === "AUTHENTICATION_REQUIRED") {
          window.location.replace("/");
          return;
        }
        setError(displayError(reason));
      });
    return () => {
      active = false;
    };
  }, [pathname]);

  if (publicPaths.has(pathname)) {
    return <div className="public-layout">{children}</div>;
  }

  if (error) {
    return (
      <main className="auth-state" id="main">
        <span className="brand-mark" aria-hidden="true">D</span>
        <h1>We could not verify your session</h1>
        <p>{error}</p>
        <div className="landing-actions">
          <button className="button primary" onClick={() => window.location.reload()}>Try again</button>
          <Link className="button" href="/">Return home</Link>
        </div>
      </main>
    );
  }

  if (!session) {
    return (
      <main className="auth-state" id="main" aria-busy="true">
        <span className="brand-mark" aria-hidden="true">D</span>
        <p>Opening your workspace…</p>
      </main>
    );
  }

  return <AppShell session={session}>{children}</AppShell>;
}
