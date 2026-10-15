"use client";

import { useFeatureFlagEnabled } from "@posthog/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import posthog from "posthog-js";
import { analyticsEnabled } from "@/lib/analytics";

const LINKS = [
  { href: "/overview", label: "Overview" },
  { href: "/partners", label: "Partner scorecards" },
  { href: "/reports", label: "Reports & exports" },
];

export function SideNav({ accountName, roleLabel }: { accountName: string; roleLabel: string }) {
  const pathname = usePathname();
  const alertsBeta = useFeatureFlagEnabled("alerts-beta");
  const links = alertsBeta ? [...LINKS, { href: "/alerts", label: "Alerts", beta: true }] : LINKS;

  return (
    <nav className="sidenav" aria-label="Main">
      <div className="logo">◆ RoamLens</div>
      <div className="org">{accountName} · Roaming team</div>
      {links.map((l) => (
        <Link key={l.href} href={l.href} className={pathname.startsWith(l.href) ? "on" : ""} aria-current={pathname.startsWith(l.href) ? "page" : undefined}>
          {l.label}{"beta" in l && <span className="beta">beta</span>}
        </Link>
      ))}
      <div className="who">
        Signed in as
        <b>{roleLabel}</b>
        {accountName}
        {/* Reset PostHog before signing out, so the next demo user isn't merged into this one. */}
        <form action="/api/session/signout" method="post" onSubmit={() => analyticsEnabled() && posthog.reset()}>
          <button type="submit">Sign out</button>
        </form>
      </div>
    </nav>
  );
}
