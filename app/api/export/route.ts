import { cookies } from "next/headers";
import { parseFilters } from "@/lib/data";
import { buildReport, isReportId } from "@/lib/reports";
import { SESSION_COOKIE, decodeSession } from "@/lib/session";

// Builds CSV exports on the server. In Phase 4 this is where the server-side
// `report_generated` event is sent, so exports are counted even if ad blockers drop client events.
export async function GET(req: Request) {
  const session = decodeSession((await cookies()).get(SESSION_COOKIE)?.value);
  if (!session) return new Response("Sign in to export data.", { status: 401 });

  const params = Object.fromEntries(new URL(req.url).searchParams);
  const report = params.report ?? "partner_scorecard";
  if (!isReportId(report)) return new Response(`Unknown report: ${report}`, { status: 400 });

  const { filename, csv } = buildReport(report, parseFilters(params));
  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "no-store",
    },
  });
}
