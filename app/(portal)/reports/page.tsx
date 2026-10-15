import { ThemeToggle } from "@/components/ThemeToggle";
import { REPORTS } from "@/lib/reports";
import { WINDOW_LABEL } from "@/lib/format";

export default function ReportsPage() {
  return (
    <>
      <div className="top">
        <div>
          <h1>Reports &amp; exports</h1>
          <div className="sub">Download the data behind the portal as CSV</div>
        </div>
        <div className="actions"><ThemeToggle /></div>
      </div>
      <form className="card" action="/api/export" method="get" style={{ maxWidth: 760 }}>
        <fieldset>
          <legend>Report</legend>
          <div className="choice">
            {REPORTS.map((r, i) => (
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
    </>
  );
}
