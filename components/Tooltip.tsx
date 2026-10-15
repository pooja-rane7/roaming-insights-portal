"use client";

import { useCallback, useState, type ReactNode } from "react";

interface TipState {
  x: number;
  y: number;
  content: ReactNode;
}

/** Shared hover tooltip: charts call show() on pointer move and hide() on leave. */
export function useTooltip() {
  const [tip, setTip] = useState<TipState | null>(null);
  const show = useCallback((e: { clientX: number; clientY: number }, content: ReactNode) => {
    setTip({ x: e.clientX, y: e.clientY, content });
  }, []);
  const hide = useCallback(() => setTip(null), []);
  const view = tip ? (
    <div className="tip" role="status" style={{ left: tip.x + 14, top: tip.y + 14 }}>
      {tip.content}
    </div>
  ) : null;
  return { show, hide, view };
}

export function Swatch({ colorVar }: { colorVar: string }) {
  return <span className="tsw" style={{ background: colorVar }} />;
}
