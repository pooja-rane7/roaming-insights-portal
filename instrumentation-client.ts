// Runs in the browser before the app becomes interactive (Next.js instrumentation-client convention).
import posthog from "posthog-js";

const token = process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN;

if (token) {
  posthog.init(token, {
    // Events go through our own domain (see rewrites in next.config.ts) so ad blockers don't drop them.
    api_host: "/lens-relay",
    ui_host: process.env.NEXT_PUBLIC_POSTHOG_UI_HOST ?? "https://us.posthog.com",
    defaults: "2026-05-30",
    // Only identified (signed-in) users get person profiles; anonymous sign-in page views stay cheap.
    person_profiles: "identified_only",
  });

  // Super properties: attached to every event from this browser.
  posthog.register({
    app_version: process.env.NEXT_PUBLIC_APP_VERSION,
    environment: process.env.NEXT_PUBLIC_APP_ENV ?? "development",
    traffic_source_type: "real",
  });
}
