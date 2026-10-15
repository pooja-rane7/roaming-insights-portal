// Server-side analytics (posthog-node). Used for events that must not depend on the browser,
// like report_generated in /api/export.
import { PostHog } from "posthog-node";
import packageJson from "@/package.json";
import { getAccount, type Session } from "./session";

export interface ServerEvent {
  report_generated: { report_type: string; row_count: number; duration_ms: number; direction: string; country_filter: string; window: string };
}

/** Send one event and flush. Call inside `after()` so it never delays the response. */
export async function captureServer<E extends keyof ServerEvent>(session: Session, event: E, properties: ServerEvent[E]): Promise<void> {
  const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN;
  if (!token) return;
  // Short-lived server work: send immediately instead of batching.
  const client = new PostHog(token, { host: process.env.POSTHOG_HOST ?? "https://us.i.posthog.com", flushAt: 1, flushInterval: 0 });
  const account = getAccount(session.accountId);
  try {
    client.capture({
      distinctId: session.userId,
      event,
      properties: {
        ...properties,
        source: "server",
        // Mirror the browser's super properties so server and client events filter the same way.
        app_version: packageJson.version,
        environment: process.env.NEXT_PUBLIC_APP_ENV ?? "development",
        traffic_source_type: "real",
        account_id: session.accountId,
        account_name: account?.name,
        account_plan: account?.plan,
      },
      groups: { company: session.accountId },
    });
  } finally {
    await client.shutdown();
  }
}
