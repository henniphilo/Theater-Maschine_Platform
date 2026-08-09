"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";

import { WorkshopStatusBar } from "@/components/layout/WorkshopStatusBar";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { apiBaseUrl } from "@/lib/api/base";

type NavLink = {
  href: Route;
  label: string;
  short: string;
  icon: NavIcon;
};

type NavIcon =
  | "productions"
  | "technik"
  | "einstellungen"
  | "dramaturgie"
  | "inszenierung"
  | "auffuehrung"
  | "stueck"
  | "director"
  | "remote";

/** Single flat register list — same items in sidebar and top tabs. */
const LINKS: NavLink[] = [
  { href: "/productions" as Route, label: "Produktionen", short: "Produktionen", icon: "productions" },
  { href: "/technik" as Route, label: "Technik-Test", short: "Technik", icon: "technik" },
  { href: "/einstellungen" as Route, label: "Einstellungen", short: "Einstellungen", icon: "einstellungen" },
  { href: "/dramaturgie" as Route, label: "Teil 1", short: "Dramaturgie", icon: "dramaturgie" },
  { href: "/stueck" as Route, label: "Stück", short: "Stück", icon: "stueck" },
  { href: "/inszenierung" as Route, label: "Teil 2", short: "Inszenierung", icon: "inszenierung" },
  { href: "/auffuehrung" as Route, label: "Aufführung", short: "Aufführung", icon: "auffuehrung" },
  { href: "/director" as Route, label: "Director", short: "Director", icon: "director" },
  { href: "/remote" as Route, label: "Remote", short: "Remote", icon: "remote" }
];

function NavIconSvg({ name }: { name: NavIcon }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.75,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const
  };

  switch (name) {
    case "productions":
      return (
        <svg {...common}>
          <path d="M4 6h16" />
          <path d="M4 12h16" />
          <path d="M4 18h10" />
        </svg>
      );
    case "technik":
      return (
        <svg {...common}>
          <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
          <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9c.3.6.9 1 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
        </svg>
      );
    case "einstellungen":
      return (
        <svg {...common}>
          <path d="M4 6h10" />
          <path d="M18 6h2" />
          <circle cx="16" cy="6" r="2" />
          <path d="M4 12h2" />
          <path d="M10 12h10" />
          <circle cx="8" cy="12" r="2" />
          <path d="M4 18h10" />
          <path d="M18 18h2" />
          <circle cx="16" cy="18" r="2" />
        </svg>
      );
    case "dramaturgie":
      return (
        <svg {...common}>
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
          <path d="M8 7h8M8 11h6" />
        </svg>
      );
    case "stueck":
      return (
        <svg {...common}>
          <path d="M4 4h16v16H4z" />
          <path d="M8 8h8M8 12h8M8 16h5" />
        </svg>
      );
    case "inszenierung":
      return (
        <svg {...common}>
          <path d="M12 3 4 7.5 12 12l8-4.5L12 3Z" />
          <path d="M4 12.5 12 17l8-4.5" />
          <path d="M4 17.5 12 22l8-4.5" />
        </svg>
      );
    case "auffuehrung":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M10 8.5v7l6-3.5-6-3.5Z" fill="currentColor" stroke="none" />
        </svg>
      );
    case "director":
      return (
        <svg {...common}>
          <path d="M12 3v18" />
          <path d="M5 8h14" />
          <path d="M7 8v5a5 5 0 0 0 10 0V8" />
        </svg>
      );
    case "remote":
      return (
        <svg {...common}>
          <rect x="7" y="2" width="10" height="20" rx="2" />
          <circle cx="12" cy="17" r="1.2" fill="currentColor" stroke="none" />
        </svg>
      );
  }
}

function isActive(pathname: string, href: string) {
  if (href === "/inszenierung") {
    return pathname === "/inszenierung" || pathname.startsWith("/inszenierung/");
  }
  if (href === "/auffuehrung") {
    return pathname === "/auffuehrung" || pathname.startsWith("/auffuehrung/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function useBackendHealth(enabled: boolean) {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: number | undefined;

    const tick = async () => {
      try {
        const res = await fetch(`${apiBaseUrl()}/health`, { cache: "no-store" });
        if (!cancelled) setOnline(res.ok);
      } catch {
        if (!cancelled) setOnline(false);
      }
      if (!cancelled) {
        timer = window.setTimeout(() => {
          void tick();
        }, 8000);
      }
    };

    void tick();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [enabled]);

  return online;
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isRemote = pathname === "/remote" || pathname.startsWith("/remote/");
  const backendOnline = useBackendHealth(!isRemote);

  // Phone remote: no chrome. Everywhere else: classic sidebar + top register tabs.
  if (isRemote) {
    return <div className="appShell appShellRemote">{children}</div>;
  }

  return (
    <div className="appShell">
      <aside className="appSidebar" aria-label="Hauptnavigation">
        <div className="appSidebarBrand">
          <span className="appBrandIcon" aria-hidden="true">
            <svg width="12" height="12" viewBox="0 0 10 10" fill="currentColor">
              <path d="M2.2 1.1v7.8L8.6 5 2.2 1.1z" />
            </svg>
          </span>
          <div className="appSidebarBrandText">
            <span className="appBrandMark">AutoPlay</span>
            <span className="appBrandClaim">theater-maschine</span>
          </div>
        </div>

        <nav className="appSidebarNav">
          {LINKS.map((link) => {
            const active = isActive(pathname, link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={active ? "appSidebarLink appSidebarLinkActive" : "appSidebarLink"}
              >
                <span className="appSidebarLinkIcon">
                  <NavIconSvg name={link.icon} />
                </span>
                <span className="appSidebarLinkLabel">{link.short}</span>
              </Link>
            );
          })}
        </nav>

        <div className="appSidebarFooter">
          <div className="appSidebarStatus">
            <span
              className={
                backendOnline === false
                  ? "appSidebarStatusDot appSidebarStatusDotOffline"
                  : "appSidebarStatusDot"
              }
              aria-hidden="true"
            />
            <div>
              <strong>Backend</strong>
              <span>
                {backendOnline === null ? "Prüfe …" : backendOnline ? "Online" : "Offline"}
              </span>
            </div>
          </div>
        </div>
      </aside>

      <div className="appShellMain">
        <header className="appTopbar">
          <nav className="appTopNav" aria-label="Register">
            {LINKS.map((link) => {
              const active = isActive(pathname, link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={active ? "appTopNavLink appTopNavLinkActive" : "appTopNavLink"}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
          <div className="appTopbarAside">
            <WorkshopStatusBar />
            <ThemeToggle />
          </div>
        </header>
        <div className="appContent">{children}</div>
      </div>
    </div>
  );
}

/** @deprecated Use AppShell — kept for pages that still import it during migration */
export function AppNav() {
  return null;
}
