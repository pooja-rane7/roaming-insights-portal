"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/overview", label: "Overview" },
  { href: "/partners", label: "Partner scorecards" },
  { href: "/reports", label: "Reports & exports" },
];

export function SideNav({ accountName, roleLabel }: { accountName: string; roleLabel: string }) {
  const pathname = usePathname();
  return (
    <nav className="sidenav" aria-label="Main">
      <div className="logo">◆ RoamLens</div>
      <div className="org">{accountName} · Roaming team</div>
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href} className={pathname.startsWith(l.href) ? "on" : ""} aria-current={pathname.startsWith(l.href) ? "page" : undefined}>
          {l.label}
        </Link>
      ))}
      <div className="who">
        Signed in as
        <b>{roleLabel}</b>
        {accountName}
        <form action="/api/session/signout" method="post">
          <button type="submit">Sign out</button>
        </form>
      </div>
    </nav>
  );
}
