"use client";

import type { ReactNode } from "react";
import { useTooltip } from "@/components/Tooltip";
import { spreadLabels } from "@/lib/scale";

export interface ScatterPoint {
  id: string;
  label: string;
  x: number;
  y: number;
  colorVar: string;
  tooltip: ReactNode;
}

interface Props {
  points: ScatterPoint[];
  xMax: number;
  yMax: number;
  xLabel: string;
  yLabel: string;
  corner?: string;
}

/** Scatter with direct labels on the right; every point is reachable by hover and by its label. */
export function ScatterChart({ points, xMax, yMax, xLabel, yLabel, corner }: Props) {
  const { show, hide, view } = useTooltip();
  const W = 470, H = 230, M = { l: 40, r: 112, t: 10, b: 32 };
  const iw = W - M.l - M.r, ih = H - M.t - M.b;
  const x = (v: number) => M.l + (Math.min(v, xMax) / xMax) * iw;
  const y = (v: number) => M.t + ih - (Math.min(v, yMax) / yMax) * ih;
  const labelYs = spreadLabels(points.map((p) => y(p.y) + 4), 13);
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * yMax);
  const xTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * xMax);

  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`${yLabel} versus ${xLabel}`} style={{ display: "block" }}>
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={M.l} x2={M.l + iw} y1={y(v)} y2={y(v)} style={{ stroke: v ? "var(--grid)" : "var(--axis)" }} />
            <text x={M.l - 6} y={y(v) + 4} fontSize={10} textAnchor="end" style={{ fill: "var(--muted)" }}>{Math.round(v)}</text>
          </g>
        ))}
        {xTicks.map((v) => (
          <text key={v} x={x(v)} y={M.t + ih + 14} fontSize={10} textAnchor="middle" style={{ fill: "var(--muted)" }}>{Math.round(v)}</text>
        ))}
        <line x1={M.l} x2={M.l} y1={M.t} y2={M.t + ih} style={{ stroke: "var(--axis)" }} />
        <text x={M.l + iw / 2} y={H - 2} fontSize={10.5} textAnchor="middle" style={{ fill: "var(--ink-2)" }}>{xLabel}</text>
        <text transform={`translate(11 ${M.t + ih / 2}) rotate(-90)`} fontSize={10.5} textAnchor="middle" style={{ fill: "var(--ink-2)" }}>{yLabel}</text>
        {corner && <text x={M.l + 6} y={M.t + 12} fontSize={10} style={{ fill: "var(--muted)" }}>{corner}</text>}
        {points.map((p, i) => (
          <g key={p.id}>
            <line x1={x(p.x) + 8} y1={y(p.y)} x2={M.l + iw + 5} y2={labelYs[i] - 4} style={{ stroke: "var(--grid)" }} />
            <circle cx={x(p.x)} cy={y(p.y)} r={7} strokeWidth={2} style={{ fill: p.colorVar, stroke: "var(--surface)" }} />
            <text x={M.l + iw + 8} y={labelYs[i]} fontSize={10.5} style={{ fill: "var(--ink-2)" }}>{p.label}</text>
            <circle
              cx={x(p.x)} cy={y(p.y)} r={13} fill="transparent"
              onPointerMove={(e) => show(e, p.tooltip)} onPointerLeave={hide}
            />
          </g>
        ))}
      </svg>
      {view}
    </>
  );
}
