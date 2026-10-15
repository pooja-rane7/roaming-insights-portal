export type Direction = "outbound" | "inbound";
export type Country = "CA" | "MX";
export type CountryFilter = "all" | Country;
export type WindowKey = "7d" | "30d" | "90d" | "365d";
export type Status = "healthy" | "watch" | "critical";

export interface Filters {
  direction: Direction;
  country: CountryFilter;
  window: WindowKey;
}

export interface SummaryRow {
  direction: Direction;
  country: Country | "ALL";
  window: WindowKey;
  unique_roamers: number;
  prev_unique_roamers: number | null;
  roamer_days: number;
  data_gb: number;
  prev_data_gb: number | null;
  registration_success_pct: number;
  speed_samples: number;
  median_download_mbps: number;
  prev_median_download_mbps: number | null;
  median_upload_mbps: number;
  median_latency_ms: number;
  prev_median_latency_ms: number | null;
  pct_samples_below_5mbps: number;
  steering_to_preferred_pct: number | null;
}

export interface PartnerPeriodRow {
  direction: Direction;
  partner_id: string;
  country: Country;
  window: WindowKey;
  unique_roamers: number;
  share_of_country_pct: number;
  roamer_days: number;
  data_gb: number;
  mb_per_roamer_day: number;
  registration_success_pct: number;
  median_download_mbps: number;
  median_upload_mbps: number;
  median_latency_ms: number;
  pct_samples_below_5mbps: number;
  status: Status;
}

export interface PartnerDailyRow {
  date: string;
  direction: Direction;
  country: Country;
  partner_id: string;
  active_roamers: number;
  data_gb: number;
  registration_attempts: number;
  registration_successes: number;
  speed_samples: number;
  median_download_mbps: number;
  median_upload_mbps: number;
  median_latency_ms: number;
}

export interface CountryDailyRow {
  date: string;
  direction: Direction;
  country: Country;
  active_roamers: number;
  data_gb: number;
  registration_success_pct: number;
  speed_samples: number;
  median_download_mbps: number;
  median_upload_mbps: number;
  median_latency_ms: number;
}

export interface LocationPeriodRow {
  direction: Direction;
  location_id: string;
  country: Country;
  window: WindowKey;
  unique_roamers: number;
}

export interface BorderPeriodRow {
  direction: Direction;
  zone_id: string;
  country: Country;
  window: WindowKey;
  events: number;
}

export interface PartnerMeta {
  id: string;
  name: string;
  country: Country;
  preferred: boolean;
}

export interface LocationMeta {
  direction: Direction;
  location_id: string;
  name: string;
  lat: number;
  lng: number;
  country: Country | "US";
}

export interface BorderZoneMeta {
  zone_id: string;
  name: string;
  lat: number;
  lng: number;
  country: Country;
}

export interface Annotation {
  id: string;
  label: string;
  kind: "incident" | "upgrade" | "steering" | "holiday";
  direction: Direction;
  partner_id?: string | null;
  country?: Country;
  start: string;
  end: string | null;
}

export interface Metadata {
  disclaimer: string;
  generator_version: string;
  seed: number;
  start_date: string;
  end_date: string;
  home_operator: { id: string; name: string; country: string };
  countries: Record<Country, string>;
  windows: Record<WindowKey, number>;
  partners: PartnerMeta[];
  locations: LocationMeta[];
  border_zones: BorderZoneMeta[];
  annotations: Annotation[];
  status_rule: Record<"critical" | "watch", { reg_below: number; dl_below: number; lat_above: number }>;
  poor_speed_threshold_mbps: number;
}

/** A daily series for charts: one value per date, per country or partner. */
export interface Series {
  key: string;
  label: string;
  colorVar: string;
  values: number[];
}
