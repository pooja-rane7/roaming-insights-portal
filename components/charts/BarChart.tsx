"use client";

import type { ReactNode } from "react";
import { useTooltip } from "@/components/Tooltip";
import { niceMax } from "@/lib/scale";

export interface Bar {
  id: string;
  label: string;
  value: number;
  colorVar: string;
  tooltip: ReactNode;
}

/** Horizontal bars, 4px rounded data end, value labels outside the bar end. */
export function BarChart({ bars, format = (v: number) => `${Math.round(v)}` }: { bars: Bar[]; format?: (v: number) => string }) {
  const { show, hide, view } = useTooltip();
  const W = 620, rowH = 30, M = { l: 128, r: 52, t: 4 };
  const H = M.t + bars.length * rowH + 6;
  const iw = W - M.l - M.r;
  const max = niceMax(Math.max(1, ...bars.map((b) => b.value)));

  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Bar chart" style={{ display: "block" }}>
        <line x1={M.l} x2={M.l} y1={M.t} y2={H - 4} style={{ stroke: "var(--axis)" }} />
        {bars.map((b, i) => {
          const yy = M.t + i * rowH + 6, h = rowH - 12, w = Math.max(4, (b.value / max) * iw);
          return (
            <g key={b.id}>
              <text x={M.l - 8} y={yy + h / 2 + 4} fontSize={11.5} textAnchor="end" style={{ fill: "var(--ink-2)" }}>{b.label}</text>
              <path d={`M${M.l} ${yy} H${M.l + w - 4} a4 4 0 0 1 4 4 V${yy + h - 4} a4 4 0 0 1 -4 4 H${M.l} Z`} style={{ fill: b.colorVar }} />
              <text x={M.l + w + 6} y={yy + h / 2 + 4} fontSize={11} style={{ fill: "var(--ink)" }}>{format(b.value)}</text>
              <rect
                x={0} y={M.t + i * rowH} width={W} height={rowH} fill="transparent"
                onPointerMove={(e) => show(e, b.tooltip)} onPointerLeave={hide}
              />
            </g>
          );
        })}
      </svg>
      {view}
    </>
  );
}
