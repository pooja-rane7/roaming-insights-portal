import { cookies } from "next/headers";
import { after } from "next/server";
import { captureServer } from "@/lib/analytics-server";
import { parseFilters } from "@/lib/data";
import { buildReport, isReportId } from "@/lib/reports";
import { SESSION_COOKIE, decodeSession } from "@/lib/session";

// Builds CSV exports on the server and records a server-side `report_generated` event, so exports
// are counted even when ad blockers drop the browser's `report_exported` event.
export async function GET(req: Request) {
  const jar = await cookies();
  const session = decodeSession(jar.get(SESSION_COOKIE)?.value);
  const trafficType = jar.get("roamlens_traffic")?.value === "test" ? "test" : "real";
  if (!session) return new Response("Sign in to export data.", { status: 401 });

  const params = Object.fromEntries(new URL(req.url).searchParams);
  const report = params.report ?? "partner_scorecard";
  if (!isReportId(report)) return new Response(`Unknown report: ${report}`, { status: 400 });

  const started = performance.now();
  const f = parseFilters(params);
  const { filename, csv, rows } = buildReport(report, f);
  const durationMs = Math.round(performance.now() - started);
  after(() => captureServer(session, "report_generated", {
    report_type: report, row_count: rows, duration_ms: durationMs, direction: f.direction, country_filter: f.country, window: f.window,
  }, trafficType));
  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
