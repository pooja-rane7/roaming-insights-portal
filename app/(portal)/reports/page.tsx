import { ReportForm } from "@/components/ReportForm";
import { ThemeToggle } from "@/components/ThemeToggle";
import { REPORTS } from "@/lib/reports";

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
      <ReportForm reports={REPORTS} />
    </>
  );
}
