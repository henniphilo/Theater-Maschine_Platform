"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/dramaturgie", label: "Dramaturgie" },
  { href: "/stueck", label: "Stücktext" },
  { href: "/auffuehrung", label: "Aufführung" },
  { href: "/director", label: "Live-Regie" }
] as const;

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="appNav" aria-label="Hauptnavigation">
      {LINKS.map((link) => {
        const active = pathname === link.href || pathname.startsWith(`${link.href}?`);
        return (
          <Link key={link.href} href={link.href} className={active ? "appNavLink appNavLinkActive" : "appNavLink"}>
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
