"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { apiLoginUrl } from "../lib/api";

const navigation = [
  ["/", "Dashboard"],
  ["/watches", "Job Watches"],
  ["/inbox", "Job Inbox"],
  ["/analyze", "Analyze a Job"],
  ["/applications", "Applications"],
  ["/notifications", "Notifications"],
  ["/career", "Career tools"],
  ["/settings", "Settings"],
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="DireHire dashboard">
          <span aria-hidden="true">D</span> DireHire
        </Link>
        <nav aria-label="Primary navigation">
          {navigation.map(([href, label]) => (
            <Link className={pathname === href ? "active" : ""} href={href} key={href}>
              {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-footer">
          <Link href="/privacy">Privacy &amp; data</Link>
          <Link href="/admin">Operations</Link>
          <a href={apiLoginUrl()}>Sign in</a>
        </div>
      </aside>
      <div className="content-shell">
        <header className="mobile-header">
          <Link className="brand" href="/">DireHire</Link>
          <details className="mobile-menu"><summary>Menu</summary><nav aria-label="Mobile navigation">{navigation.map(([href, label]) => <Link href={href} key={href}>{label}</Link>)}<Link href="/privacy">Privacy &amp; data</Link><a href={apiLoginUrl()}>Sign in</a></nav></details>
        </header>
        <main id="main">{children}</main>
      </div>
    </div>
  );
}

export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="page-header">
      <div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1></div>
      {children && <div className="header-actions">{children}</div>}
    </div>
  );
}

export function StatusMessage({ children }: { children: ReactNode }) {
  return <p className="status-message" role="status" aria-live="polite">{children}</p>;
}
