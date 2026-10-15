// Client-side analytics. The tracking plan (docs/tracking-plan.md) as types: an event or
// property that isn't in the plan won't compile.
import posthog from "posthog-js";
import type { Direction, WindowKey } from "./types";

export type PageName = "sign_in" | "overview" | "partners" | "partner_detail" | "reports" | "alerts" | "other";

export interface EventMap {
  user_signed_in: { role: string; account_plan: string; login_method: string };
  filter_applied: { filter_name: "direction" | "country" | "window"; filter_value: string; page_name: PageName };
  map_marker_clicked: { location_type: "city" | "border_zone"; country_code: string; direction: Direction; location_name: string };
  border_layer_toggled: { is_enabled: boolean };
  partner_scorecard_opened: { partner_id: string; direction: Direction; partner_status: string; window: WindowKey };
  chart_view_toggled: { chart_id: string; view: "chart" | "table" };
  report_exported: { report_type: string; format: "csv"; direction: string; country_filter: string; window: string; page_name: PageName };
  alert_created: { metric: string; threshold: number; partner_id: string };
  theme_changed: { theme: "light" | "dark" };
}

/** Whether PostHog was initialized (it's skipped when no project token is configured). */
export const analyticsEnabled = () => typeof window !== "undefined" && Boolean(posthog.__loaded);

export function track<E extends keyof EventMap>(event: E, properties: EventMap[E]): void {
  if (analyticsEnabled()) posthog.capture(event, properties);
}

export function pageName(pathname: string): PageName {
  if (pathname === "/") return "sign_in";
  if (pathname.startsWith("/overview")) return "overview";
  if (/^\/partners\/[^/]+/.test(pathname)) return "partner_detail";
  if (pathname.startsWith("/partners")) return "partners";
  if (pathname.startsWith("/reports")) return "reports";
  if (pathname.startsWith("/alerts")) return "alerts";
  return "other";
}
