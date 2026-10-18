"use client";

import type * as Leaflet from "leaflet";
import { useEffect, useRef, useState } from "react";
import type { MapPoint } from "@/lib/data";

// OpenStreetMap's standard tiles (usage policy: attribution, light traffic). They're tinted gray in
// CSS (.map .leaflet-tile-pane in globals.css), so one tile set works for both themes.
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

interface Props {
  points: MapPoint[];
  zones: MapPoint[];
  showZones: boolean;
  /** When this changes, the map re-fits to the points (e.g. a new direction or country). */
  fitKey: string;
  pointTooltip: (p: MapPoint) => string;
  zoneTooltip: (z: MapPoint) => string;
  onMarkerClick?: (kind: "city" | "border_zone", p: MapPoint) => void;
}

const radius = (v: number, maxV: number) => 4 + 22 * Math.sqrt(v / maxV);   // area ∝ value

export function RoamingMap({ points, zones, showZones, fitKey, pointTooltip, zoneTooltip, onMarkerClick }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<Leaflet.Map | null>(null);
  const L = useRef<typeof Leaflet | null>(null);
  const layers = useRef<{ bubbles?: Leaflet.LayerGroup; zones?: Leaflet.LayerGroup }>({});
  const lastFit = useRef("");
  const [ready, setReady] = useState(false);

  // Create the map once, in the browser only (Leaflet needs `window`).
  useEffect(() => {
    let cancelled = false;
    import("leaflet").then((mod) => {
      if (cancelled || !el.current) return;
      L.current = mod.default ?? mod;
      const m = L.current.map(el.current, { scrollWheelZoom: false, zoomSnap: 1 });
      map.current = m;
      layers.current.bubbles = L.current.layerGroup().addTo(m);
      layers.current.zones = L.current.layerGroup().addTo(m);
      L.current.tileLayer(TILES, { attribution: ATTRIBUTION, maxZoom: 10 }).addTo(m);
      setReady(true);
    });
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Redraw markers whenever the data changes.
  useEffect(() => {
    const Lf = L.current, m = map.current, { bubbles, zones: zoneLayer } = layers.current;
    if (!ready || !Lf || !m || !bubbles || !zoneLayer) return;
    bubbles.clearLayers();
    zoneLayer.clearLayers();
    const maxV = Math.max(1, ...points.map((p) => p.value));
    for (const p of points) {
      Lf.circleMarker([p.lat, p.lng], { radius: radius(p.value, maxV), weight: 2, fillOpacity: 0.82, className: `bubble-${p.country}` })
        .bindTooltip(pointTooltip(p), { direction: "top" })
        .on("click", () => onMarkerClick?.("city", p))
        .addTo(bubbles);
    }
    if (showZones) {
      const maxZ = Math.max(1, ...zones.map((z) => z.value));
      for (const z of zones) {
        const s = Math.round(8 + 14 * Math.sqrt(z.value / maxZ));
        Lf.marker([z.lat, z.lng], { icon: Lf.divIcon({ className: "", iconSize: [s, s], html: '<div class="zone"></div>' }), keyboard: true, title: z.name })
          .bindTooltip(zoneTooltip(z), { direction: "top" })
          .on("click", () => onMarkerClick?.("border_zone", z))
          .addTo(zoneLayer);
      }
    }
    if (lastFit.current !== fitKey && points.length) {
      m.fitBounds(Lf.latLngBounds([...points, ...zones].map((p) => [p.lat, p.lng] as [number, number])), { padding: [30, 30] });
      lastFit.current = fitKey;
    }
  }, [ready, points, zones, showZones, fitKey, pointTooltip, zoneTooltip, onMarkerClick]);

  return <div ref={el} className="map" role="region" aria-label="Map of roaming locations" />;
}
