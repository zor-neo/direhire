"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { apiRequest } from "../lib/api";
import { Icon, type IconName } from "./icons";

interface NavItem {
  href: string;
  label: string;
  icon: IconName;
}

const discoverGroup: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: "dashboard" },
  { href: "/watches", label: "Job Watches", icon: "watch" },
  { href: "/inbox", label: "Job Inbox", icon: "inbox" },
  { href: "/analyze", label: "Analyze a Job", icon: "analyze" },
];

const manageGroup: NavItem[] = [
  { href: "/applications", label: "Applications", icon: "applications" },
  { href: "/notifications", label: "Notifications", icon: "bell" },
  { href: "/career", label: "Career tools", icon: "career" },
  { href: "/settings", label: "Settings", icon: "settings" },
];

const allItems = [...discoverGroup, ...manageGroup];

export interface ProductSession {
  role: string;
  plan: string;
}

function NavLinks({ pathname }: { pathname: string }) {
  return (
    <>
      <div className="nav-group">
        <p className="nav-label">Discover</p>
        {discoverGroup.map(({ href, label, icon }) => (
          <Link className={pathname === href ? "active" : ""} href={href} key={href}>
            <Icon name={icon} />
            {label}
          </Link>
        ))}
      </div>
      <div className="nav-group">
        <p className="nav-label">Manage</p>
        {manageGroup.map(({ href, label, icon }) => (
          <Link className={pathname === href ? "active" : ""} href={href} key={href}>
            <Icon name={icon} />
            {label}
          </Link>
        ))}
      </div>
    </>
  );
}

export function AppShell({ children, session }: { children: ReactNode; session: ProductSession }) {
  const pathname = usePathname();
  const canOperate = session.role === "ADMIN" || session.role === "SUPERADMIN";

  async function signOut() {
    await apiRequest<void>("/auth/session", { method: "DELETE" });
    window.location.replace("/");
  }

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard" aria-label="DireHire dashboard">
          <span className="brand-mark" aria-hidden="true">D</span> DireHire
        </Link>
        <nav aria-label="Primary navigation">
          <NavLinks pathname={pathname} />
        </nav>
        <div className="sidebar-footer">
          <Link href="/privacy"><Icon name="privacy" />Privacy &amp; data</Link>
          {canOperate && <Link href="/admin"><Icon name="operations" />Operations</Link>}
          <button className="sidebar-action" type="button" onClick={() => void signOut()}>
            <Icon name="signin" />Sign out
          </button>
        </div>
      </aside>
      <div className="content-shell">
        <header className="mobile-header">
          <Link className="brand" href="/dashboard">
            <span className="brand-mark" aria-hidden="true">D</span> DireHire
          </Link>
          <details className="mobile-menu">
            <summary><Icon name="menu" size={16} />Menu</summary>
            <nav aria-label="Mobile navigation">
              {allItems.map(({ href, label, icon }) => (
                <Link href={href} key={href}><Icon name={icon} size={16} />{label}</Link>
              ))}
              <Link href="/privacy"><Icon name="privacy" size={16} />Privacy &amp; data</Link>
              {canOperate && <Link href="/admin"><Icon name="operations" size={16} />Operations</Link>}
              <button type="button" onClick={() => void signOut()}><Icon name="signin" size={16} />Sign out</button>
            </nav>
          </details>
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
