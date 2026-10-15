import { BarChart } from "@/components/charts/BarChart";
import { ScatterChart } from "@/components/charts/ScatterChart";
import { ExportLink } from "@/components/ExportLink";
import { FilterBar } from "@/components/FilterBar";
import { PartnerTable } from "@/components/PartnerTable";
import { ThemeToggle } from "@/components/ThemeToggle";
import { getPartnerRows, parseFilters } from "@/lib/data";
import { WINDOW_LABEL } from "@/lib/format";
import { dataPerRoamerBars, speedLatencyPoints } from "@/lib/views";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function PartnersPage({ searchParams }: { searchParams: SearchParams }) {
  const f = parseFilters(await searchParams);
  const rows = getPartnerRows(f);
  const out = f.direction === "outbound";

  return (
    <>
      <div className="top">
        <div>
          <h1>Partner scorecards</h1>
          <div className="sub">{out ? "Networks our subscribers roam on" : "Operators whose subscribers visit our network"} · {WINDOW_LABEL[f.window]}</div>
        </div>
        <div className="actions">
          <ThemeToggle />
          <ExportLink report="partner_scorecard" filters={f} />
        </div>
      </div>
      <FilterBar filters={f} />
      <div className="card" style={{ marginBottom: 14 }}>
        <h3>Scorecard</h3>
        <div className="cap">Select a partner for daily trends and events.</div>
        <PartnerTable rows={rows} filters={f} />
      </div>
      <div className="grid2 even">
        <div className="card">
          <h3>Speed vs. latency</h3>
          <div className="cap">Median download vs. median latency. Top-left is best.</div>
          <ScatterChart
            points={speedLatencyPoints(rows)} xMax={160} yMax={60}
            xLabel="Median latency (ms) → worse" yLabel="Download (Mbps) ↑ better" corner="Best experience"
          />
        </div>
        <div className="card">
          <h3>Data per roamer</h3>
          <div className="cap">Average MB per {out ? "roamer" : "visitor"} per day</div>
          <BarChart bars={dataPerRoamerBars(rows, f)} />
        </div>
      </div>
    </>
  );
}
