"use client";

import { useCallback, useState } from "react";
import { RoamingMap } from "@/components/RoamingMap";
import { track } from "@/lib/analytics";
import type { MapPoint } from "@/lib/data";
import { fmtInt } from "@/lib/format";
import type { Direction } from "@/lib/types";

const COUNTRY = { CA: "Canada", MX: "Mexico" } as const;

interface Props {
  direction: Direction;
  windowLabel: string;
  points: MapPoint[];
  zones: MapPoint[];
  fitKey: string;
}

export function MapCard({ direction, windowLabel, points, zones, fitKey }: Props) {
  const [showZones, setShowZones] = useState(true);
  const out = direction === "outbound";

  const pointTooltip = useCallback(
    (p: MapPoint) => out
      ? `<b>${p.name}</b>, ${COUNTRY[p.country]}<br>${fmtInt(p.value)} unique roamers`
      : `<b>${p.name}</b>, USA<br>${fmtInt(p.value)} unique visitors from ${COUNTRY[p.country]}`,
    [out],
  );
  const zoneTooltip = useCallback(
    (z: MapPoint) => `<b>${z.name}</b> border zone<br>${fmtInt(z.value)} cross-border registrations<br>${
      out ? `Our devices attaching to ${COUNTRY[z.country]} networks` : `${COUNTRY[z.country]} devices attaching to our network`}`,
    [out],
  );

  const onMarkerClick = useCallback(
    (kind: "city" | "border_zone", p: MapPoint) =>
      track("map_marker_clicked", { location_type: kind, country_code: p.country, direction, location_name: p.name }),
    [direction],
  );

  return (
    <div className="card">
      <h3>{out ? "Where our subscribers roam" : "Where visitors use our network"}</h3>
      <div className="cap">
        {out ? "Unique roamers by location" : "Unique visiting devices by U.S. metro and home country"}, {windowLabel.toLowerCase()}. Bubble area ∝ count. Hover for details.
      </div>
      <RoamingMap
        points={points} zones={zones} showZones={showZones} fitKey={fitKey}
        pointTooltip={pointTooltip} zoneTooltip={zoneTooltip} onMarkerClick={onMarkerClick}
      />
      <div className="maplegend">
        <span><span className="sw" style={{ background: "var(--ca)" }} />Canada</span>
        <span><span className="sw" style={{ background: "var(--mx)" }} />Mexico</span>
        <label>
          <input type="checkbox" checked={showZones} onChange={(e) => { setShowZones(e.target.checked); track("border_layer_toggled", { is_enabled: e.target.checked }); }} />{" "}
          <span className="sw sq" style={{ background: "var(--ink-2)" }} />Border-zone hotspots
        </label>
      </div>
    </div>
  );
}
