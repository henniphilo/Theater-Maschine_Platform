"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { WorkshopStatusBar } from "@/components/layout/WorkshopStatusBar";

const LINKS = [
  { href: "/technik", label: "Technik-Test" },
  { href: "/dramaturgie", label: "Dramaturgie" },
  { href: "/inszenierung", label: "Teil 2" },
  { href: "/stueck", label: "Stücktext" },
  { href: "/auffuehrung", label: "Aufführung" },
  { href: "/director", label: "Live-Regie" }
] as const;

export function AppNav() {
  const pathname = usePathname();

  return (
    <div className="col" style={{ alignItems: "flex-end", gap: "0.25rem" }}>
      <WorkshopStatusBar />
      <nav className="appNav" aria-label="Hauptnavigation">
        {LINKS.map((link) => {
          const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
          return (
            <Link key={link.href} href={link.href} className={active ? "appNavLink appNavLinkActive" : "appNavLink"}>
              {link.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
