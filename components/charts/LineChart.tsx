"use client";

import { useRef, useState } from "react";
import { Swatch, useTooltip } from "@/components/Tooltip";
import { fmtCompact, fmtDay, fmtDayYear, fmtMonthYear } from "@/lib/format";
import { niceMax, spreadLabels, tickIndices } from "@/lib/scale";
import type { Annotation, Series } from "@/lib/types";

interface Props {
  title: string;
  caption: string;
  dates: string[];
  series: Series[];
  annotations?: Annotation[];
  unit?: string;
  decimals?: number;
  yMax?: number;
  width?: number;
  chartId: string;
}

const H_RATIO = 0.4;
const M = { l: 44, r: 92, t: 18, b: 24 };

/** Single-axis daily line chart with crosshair tooltip, direct end labels, event markers and a table view. */
export function LineChart({ title, caption, dates, series, annotations = [], unit = "", decimals = 0, yMax, width = 470, chartId }: Props) {
  const [asTable, setAsTable] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const { show, hide, view } = useTooltip();

  const W = width, H = Math.round(W * H_RATIO);
  const iw = W - M.l - M.r, ih = H - M.t - M.b;
  const n = dates.length;
  const max = yMax ?? niceMax(Math.max(1, ...series.flatMap((s) => s.values)));
  const x = (i: number) => M.l + (n > 1 ? (i / (n - 1)) * iw : iw / 2);
  const y = (v: number) => M.t + ih - (v / max) * ih;
  const fmt = (v: number) => (decimals ? v.toFixed(decimals) : fmtCompact(v));
  const fmtFull = (v: number) => (decimals ? v.toFixed(decimals) : Math.round(v).toLocaleString("en-US"));
  const longRange = n > 120;

  const marks = annotations.map((a, k) => {
    const i = Math.max(0, dates.indexOf(a.start) === -1 ? (a.start < dates[0] ? 0 : n - 1) : dates.indexOf(a.start));
    return { a, i, n: k + 1 };
  });
  const endYs = spreadLabels(series.map((s) => y(s.values[n - 1] ?? 0) + 4), 13);

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM()!.inverse());
    const i = Math.max(0, Math.min(n - 1, Math.round(((p.x - M.l) / iw) * (n - 1))));
    setHover(i);
    const here = marks.filter((m) => m.i === i);
    show(e, (
      <>
        <b>{fmtDayYear(dates[i])}</b>
        {series.map((s) => (
          <div key={s.key}><Swatch colorVar={s.colorVar} />{s.label}: {fmtFull(s.values[i])}{unit}</div>
        ))}
        {here.map((m) => <div key={m.a.id} style={{ marginTop: 4 }}>⚑ {m.a.label}</div>)}
      </>
    ));
  }

  return (
    <div className="card">
      <h3>{title}</h3>
      <div className="cap">
        {caption}{" "}
        <button className="linkish" onClick={() => setAsTable((v) => !v)} data-chart-id={chartId}>
          {asTable ? "View as chart" : "View as table"}
        </button>
      </div>
      {series.length > 1 && (
        <div className="legend">
          {series.map((s) => <span key={s.key}><span className="sw" style={{ background: s.colorVar }} />{s.label}</span>)}
        </div>
      )}
      {asTable ? (
        <div className="tableview">
          <table>
            <thead><tr><th>Date</th>{series.map((s) => <th key={s.key} className="num">{s.label}{unit && ` (${unit.trim()})`}</th>)}</tr></thead>
            <tbody>
              {dates.map((d, i) => (
                <tr key={d}><td>{fmtDayYear(d)}</td>{series.map((s) => <td key={s.key} className="num">{fmtFull(s.values[i])}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`${title}. ${caption}`} style={{ display: "block" }}>
          {[0, 0.25, 0.5, 0.75, 1].map((f) => (
            <g key={f}>
              <line x1={M.l} x2={M.l + iw} y1={y(max * f)} y2={y(max * f)} style={{ stroke: f === 0 ? "var(--axis)" : "var(--grid)" }} />
              <text x={M.l - 6} y={y(max * f) + 4} fontSize={10} textAnchor="end" style={{ fill: "var(--muted)" }}>{fmt(max * f)}</text>
            </g>
          ))}
          {tickIndices(n).map((i) => (
            <text key={i} x={x(i)} y={H - 6} fontSize={10} textAnchor="middle" style={{ fill: "var(--muted)" }}>
              {longRange ? fmtMonthYear(dates[i]) : fmtDay(dates[i])}
            </text>
          ))}
          {marks.map((m) => (
            <g key={m.a.id}>
              <line x1={x(m.i)} x2={x(m.i)} y1={M.t} y2={M.t + ih} style={{ stroke: "var(--axis)" }} />
              <circle cx={x(m.i)} cy={M.t - 8} r={7} style={{ fill: "var(--axis)" }} />
              <text x={x(m.i)} y={M.t - 5} fontSize={9} fontWeight={600} textAnchor="middle" style={{ fill: "var(--ink)" }}>{m.n}</text>
            </g>
          ))}
          {series.map((s, si) => (
            <g key={s.key}>
              <path
                d={s.values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join("")}
                fill="none" strokeWidth={longRange ? 1.5 : 2} strokeLinejoin="round" style={{ stroke: s.colorVar }}
              />
              <text x={x(n - 1) + 6} y={endYs[si]} fontSize={11} style={{ fill: "var(--ink-2)" }}>{s.label} {fmt(s.values[n - 1])}</text>
            </g>
          ))}
          {hover !== null && (
            <g>
              <line x1={x(hover)} x2={x(hover)} y1={M.t} y2={M.t + ih} style={{ stroke: "var(--ink-2)" }} />
              {series.map((s) => (
                <circle key={s.key} cx={x(hover)} cy={y(s.values[hover])} r={4} strokeWidth={2} style={{ fill: s.colorVar, stroke: "var(--surface)" }} />
              ))}
            </g>
          )}
          <rect
            x={M.l} y={M.t} width={iw} height={ih} fill="transparent"
            onPointerMove={onMove} onPointerLeave={() => { setHover(null); hide(); }}
          />
        </svg>
      )}
      {marks.length > 0 && (
        <ul className="events">
          {marks.map((m) => (
            <li key={m.a.id}>
              <span className="n">{m.n}</span>{m.a.label} · {fmtDay(m.a.start)}{m.a.end && m.a.end !== m.a.start ? `–${fmtDay(m.a.end)}` : m.a.end === null ? " onward" : ""}
            </li>
          ))}
        </ul>
      )}
      {view}
    </div>
  );
}
