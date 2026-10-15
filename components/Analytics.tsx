"use client";

import { PostHogProvider } from "@posthog/react";
import posthog from "posthog-js";
import { useEffect, useRef } from "react";
import { analyticsEnabled, track, type EventMap } from "@/lib/analytics";
import type { Account, Session } from "@/lib/session";

/**
 * Ties the browser's PostHog identity to the signed-in demo user and their customer account.
 * - identify(): once per sign-in (each sign-in creates a new user id)
 * - group('company'): every session start. Requires PostHog's paid group analytics add-on to be
 *   queryable, so we also register account_* super properties as a free alternative.
 */
export function AnalyticsIdentity({ session, account }: { session: Session; account: Account }) {
  // Effects can run twice for one page load (React Strict Mode in development); send once.
  const done = useRef("");
  useEffect(() => {
    if (!analyticsEnabled() || done.current === session.userId) return;
    done.current = session.userId;
    const accountProps = { account_id: account.id, account_name: account.name, account_plan: account.plan };
    posthog.register(accountProps);
    const isNewSignIn = posthog.get_distinct_id() !== session.userId;
    if (isNewSignIn) {
      posthog.identify(session.userId, { role: session.role, team: "roaming", ...accountProps });
    }
    posthog.group("company", account.id, { name: account.name, plan: account.plan, seats: account.seats, home_country: "US" });
    if (isNewSignIn) track("user_signed_in", { role: session.role, account_plan: account.plan });
  }, [session, account]);
  return null;
}

/** Makes PostHog available to hooks like useFeatureFlagEnabled. */
export function AnalyticsProvider({ children }: { children: React.ReactNode }) {
  return <PostHogProvider client={posthog}>{children}</PostHogProvider>;
}

/** Fire an event once when a page mounts (e.g. partner_scorecard_opened). */
export function TrackOnMount<E extends keyof EventMap>({ event, properties }: { event: E; properties: EventMap[E] }) {
  const key = JSON.stringify(properties);
  const sent = useRef("");
  useEffect(() => {
    // Fire once per distinct event + properties, even if the effect runs twice.
    if (sent.current === event + key) return;
    sent.current = event + key;
    track(event, JSON.parse(key));
  }, [event, key]);
  return null;
}
