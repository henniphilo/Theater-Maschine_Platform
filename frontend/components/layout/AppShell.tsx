"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";

import { WorkshopStatusBar } from "@/components/layout/WorkshopStatusBar";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

const LINKS = [
  { href: "/productions", label: "Produktionen", short: "Produktionen", icon: "productions" },
  { href: "/technik", label: "Technik-Test", short: "Technik", icon: "technik" },
  { href: "/dramaturgie", label: "Teil 1", short: "Dramaturgie", icon: "dramaturgie" },
  { href: "/inszenierung", label: "Teil 2", short: "Inszenierung", icon: "inszenierung" },
  { href: "/auffuehrung", label: "Aufführung", short: "Aufführung", icon: "auffuehrung" }
] as const;

type NavIcon = (typeof LINKS)[number]["icon"];

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
    case "dramaturgie":
      return (
        <svg {...common}>
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
          <path d="M8 7h8M8 11h6" />
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
  }
}

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

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
            <span className="appBrandClaim">Dramaturgie. Automation. Performance.</span>
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
            <span className="appSidebarStatusDot" aria-hidden="true" />
            <div>
              <strong>AutoPlay</strong>
              <span>Online</span>
            </div>
          </div>
        </div>
      </aside>

      <div className="appShellMain">
        <header className="appTopbar">
          <nav className="appTopNav" aria-label="Bereiche">
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
