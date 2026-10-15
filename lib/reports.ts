import { type Column, toCsv } from "./csv";
import { getBorderZones, getCountryDailyRows, getPartnerRows, type MapPoint, type PartnerRow } from "./data";
import type { CountryDailyRow, Filters } from "./types";

export const REPORTS = [
  { id: "partner_scorecard", label: "Partner scorecard", description: "One row per partner: roamers, share, registration, data, speed, latency, status" },
  { id: "daily_trend", label: "Daily trend by country", description: "One row per day and country: active roamers, data, registration, speed, latency" },
  { id: "border_zones", label: "Border zones", description: "Cross-border registrations per border zone" },
] as const;

export type ReportId = (typeof REPORTS)[number]["id"];
export const isReportId = (v: string): v is ReportId => REPORTS.some((r) => r.id === v);

const partnerColumns: Column<PartnerRow>[] = [
  { header: "partner", value: (r) => r.name },
  { header: "country", value: (r) => r.country },
  { header: "preferred", value: (r) => r.preferred },
  { header: "unique_roamers", value: (r) => r.unique_roamers },
  { header: "share_of_country_pct", value: (r) => r.share_of_country_pct },
  { header: "registration_success_pct", value: (r) => r.registration_success_pct },
  { header: "data_gb", value: (r) => r.data_gb },
  { header: "mb_per_roamer_day", value: (r) => r.mb_per_roamer_day },
  { header: "median_download_mbps", value: (r) => r.median_download_mbps },
  { header: "median_upload_mbps", value: (r) => r.median_upload_mbps },
  { header: "median_latency_ms", value: (r) => r.median_latency_ms },
  { header: "status", value: (r) => r.status },
];

const dailyColumns: Column<CountryDailyRow>[] = [
  { header: "date", value: (r) => r.date },
  { header: "country", value: (r) => r.country },
  { header: "active_roamers", value: (r) => r.active_roamers },
  { header: "data_gb", value: (r) => r.data_gb },
  { header: "registration_success_pct", value: (r) => r.registration_success_pct },
  { header: "median_download_mbps", value: (r) => r.median_download_mbps },
  { header: "median_upload_mbps", value: (r) => r.median_upload_mbps },
  { header: "median_latency_ms", value: (r) => r.median_latency_ms },
];

const borderColumns: Column<MapPoint>[] = [
  { header: "border_zone", value: (r) => r.name },
  { header: "other_country", value: (r) => r.country },
  { header: "cross_border_registrations", value: (r) => r.value },
];

export function buildReport(report: ReportId, f: Filters): { filename: string; csv: string; rows: number } {
  const filename = `roamlens_${report}_${f.direction}_${f.country}_${f.window}.csv`;
  switch (report) {
    case "partner_scorecard": {
      const rows = getPartnerRows(f);
      return { filename, csv: toCsv(rows, partnerColumns), rows: rows.length };
    }
    case "daily_trend": {
      const rows = getCountryDailyRows(f);
      return { filename, csv: toCsv(rows, dailyColumns), rows: rows.length };
    }
    case "border_zones": {
      const rows = getBorderZones(f);
      return { filename, csv: toCsv(rows, borderColumns), rows: rows.length };
    }
  }
}
