import { BarChart } from "@/components/charts/BarChart";
import { LineChart } from "@/components/charts/LineChart";
import { ScatterChart } from "@/components/charts/ScatterChart";
import { ExportLink } from "@/components/ExportLink";
import { FilterBar } from "@/components/FilterBar";
import { KpiTiles } from "@/components/KpiTiles";
import { MapCard } from "@/components/MapCard";
import { PartnerTable } from "@/components/PartnerTable";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  getAnnotations, getBorderZones, getCountryDaily, getLocations, getPartnerRows, getSummary, metadata, parseFilters, windowRange,
} from "@/lib/data";
import { WINDOW_LABEL, fmtDayYear } from "@/lib/format";
import { dataPerRoamerBars, speedLatencyPoints, summaryKpis } from "@/lib/views";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function OverviewPage({ searchParams }: { searchParams: SearchParams }) {
  const f = parseFilters(await searchParams);
  const out = f.direction === "outbound";
  const range = windowRange(f.window);
  const partners = getPartnerRows(f);
  const roamers = getCountryDaily(f, "active_roamers");
  const speed = getCountryDaily(f, "median_download_mbps");
  const rule = metadata.status_rule;

  return (
    <>
      <div className="top">
        <div>
          <h1>Roaming overview</h1>
          <div className="sub">
            {out ? "Our subscribers roaming in" : "Visitors on our U.S. network from"} Canada &amp; Mexico · {fmtDayYear(range.start)} – {fmtDayYear(range.end)}
          </div>
        </div>
        <div className="actions">
          <ThemeToggle />
          <ExportLink report="partner_scorecard" filters={f} />
        </div>
      </div>
      <div className="banner">Demo data. Every operator and number is <b>fictional</b>.</div>

      <FilterBar filters={f} />
      <KpiTiles items={summaryKpis(getSummary(f), f)} />

      <div className="grid2">
        <MapCard
          direction={f.direction} windowLabel={WINDOW_LABEL[f.window]}
          points={getLocations(f)} zones={getBorderZones(f)} fitKey={`${f.direction}-${f.country}`}
        />
        <div className="stack">
          <LineChart
            chartId="daily_roamers" title={out ? "Daily outbound roamers" : "Daily inbound visitors"}
            caption="Devices active each day" dates={roamers.dates} series={roamers.series}
            annotations={getAnnotations(f, { kinds: ["holiday"] })}
          />
          <div className="card">
            <h3>Speed vs. latency by partner</h3>
            <div className="cap">
              {out ? "Our subscribers on each partner network. Top-left is best." : "Visitors on our network, by home operator. Home routing adds latency."}
            </div>
            <ScatterChart
              points={speedLatencyPoints(partners)} xMax={160} yMax={60}
              xLabel="Median latency (ms) → worse" yLabel="Download (Mbps) ↑ better" corner="Best experience"
            />
          </div>
        </div>
      </div>

      <div className="grid2 even">
        <LineChart
          chartId="daily_download" title="Daily median download speed"
          caption="Combined median across partners, Mbps" dates={speed.dates} series={speed.series}
          annotations={getAnnotations(f, { kinds: ["incident", "upgrade"] })} unit=" Mbps" decimals={1} yMax={60} width={620}
        />
        <div className="card">
          <h3>Data per roamer by partner</h3>
          <div className="cap">Average MB per {out ? "roamer" : "visitor"} per day</div>
          <BarChart bars={dataPerRoamerBars(partners, f)} />
        </div>
      </div>

      <div className="card">
        <h3>{out ? "Partner scorecard · outbound" : "Home-operator scorecard · inbound"}</h3>
        <div className="cap">
          {out ? "Partner networks our subscribers use abroad. Steering target: ≥ 80% of each country's roamers on the preferred partner. " : "Operators whose subscribers visit our network. Latency includes home routing. "}
          Status: Critical if registration &lt; {rule.critical.reg_below * 100}%, download &lt; {rule.critical.dl_below} Mbps or latency &gt; {rule.critical.lat_above} ms;
          Watch if &lt; {rule.watch.reg_below * 100}%, &lt; {rule.watch.dl_below} Mbps or &gt; {rule.watch.lat_above} ms. Select a partner for daily detail.
        </div>
        <PartnerTable rows={partners} filters={f} />
      </div>
    </>
  );
}
