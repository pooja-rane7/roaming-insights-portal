"use client";

import { track } from "@/lib/analytics";
import { WINDOW_LABEL } from "@/lib/format";

interface ReportOption {
  id: string;
  label: string;
  description: string;
}

export function ReportForm({ reports }: { reports: readonly ReportOption[] }) {
  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    const d = new FormData(e.currentTarget);
    track("report_exported", {
      report_type: String(d.get("report")), format: "csv", direction: String(d.get("direction")),
      country_filter: String(d.get("country")), window: String(d.get("window")), page_name: "reports",
    });
  }

  return (
    <form className="card" action="/api/export" method="get" style={{ maxWidth: 760 }} onSubmit={onSubmit}>
      <fieldset>
        <legend>Report</legend>
        <div className="choice">
          {reports.map((r, i) => (
            <label key={r.id}>
              <input type="radio" name="report" value={r.id} defaultChecked={i === 0} />
              <b>{r.label}</b>
              <small>{r.description}</small>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="filters">
        <label>Direction{" "}
          <select name="direction" defaultValue="outbound" className="btn">
            <option value="outbound">Outbound</option>
            <option value="inbound">Inbound</option>
          </select>
        </label>
        <label>Country{" "}
          <select name="country" defaultValue="all" className="btn">
            <option value="all">All</option>
            <option value="CA">Canada</option>
            <option value="MX">Mexico</option>
          </select>
        </label>
        <label>Period{" "}
          <select name="window" defaultValue="30d" className="btn">
            {Object.entries(WINDOW_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>
      <button type="submit" className="btn primary">⤓ Download CSV</button>
    </form>
  );
}
