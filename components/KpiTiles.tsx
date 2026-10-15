import type { Delta } from "@/lib/format";

export interface Kpi {
  label: string;
  value: string;
  /** Change vs. the previous period, or a short note when there's no comparison. */
  delta?: Delta | null;
  note?: string;
}

export function KpiTiles({ items }: { items: Kpi[] }) {
  return (
    <div className={`kpis${items.length === 4 ? " four" : ""}`}>
      {items.map((k) => (
        <div className="card kpi" key={k.label}>
          <div className="k">{k.label}</div>
          <div className="v">{k.value}</div>
          <div className="d">
            {k.delta ? (
              <>
                <span className={k.delta.good ? "up" : "down"}>
                  {k.delta.pct >= 0 ? "▲" : "▼"} {Math.abs(k.delta.pct).toFixed(1)}%
                </span>{" "}
                vs. previous period
              </>
            ) : (
              k.note ?? "No earlier period to compare"
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
