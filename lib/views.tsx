// View-model builders shared by pages: turn dataset rows into chart and tile props.
import type { Bar } from "@/components/charts/BarChart";
import type { ScatterPoint } from "@/components/charts/ScatterChart";
import type { Kpi } from "@/components/KpiTiles";
import type { PartnerRow } from "./data";
import { COUNTRY_COLOR_VAR, COUNTRY_NAME } from "./data";
import { delta, fmtCompact, fmtData } from "./format";
import type { Filters, SummaryRow } from "./types";

export function summaryKpis(s: SummaryRow, f: Filters): Kpi[] {
  const out = f.direction === "outbound";
  return [
    { label: out ? "Unique outbound roamers" : "Unique inbound visitors", value: fmtCompact(s.unique_roamers), delta: delta(s.unique_roamers, s.prev_unique_roamers) },
    { label: out ? "Roaming data used" : "Visitor data on our network", value: fmtData(s.data_gb), delta: delta(s.data_gb, s.prev_data_gb) },
    out
      ? { label: "Steering to preferred partner", value: `${s.steering_to_preferred_pct!.toFixed(0)}%`, note: "Target ≥ 80%" }
      : { label: "Median latency", value: `${Math.round(s.median_latency_ms)} ms`, delta: delta(s.median_latency_ms, s.prev_median_latency_ms, false) },
    { label: "Registration success", value: `${s.registration_success_pct.toFixed(1)}%`, note: "Successful network registrations" },
    { label: "Median download speed", value: `${s.median_download_mbps.toFixed(1)} Mbps`, delta: delta(s.median_download_mbps, s.prev_median_download_mbps) },
  ];
}

export function speedLatencyPoints(rows: PartnerRow[]): ScatterPoint[] {
  return rows.map((p) => ({
    id: p.partner_id,
    label: p.name,
    x: p.median_latency_ms,
    y: p.median_download_mbps,
    colorVar: COUNTRY_COLOR_VAR[p.country],
    tooltip: (
      <>
        <b>{p.name}</b> · {COUNTRY_NAME[p.country]}
        <div>Download {p.median_download_mbps.toFixed(1)} Mbps · Upload {p.median_upload_mbps.toFixed(1)} Mbps</div>
        <div>Latency {Math.round(p.median_latency_ms)} ms</div>
        <div>{p.pct_samples_below_5mbps.toFixed(1)}% of samples below 5 Mbps</div>
      </>
    ),
  }));
}

export function dataPerRoamerBars(rows: PartnerRow[], f: Filters): Bar[] {
  return [...rows]
    .sort((a, b) => b.mb_per_roamer_day - a.mb_per_roamer_day)
    .map((p) => ({
      id: p.partner_id,
      label: p.name,
      value: p.mb_per_roamer_day,
      colorVar: COUNTRY_COLOR_VAR[p.country],
      tooltip: (
        <>
          <b>{p.name}</b> · {COUNTRY_NAME[p.country]}
          <div>{Math.round(p.mb_per_roamer_day)} MB per {f.direction === "outbound" ? "roamer" : "visitor"} per day</div>
          <div>{fmtData(p.data_gb)} total</div>
        </>
      ),
    }));
}

export function exportHref(report: string, f: Filters) {
  return `/api/export?report=${report}&direction=${f.direction}&country=${f.country}&window=${f.window}`;
}
