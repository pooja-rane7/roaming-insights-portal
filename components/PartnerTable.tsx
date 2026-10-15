import Link from "next/link";
import type { PartnerRow } from "@/lib/data";
import { fmtInt } from "@/lib/format";
import type { Filters, Status } from "@/lib/types";

const COUNTRY = { CA: "Canada", MX: "Mexico" } as const;
const STATUS: Record<Status, { icon: string; label: string }> = {
  healthy: { icon: "✓", label: "Healthy" },
  watch: { icon: "!", label: "Watch" },
  critical: { icon: "✕", label: "Critical" },
};

export function StatusBadge({ status }: { status: Status }) {
  return <span className={`status ${status}`}><i aria-hidden>{STATUS[status].icon}</i>{STATUS[status].label}</span>;
}

export function partnerHref(id: string, f: Pick<Filters, "direction" | "window">) {
  return `/partners/${id}?direction=${f.direction}&window=${f.window}`;
}

export function PartnerTable({ rows, filters }: { rows: PartnerRow[]; filters: Filters }) {
  const out = filters.direction === "outbound";
  return (
    <table>
      <thead>
        <tr>
          <th>{out ? "Partner network" : "Visitor home operator"}</th>
          <th>Country</th>
          <th className="num">{out ? "Roamers" : "Visitors"}</th>
          <th className="num">Share of country</th>
          <th className="num">Registration success</th>
          <th className="num">MB / roamer / day</th>
          <th className="num">Download (Mbps)</th>
          <th className="num">Upload (Mbps)</th>
          <th className="num">Latency (ms)</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p) => (
          <tr className="row" key={p.partner_id}>
            <td>
              <Link href={partnerHref(p.partner_id, filters)}>{p.name}</Link>
              {out && p.preferred && <span className="pref">Preferred</span>}
            </td>
            <td><span className="sw" style={{ background: `var(--${p.country.toLowerCase()})` }} />{COUNTRY[p.country]}</td>
            <td className="num">{fmtInt(p.unique_roamers)}</td>
            <td className="num">{p.share_of_country_pct.toFixed(0)}%</td>
            <td className="num">{p.registration_success_pct.toFixed(1)}%</td>
            <td className="num">{Math.round(p.mb_per_roamer_day)}</td>
            <td className="num">{p.median_download_mbps.toFixed(1)}</td>
            <td className="num">{p.median_upload_mbps.toFixed(1)}</td>
            <td className="num">{Math.round(p.median_latency_ms)}</td>
            <td><StatusBadge status={p.status} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
