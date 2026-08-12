"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { apiLoginUrl } from "../lib/api";
import { Icon, type IconName } from "./icons";

interface NavItem {
  href: string;
  label: string;
  icon: IconName;
}

const discoverGroup: NavItem[] = [
  { href: "/", label: "Dashboard", icon: "dashboard" },
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

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <Link className="brand" href="/" aria-label="DireHire dashboard">
          <span className="brand-mark" aria-hidden="true">D</span> DireHire
        </Link>
        <nav aria-label="Primary navigation">
          <NavLinks pathname={pathname} />
        </nav>
        <div className="sidebar-footer">
          <Link href="/privacy"><Icon name="privacy" />Privacy &amp; data</Link>
          <Link href="/admin"><Icon name="operations" />Operations</Link>
          <a href={apiLoginUrl()}><Icon name="signin" />Sign in</a>
        </div>
      </aside>
      <div className="content-shell">
        <header className="mobile-header">
          <Link className="brand" href="/">
            <span className="brand-mark" aria-hidden="true">D</span> DireHire
          </Link>
          <details className="mobile-menu">
            <summary><Icon name="menu" size={16} />Menu</summary>
            <nav aria-label="Mobile navigation">
              {allItems.map(({ href, label, icon }) => (
                <Link href={href} key={href}><Icon name={icon} size={16} />{label}</Link>
              ))}
              <Link href="/privacy"><Icon name="privacy" size={16} />Privacy &amp; data</Link>
              <a href={apiLoginUrl()}><Icon name="signin" size={16} />Sign in</a>
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
