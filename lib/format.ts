export function fmtCompact(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(n / 1e3).toFixed(1)}k`;
  return `${Math.round(n)}`;
}

export const fmtInt = (n: number) => Math.round(n).toLocaleString("en-US");

export function fmtData(gb: number): string {
  if (gb >= 1024 * 1024) return `${(gb / 1024 / 1024).toFixed(2)} PB`;
  if (gb >= 1024) return `${(gb / 1024).toFixed(1)} TB`;
  return `${gb.toFixed(1)} GB`;
}

export function fmtDay(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

export function fmtDayYear(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
}

/** "Oct ’25": month plus two-digit year, for long date ranges. */
export function fmtMonthYear(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return `${d.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" })} ’${String(d.getUTCFullYear()).slice(2)}`;
}

export interface Delta {
  pct: number;
  /** Whether the change is good news, given the metric's direction. */
  good: boolean;
}

/** Percent change vs. the previous period; null when there's nothing to compare against. */
export function delta(current: number, previous: number | null | undefined, higherIsBetter = true): Delta | null {
  if (previous === null || previous === undefined || previous === 0) return null;
  const pct = ((current - previous) / previous) * 100;
  return { pct, good: higherIsBetter ? pct >= 0 : pct <= 0 };
}

export const WINDOW_LABEL: Record<string, string> = {
  "7d": "Last 7 days", "30d": "Last 30 days", "90d": "Last 90 days", "365d": "Last 12 months",
};
