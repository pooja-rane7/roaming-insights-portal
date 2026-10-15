"use client";

import { useFeatureFlagEnabled } from "@posthog/react";
import { useEffect, useState } from "react";
import { track } from "@/lib/analytics";
import type { PartnerMeta } from "@/lib/types";

const METRICS = [
  { id: "median_download_mbps", label: "Median download falls below", unit: "Mbps", default: 10 },
  { id: "median_latency_ms", label: "Median latency rises above", unit: "ms", default: 120 },
  { id: "registration_success_pct", label: "Registration success falls below", unit: "%", default: 95 },
];

interface Alert {
  id: string;
  partner_id: string;
  metric: string;
  threshold: number;
}

/** Alerts page, shown only when the `alerts-beta` feature flag is on for this user. */
export function AlertsBeta({ partners, storageKey }: { partners: PartnerMeta[]; storageKey: string }) {
  const enabled = useFeatureFlagEnabled("alerts-beta");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [metric, setMetric] = useState(METRICS[0].id);

  useEffect(() => {
    try { setAlerts(JSON.parse(localStorage.getItem(storageKey) ?? "[]")); } catch { setAlerts([]); }
  }, [storageKey]);

  if (enabled === undefined) return <div className="card empty">Loading…</div>;
  if (!enabled) {
    return (
      <div className="card empty">
        Alerts is in private beta. Ask your RoamLens customer success manager for access.
      </div>
    );
  }

  const m = METRICS.find((x) => x.id === metric)!;

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const alert: Alert = {
      id: crypto.randomUUID(),
      partner_id: String(d.get("partner")),
      metric: String(d.get("metric")),
      threshold: Number(d.get("threshold")),
    };
    const next = [...alerts, alert];
    setAlerts(next);
    localStorage.setItem(storageKey, JSON.stringify(next));
    track("alert_created", { metric: alert.metric, threshold: alert.threshold, partner_id: alert.partner_id });
  }

  return (
    <div className="grid2 even">
      <form className="card" onSubmit={onSubmit}>
        <h3>New alert</h3>
        <div className="cap">Get notified when a partner&apos;s daily metric crosses a threshold. (Demo: alerts are saved in this browser only.)</div>
        <div className="filters" style={{ flexDirection: "column", alignItems: "stretch" }}>
          <label>Partner{" "}
            <select name="partner" className="btn">
              {partners.map((p) => <option key={p.id} value={p.id}>{p.name} ({p.country})</option>)}
            </select>
          </label>
          <label>When{" "}
            <select name="metric" className="btn" value={metric} onChange={(e) => setMetric(e.target.value)}>
              {METRICS.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
            </select>
          </label>
          <label>Threshold ({m.unit}){" "}
            <input key={m.id} name="threshold" type="number" step="0.1" defaultValue={m.default} className="btn" required />
          </label>
        </div>
        <button type="submit" className="btn primary">Create alert</button>
      </form>
      <div className="card">
        <h3>Your alerts</h3>
        {alerts.length === 0 ? (
          <div className="empty">No alerts yet.</div>
        ) : (
          <table>
            <thead><tr><th>Partner</th><th>Condition</th></tr></thead>
            <tbody>
              {alerts.map((a) => {
                const mm = METRICS.find((x) => x.id === a.metric);
                return (
                  <tr key={a.id}>
                    <td>{partners.find((p) => p.id === a.partner_id)?.name ?? a.partner_id}</td>
                    <td>{mm?.label} {a.threshold} {mm?.unit}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
