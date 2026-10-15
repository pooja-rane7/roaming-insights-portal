"use client";

import { PostHogProvider } from "@posthog/react";
import posthog from "posthog-js";
import { useEffect, useRef } from "react";
import { analyticsEnabled, track, type EventMap } from "@/lib/analytics";
import { identityCalls } from "@/lib/identity";
import type { Account, Session } from "@/lib/session";

/**
 * Ties the browser's PostHog identity to the signed-in demo user and their customer account.
 * The calls themselves are planned in lib/identity.ts. group('company') requires PostHog's paid
 * group analytics add-on to be queryable, so account_* super properties are the free alternative.
 */
export function AnalyticsIdentity({ session, account }: { session: Session; account: Account }) {
  // Effects can run twice for one page load (React Strict Mode in development); send once.
  const done = useRef("");
  useEffect(() => {
    if (!analyticsEnabled() || done.current === session.userId) return;
    done.current = session.userId;
    for (const call of identityCalls(session, account, posthog.get_distinct_id())) {
      if (call.type === "identify") posthog.identify(call.distinctId, call.personProperties);
      else if (call.type === "register") posthog.register(call.properties);
      else if (call.type === "group") posthog.group(call.groupType, call.groupKey, call.groupProperties);
      else track(call.event, call.properties);
    }
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
