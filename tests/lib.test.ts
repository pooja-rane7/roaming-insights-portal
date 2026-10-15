import { describe, expect, it } from "vitest";
import { csvField, toCsv } from "@/lib/csv";
import {
  getAnnotations, getBorderZones, getCountryDaily, getLocations, getPartnerDaily, getPartnerRows, getSummary,
  metadata, parseFilters, windowRange,
} from "@/lib/data";
import { delta, fmtCompact, fmtData } from "@/lib/format";
import { buildReport } from "@/lib/reports";
import { niceMax, spreadLabels, tickIndices } from "@/lib/scale";
import { decodeSession, encodeSession, newUserId } from "@/lib/session";
import type { Filters } from "@/lib/types";

const F: Filters = { direction: "outbound", country: "all", window: "30d" };

describe("parseFilters", () => {
  it("uses defaults for missing or invalid values", () => {
    expect(parseFilters({})).toEqual(F);
    expect(parseFilters({ direction: "sideways", country: "FR", window: "2d" })).toEqual(F);
  });
  it("accepts valid values, including repeated params", () => {
    expect(parseFilters({ direction: "inbound", country: "MX", window: ["7d", "30d"] }))
      .toEqual({ direction: "inbound", country: "MX", window: "7d" });
  });
});

describe("windowRange", () => {
  it("covers exactly N days ending on the last data day", () => {
    expect(windowRange("7d")).toEqual({ start: "2026-10-08", end: "2026-10-14" });
    expect(windowRange("365d").start).toBe(metadata.start_date);
  });
});

describe("dataset selectors", () => {
  it("summary 'all' equals Canada + Mexico unique roamers", () => {
    const all = getSummary(F).unique_roamers;
    const ca = getSummary({ ...F, country: "CA" }).unique_roamers;
    const mx = getSummary({ ...F, country: "MX" }).unique_roamers;
    expect(all).toBe(ca + mx);
  });
  it("partner rows respect the country filter and carry names", () => {
    const rows = getPartnerRows({ ...F, country: "CA" });
    expect(rows).toHaveLength(3);
    expect(rows.every((r) => r.country === "CA" && r.name.length > 0)).toBe(true);
  });
  it("daily series have one value per day in the window", () => {
    const { dates, series } = getCountryDaily(F, "active_roamers");
    expect(dates).toHaveLength(30);
    expect(series.map((s) => s.key)).toEqual(["CA", "MX"]);
    expect(series.every((s) => s.values.length === 30 && s.values.every((v) => v > 0))).toBe(true);
  });
  it("map points have coordinates and are sorted largest first", () => {
    for (const pts of [getLocations(F), getBorderZones(F)]) {
      expect(pts.length).toBeGreaterThan(0);
      expect(pts.every((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng))).toBe(true);
      expect(pts.map((p) => p.value)).toEqual([...pts.map((p) => p.value)].sort((a, b) => b - a));
    }
  });
  it("inbound locations are U.S. metros split by visitor country", () => {
    const pts = getLocations({ ...F, direction: "inbound" });
    expect(new Set(pts.map((p) => p.country))).toEqual(new Set(["CA", "MX"]));
  });
  it("partner daily returns the window for one partner and direction", () => {
    const rows = getPartnerDaily("costa", "outbound", "30d");
    expect(rows).toHaveLength(30);
    expect(rows.every((r) => r.partner_id === "costa" && r.direction === "outbound")).toBe(true);
  });
});

describe("getAnnotations", () => {
  it("shows the Costa Red incident in the last 30 days for Mexico, not Canada", () => {
    const ids = (f: Filters) => getAnnotations(f).map((a) => a.id);
    expect(ids({ ...F, country: "MX" })).toContain("costa-outage");
    expect(ids({ ...F, country: "CA" })).not.toContain("costa-outage");
  });
  it("excludes events outside the window and in the other direction", () => {
    expect(getAnnotations({ ...F, window: "7d" }).map((a) => a.id)).not.toContain("costa-outage");
    expect(getAnnotations({ ...F, direction: "inbound" }).map((a) => a.id)).not.toContain("costa-outage");
  });
  it("on a partner page, shows only that partner's events plus global ones", () => {
    const ids = getAnnotations({ ...F, window: "365d", country: "CA" }, { partnerId: "maple", kinds: ["incident", "upgrade", "steering"] }).map((a) => a.id);
    expect(ids).toContain("maplelink-upgrade");
    expect(ids).toContain("steering-policy");
    expect(ids).not.toContain("tundra-degradation");
  });
});

describe("format", () => {
  it("formats compact numbers and data sizes", () => {
    expect(fmtCompact(411498)).toBe("411.5k");
    expect(fmtCompact(2_400_000)).toBe("2.4M");
    expect(fmtCompact(42)).toBe("42");
    expect(fmtData(512)).toBe("512.0 GB");
    expect(fmtData(2048)).toBe("2.0 TB");
  });
  it("judges deltas by the metric's direction", () => {
    expect(delta(110, 100)).toEqual({ pct: 10, good: true });
    expect(delta(110, 100, false)).toEqual({ pct: 10, good: false });
    expect(delta(5, null)).toBeNull();
    expect(delta(5, 0)).toBeNull();
  });
});

describe("csv", () => {
  it("quotes fields with commas, quotes and newlines", () => {
    expect(csvField("plain")).toBe("plain");
    expect(csvField("a,b")).toBe('"a,b"');
    expect(csvField('say "hi"')).toBe('"say ""hi"""');
    expect(csvField("two\nlines")).toBe('"two\nlines"');
    expect(csvField(null)).toBe("");
  });
  it("builds a header row plus one line per row", () => {
    const csv = toCsv([{ a: 1, b: "x" }], [{ header: "a", value: (r) => r.a }, { header: "b", value: (r) => r.b }]);
    expect(csv).toBe("a,b\r\n1,x\r\n");
  });
  it("exports every report type with the expected row counts", () => {
    expect(buildReport("partner_scorecard", F).rows).toBe(6);
    expect(buildReport("daily_trend", F).rows).toBe(60);
    expect(buildReport("border_zones", { ...F, country: "CA" }).rows).toBe(4);
    expect(buildReport("partner_scorecard", F).filename).toBe("roamlens_partner_scorecard_outbound_all_30d.csv");
  });
});

describe("scale", () => {
  it("rounds axis maxima to nice numbers", () => {
    expect(niceMax(47)).toBe(60);
    expect(niceMax(51000)).toBe(60000);
    expect(niceMax(23)).toBe(30);
    expect(niceMax(1450)).toBe(1600);
    expect(niceMax(0)).toBe(1);
  });
  it("picks evenly spaced ticks including both ends", () => {
    expect(tickIndices(30)).toEqual([0, 7, 15, 22, 29]);
    expect(tickIndices(1)).toEqual([0]);
  });
  it("spreads close labels apart without reordering them", () => {
    expect(spreadLabels([10, 12, 50], 10)).toEqual([10, 20, 50]);
    expect(spreadLabels([30, 25], 10)).toEqual([35, 25]);
  });
});

describe("session", () => {
  it("round-trips a session", () => {
    const s = { userId: "meridian_analyst_abc123", accountId: "meridian", role: "analyst" as const };
    expect(decodeSession(encodeSession(s))).toEqual(s);
  });
  it("rejects missing, malformed and unknown-account cookies", () => {
    expect(decodeSession(undefined)).toBeNull();
    expect(decodeSession("not-base64-json")).toBeNull();
    expect(decodeSession(encodeSession({ userId: "x", accountId: "acme", role: "analyst" }))).toBeNull();
  });
  it("generates user ids that encode account and role", () => {
    expect(newUserId("corvalia", "manager", () => 0.5)).toMatch(/^corvalia_manager_[0-9a-z]{6}$/);
  });
});

describe("analytics", () => {
  it("maps paths to tracking-plan page names", async () => {
    const { pageName } = await import("@/lib/analytics");
    expect(pageName("/")).toBe("sign_in");
    expect(pageName("/overview")).toBe("overview");
    expect(pageName("/partners")).toBe("partners");
    expect(pageName("/partners/costa")).toBe("partner_detail");
    expect(pageName("/reports")).toBe("reports");
    expect(pageName("/alerts")).toBe("alerts");
    expect(pageName("/elsewhere")).toBe("other");
  });
});
