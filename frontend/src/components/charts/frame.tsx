/* Chart container: title, legend, table-view twin and a shared tooltip layer.
   Every chart ships a table view so no value is reachable only by hover or by color. */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon } from "../ui/Icon";

export const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)", "var(--series-5)",
  "var(--series-6)", "var(--series-7)", "var(--series-8)"];

export function useWidth<T extends HTMLElement>(fallback = 640) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const w = Math.floor(entries[0].contentRect.width);
      if (w > 0) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, width };
}

export interface TooltipRow {
  value: string;
  label: string;
  color?: string;
}

export interface TooltipState {
  x: number;
  y: number;
  title?: string;
  rows: TooltipRow[];
}

export function useTooltip() {
  const [tip, setTip] = useState<TooltipState | null>(null);
  return { tip, show: setTip, hide: () => setTip(null) };
}

export function Tooltip({ tip, width }: { tip: TooltipState | null; width: number }) {
  if (!tip) return null;
  const left = Math.min(Math.max(tip.x + 12, 4), Math.max(4, width - 220));
  return (
    <div className="viz-tooltip" style={{ left, top: Math.max(tip.y - 10, 0) }} role="status">
      {tip.title && <div className="viz-tooltip-title">{tip.title}</div>}
      {tip.rows.map((r, i) => (
        <div key={i} className="viz-tooltip-row">
          {r.color && <span className="viz-key" style={{ background: r.color }} />}
          <strong>{r.value}</strong>
          <span>{r.label}</span>
        </div>
      ))}
    </div>
  );
}

export function Legend({ items, shape = "rect" }: { items: { label: string; color: string }[]; shape?: "rect" | "line" }) {
  if (items.length < 2) return null;
  return (
    <ul className="viz-legend" aria-label="Legend">
      {items.map((it) => (
        <li key={it.label}>
          <span className={shape === "line" ? "viz-legend-line" : "viz-legend-rect"} style={{ background: it.color }} />
          {it.label}
        </li>
      ))}
    </ul>
  );
}

export interface TableData {
  columns: string[];
  rows: (string | number)[][];
}

export function ChartFrame({ title, subtitle, legend, table, summary, children, width, tip }: {
  title: string; subtitle?: ReactNode; legend?: ReactNode; table: TableData; summary: string; children: ReactNode;
  width: number; tip: TooltipState | null;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure className="viz" aria-label={title}>
      <figcaption className="viz-head">
        <div>
          <div className="viz-title">{title}</div>
          {subtitle && <div className="viz-sub">{subtitle}</div>}
        </div>
        <button className="btn ghost sm" onClick={() => setShowTable((v) => !v)} aria-pressed={showTable}>
          <Icon name={showTable ? "chart" : "table"} size={14} />
          {showTable ? "Chart" : "Table"}
        </button>
      </figcaption>
      {legend}
      {showTable ? (
        <div className="table-wrap" style={{ marginTop: 8 }}>
          <table className="table">
            <thead>
              <tr>{table.columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{typeof v === "number" ? v.toLocaleString("en-US", { maximumFractionDigits: 3 }) : v}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="viz-plot" role="img" aria-label={summary}>
          {children}
          <Tooltip tip={tip} width={width} />
        </div>
      )}
    </figure>
  );
}

/** Horizontal bar path with a 4px rounded data end and a square baseline end. */
export function hBar(x0: number, x1: number, y: number, h: number, r = 4): string {
  const w = Math.abs(x1 - x0);
  const rr = Math.min(r, w, h / 2);
  if (w < 0.5) return "";
  if (x1 >= x0) {
    return `M${x0},${y}H${x1 - rr}Q${x1},${y} ${x1},${y + rr}V${y + h - rr}Q${x1},${y + h} ${x1 - rr},${y + h}H${x0}Z`;
  }
  return `M${x0},${y}H${x1 + rr}Q${x1},${y} ${x1},${y + rr}V${y + h - rr}Q${x1},${y + h} ${x1 + rr},${y + h}H${x0}Z`;
}

/** Vertical column path with a rounded data end (top for positive values). */
export function vBar(x: number, w: number, y0: number, y1: number, r = 4): string {
  const h = Math.abs(y1 - y0);
  const rr = Math.min(r, h, w / 2);
  if (h < 0.5) return "";
  if (y1 <= y0) {
    return `M${x},${y0}V${y1 + rr}Q${x},${y1} ${x + rr},${y1}H${x + w - rr}Q${x + w},${y1} ${x + w},${y1 + rr}V${y0}Z`;
  }
  return `M${x},${y0}V${y1 - rr}Q${x},${y1} ${x + rr},${y1}H${x + w - rr}Q${x + w},${y1} ${x + w},${y1 - rr}V${y0}Z`;
}

export function textWidth(text: string, size = 11): number {
  return text.length * size * 0.56;
}
