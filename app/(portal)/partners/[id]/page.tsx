import Link from "next/link";
import { notFound } from "next/navigation";
import { LineChart } from "@/components/charts/LineChart";
import { FilterBar } from "@/components/FilterBar";
import { KpiTiles } from "@/components/KpiTiles";
import { StatusBadge } from "@/components/PartnerTable";
import { ThemeToggle } from "@/components/ThemeToggle";
import {
  COUNTRY_COLOR_VAR, COUNTRY_NAME, getAnnotations, getPartnerDaily, getPartnerMeta, getPartnerPeriods, parseFilters,
} from "@/lib/data";
import { WINDOW_LABEL, fmtCompact, fmtData } from "@/lib/format";
import type { Series } from "@/lib/types";

type Params = Promise<{ id: string }>;
type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function PartnerPage({ params, searchParams }: { params: Params; searchParams: SearchParams }) {
  const { id } = await params;
  const partner = getPartnerMeta(id);
  if (!partner) notFound();
  const f = { ...parseFilters(await searchParams), country: partner.country };
  const out = f.direction === "outbound";
  const p = getPartnerPeriods(id, f.direction)[f.window];
  const daily = getPartnerDaily(id, f.direction, f.window);
  const dates = daily.map((d) => d.date);
  const annotations = getAnnotations(f, { partnerId: id });
  const events = annotations.filter((a) => a.kind !== "holiday");
  const one = (key: string, label: string, values: number[]): Series[] => [{ key, label, colorVar: COUNTRY_COLOR_VAR[partner.country], values }];

  return (
    <>
      <Link className="back" href={`/partners?direction=${f.direction}&window=${f.window}`}>← All partners</Link>
      <div className="top">
        <div>
          <h1>{partner.name}</h1>
          <div className="sub">
            {COUNTRY_NAME[partner.country]} · {out ? "our subscribers on this network" : "this operator's subscribers on our network"}
            {out && partner.preferred && <span className="pref">Preferred</span>} · <StatusBadge status={p.status} />
          </div>
        </div>
        <div className="actions"><ThemeToggle /></div>
      </div>
      <FilterBar filters={f} show={["direction", "window"]} />
      <KpiTiles items={[
        { label: out ? "Unique roamers" : "Unique visitors", value: fmtCompact(p.unique_roamers), note: `${p.share_of_country_pct.toFixed(0)}% of ${COUNTRY_NAME[partner.country]}` },
        { label: "Data used", value: fmtData(p.data_gb), note: `${Math.round(p.mb_per_roamer_day)} MB per ${out ? "roamer" : "visitor"} per day` },
        { label: "Registration success", value: `${p.registration_success_pct.toFixed(1)}%`, note: WINDOW_LABEL[f.window] },
        { label: "Median download", value: `${p.median_download_mbps.toFixed(1)} Mbps`, note: `${p.pct_samples_below_5mbps.toFixed(1)}% of samples below 5 Mbps` },
        { label: "Median latency", value: `${Math.round(p.median_latency_ms)} ms`, note: out ? "Measured on the partner network" : "Includes home routing" },
      ]} />
      <div className="grid2 even">
        <LineChart
          chartId="partner_active" title={out ? "Daily active roamers" : "Daily active visitors"} caption="Devices active each day"
          dates={dates} series={one("active", partner.name, daily.map((d) => d.active_roamers))}
          annotations={annotations} width={620}
        />
        <LineChart
          chartId="partner_registration" title="Registration success" caption="Successful ÷ attempted registrations, %"
          dates={dates} series={one("reg", partner.name, daily.map((d) => (100 * d.registration_successes) / d.registration_attempts))}
          annotations={events} unit="%" decimals={1} yMax={100} width={620}
        />
        <LineChart
          chartId="partner_download" title="Median download speed" caption="Daily median, Mbps"
          dates={dates} series={one("dl", partner.name, daily.map((d) => d.median_download_mbps))}
          annotations={events} unit=" Mbps" decimals={1} width={620}
        />
        <LineChart
          chartId="partner_latency" title="Median latency" caption="Daily median, ms"
          dates={dates} series={one("lat", partner.name, daily.map((d) => d.median_latency_ms))}
          annotations={events} unit=" ms" width={620}
        />
      </div>
    </>
  );
}
