// Server-side access to the generated dataset in data/. Pure functions so they can be unit tested.
import borderPeriodJson from "@/data/border_period.json";
import countryDailyJson from "@/data/country_daily.json";
import locationPeriodJson from "@/data/location_period.json";
import metadataJson from "@/data/metadata.json";
import partnerDailyJson from "@/data/partner_daily.json";
import partnerPeriodJson from "@/data/partner_period.json";
import summaryJson from "@/data/summary.json";
import type {
  Annotation, BorderPeriodRow, Country, CountryDailyRow, CountryFilter, Direction, Filters,
  LocationPeriodRow, Metadata, PartnerDailyRow, PartnerPeriodRow, Series, SummaryRow, WindowKey,
} from "./types";

export const metadata = metadataJson as unknown as Metadata;
const summary = summaryJson as unknown as SummaryRow[];
const partnerPeriod = partnerPeriodJson as unknown as PartnerPeriodRow[];
const partnerDaily = partnerDailyJson as unknown as PartnerDailyRow[];
const countryDaily = countryDailyJson as unknown as CountryDailyRow[];
const locationPeriod = locationPeriodJson as unknown as LocationPeriodRow[];
const borderPeriod = borderPeriodJson as unknown as BorderPeriodRow[];

export const DIRECTIONS: Direction[] = ["outbound", "inbound"];
export const COUNTRY_FILTERS: CountryFilter[] = ["all", "CA", "MX"];
export const WINDOWS: WindowKey[] = ["7d", "30d", "90d", "365d"];
export const COUNTRY_NAME: Record<Country, string> = { CA: "Canada", MX: "Mexico" };
export const COUNTRY_COLOR_VAR: Record<Country, string> = { CA: "var(--ca)", MX: "var(--mx)" };
export const DEFAULT_FILTERS: Filters = { direction: "outbound", country: "all", window: "30d" };

type Params = Record<string, string | string[] | undefined>;

/** Read filters from URL search params, falling back to defaults for missing or invalid values. */
export function parseFilters(params: Params): Filters {
  const one = (k: string) => (Array.isArray(params[k]) ? params[k]![0] : (params[k] as string | undefined));
  const pick = <T extends string>(v: string | undefined, allowed: readonly T[], fallback: T): T =>
    v && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
  return {
    direction: pick(one("direction"), DIRECTIONS, DEFAULT_FILTERS.direction),
    country: pick(one("country"), COUNTRY_FILTERS, DEFAULT_FILTERS.country),
    window: pick(one("window"), WINDOWS, DEFAULT_FILTERS.window),
  };
}

export const countriesFor = (c: CountryFilter): Country[] => (c === "all" ? ["CA", "MX"] : [c]);

/** Inclusive ISO date range covered by a window ending on the dataset's last day. */
export function windowRange(window: WindowKey, endDate = metadata.end_date): { start: string; end: string } {
  const end = new Date(`${endDate}T00:00:00Z`);
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - (metadata.windows[window] - 1));
  return { start: start.toISOString().slice(0, 10), end: endDate };
}

export function getSummary(f: Filters): SummaryRow {
  const country = f.country === "all" ? "ALL" : f.country;
  const row = summary.find((r) => r.direction === f.direction && r.window === f.window && r.country === country);
  if (!row) throw new Error(`No summary for ${f.direction}/${country}/${f.window}`);
  return row;
}

export interface PartnerRow extends PartnerPeriodRow {
  name: string;
  preferred: boolean;
}

export function getPartnerRows(f: Filters): PartnerRow[] {
  const allowed = countriesFor(f.country);
  return partnerPeriod
    .filter((r) => r.direction === f.direction && r.window === f.window && allowed.includes(r.country))
    .map((r) => {
      const meta = getPartnerMeta(r.partner_id)!;
      return { ...r, name: meta.name, preferred: meta.preferred };
    });
}

export const getPartnerMeta = (id: string) => metadata.partners.find((p) => p.id === id);

export function getPartnerPeriods(id: string, direction: Direction): Record<WindowKey, PartnerPeriodRow> {
  const rows = partnerPeriod.filter((r) => r.partner_id === id && r.direction === direction);
  return Object.fromEntries(rows.map((r) => [r.window, r])) as Record<WindowKey, PartnerPeriodRow>;
}

export function getPartnerDaily(id: string, direction: Direction, window: WindowKey): PartnerDailyRow[] {
  const { start } = windowRange(window);
  return partnerDaily.filter((r) => r.partner_id === id && r.direction === direction && r.date >= start);
}

export interface MapPoint {
  id: string;
  name: string;
  lat: number;
  lng: number;
  country: Country;
  value: number;
}

export function getLocations(f: Filters): MapPoint[] {
  const allowed = countriesFor(f.country);
  return locationPeriod
    .filter((r) => r.direction === f.direction && r.window === f.window && allowed.includes(r.country))
    .map((r) => {
      const loc = metadata.locations.find((l) => l.direction === r.direction && l.location_id === r.location_id)!;
      return { id: `${r.location_id}-${r.country}`, name: loc.name, lat: loc.lat, lng: loc.lng, country: r.country, value: r.unique_roamers };
    })
    .sort((a, b) => b.value - a.value);
}

export function getBorderZones(f: Filters): MapPoint[] {
  const allowed = countriesFor(f.country);
  return borderPeriod
    .filter((r) => r.direction === f.direction && r.window === f.window && allowed.includes(r.country))
    .map((r) => {
      const z = metadata.border_zones.find((b) => b.zone_id === r.zone_id)!;
      return { id: r.zone_id, name: z.name, lat: z.lat, lng: z.lng, country: r.country, value: r.events };
    })
    .sort((a, b) => b.value - a.value);
}

export type DailyMetric = "active_roamers" | "median_download_mbps" | "median_latency_ms";

/** Daily dates plus one series per selected country, for the selected window. */
export function getCountryDaily(f: Filters, metric: DailyMetric): { dates: string[]; series: Series[] } {
  const { start } = windowRange(f.window);
  const rows = countryDaily.filter((r) => r.direction === f.direction && r.date >= start);
  const dates = [...new Set(rows.map((r) => r.date))].sort();
  const series = countriesFor(f.country).map((c) => {
    const byDate = new Map(rows.filter((r) => r.country === c).map((r) => [r.date, r[metric]]));
    return { key: c, label: COUNTRY_NAME[c], colorVar: COUNTRY_COLOR_VAR[c], values: dates.map((d) => byDate.get(d) ?? 0) };
  });
  return { dates, series };
}

export function getCountryDailyRows(f: Filters): CountryDailyRow[] {
  const { start } = windowRange(f.window);
  const allowed = countriesFor(f.country);
  return countryDaily.filter((r) => r.direction === f.direction && r.date >= start && allowed.includes(r.country));
}

/**
 * Annotations to mark on charts for the window. A bounded event shows if it overlaps the
 * window; an open-ended one (upgrade, steering change) shows if it starts inside the window.
 * Holidays match on country; partner events match on the partner's country, or on the
 * partner itself when `partnerId` is given.
 */
export function getAnnotations(f: Filters, opts: { partnerId?: string; kinds?: Annotation["kind"][] } = {}): Annotation[] {
  const { start, end } = windowRange(f.window);
  const allowed = countriesFor(f.country);
  return metadata.annotations.filter((a) => {
    if (a.direction !== f.direction) return false;
    if (opts.kinds && !opts.kinds.includes(a.kind)) return false;
    if (a.start > end || (a.end ?? a.start) < start) return false;
    if (a.kind === "holiday") return a.country !== undefined && allowed.includes(a.country);
    if (opts.partnerId) return !a.partner_id || a.partner_id === opts.partnerId;
    const partnerCountry = a.partner_id ? getPartnerMeta(a.partner_id)?.country : undefined;
    return !partnerCountry || allowed.includes(partnerCountry);
  });
}
