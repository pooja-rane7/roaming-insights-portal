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

  // Super properties: attached to every event from this browser. QA browsers set
  // localStorage.roamlens_traffic = "test" so our own checks never count as real usage.
  let trafficType = "real";
  try {
    if (localStorage.getItem("roamlens_traffic") === "test") {
      trafficType = "test";
      // Mirror the flag into a cookie so server-side events (e.g. report_generated) are tagged too.
      document.cookie = "roamlens_traffic=test; path=/; SameSite=Lax; max-age=31536000";
    }
  } catch {
    // storage unavailable (privacy mode); treat as real
  }
  posthog.register({
    app_version: process.env.NEXT_PUBLIC_APP_VERSION,
    environment: process.env.NEXT_PUBLIC_APP_ENV ?? "development",
    traffic_source_type: trafficType,
  });
}
