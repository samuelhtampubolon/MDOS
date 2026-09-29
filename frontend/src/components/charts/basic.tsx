/* Bar, line, histogram, coefficient and scatter charts (hand-built SVG, d3 scales only). */

import { max, min } from "d3-array";
import { scaleBand, scaleLinear, scaleLog } from "d3-scale";
import { curveMonotoneX, line } from "d3-shape";
import { useMemo } from "react";
import { money, num, pct } from "../../lib/format";
import { ChartFrame, hBar, Legend, SERIES, textWidth, useTooltip, useWidth, vBar } from "./frame";

export type Fmt = "percent" | "number" | "money" | "decimal";

export function fmtValue(v: number | null | undefined, fmt: Fmt, currency = "IDR"): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "n/a";
  if (fmt === "percent") return pct(v, Math.abs(v) < 0.1 ? 1 : 0);
  if (fmt === "money") return money(v, currency, { compact: Math.abs(v) >= 1e5 });
  if (fmt === "decimal") return num(v, 2);
  return Math.abs(v) >= 1000 ? num(v) : num(v, Math.abs(v) < 10 ? 2 : 1);
}

/* ---------- Horizontal bar chart (single series, optional interval whiskers) ---------- */

export function BarChart({ title, subtitle, data, fmt = "number", currency = "IDR", color = SERIES[0] }: {
  title: string; subtitle?: string; data: { label: string; value: number | null; low?: number | null; high?: number | null }[];
  fmt?: Fmt; currency?: string; color?: string;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const rows = data.filter((d) => d.value !== null && Number.isFinite(d.value as number)) as
    { label: string; value: number; low?: number | null; high?: number | null }[];
  const labelW = Math.min(200, Math.max(60, ...rows.map((r) => textWidth(r.label, 11) + 8)));
  const band = 30;
  const height = rows.length * band + 24;
  const lo = Math.min(0, min(rows, (r) => Math.min(r.value, r.low ?? r.value)) ?? 0);
  const hi = Math.max(0, max(rows, (r) => Math.max(r.value, r.high ?? r.value)) ?? 1);
  const x = scaleLinear().domain([lo, hi === lo ? lo + 1 : hi]).nice().range([labelW, Math.max(labelW + 40, width - 56)]);
  const barH = Math.min(24, band - 10);
  const ticks = x.ticks(4);
  const summary = `${title}: ${rows.map((r) => `${r.label} ${fmtValue(r.value, fmt, currency)}`).join(", ")}`;
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} summary={summary} width={width} tip={tip}
        table={{ columns: ["Category", "Value", ...(rows.some((r) => r.low != null) ? ["Low", "High"] : [])],
          rows: rows.map((r) => [r.label, fmtValue(r.value, fmt, currency), ...(r.low != null ? [fmtValue(r.low, fmt, currency), fmtValue(r.high ?? null, fmt, currency)] : [])]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">
            {ticks.map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={0} y2={height - 20} />)}
          </g>
          <g className="viz-axis">
            {ticks.map((t) => <text key={t} x={x(t)} y={height - 6} textAnchor="middle">{fmtValue(t, fmt, currency)}</text>)}
          </g>
          {rows.map((r, i) => {
            const y = i * band + (band - barH) / 2;
            const label = fmtValue(r.value, fmt, currency);
            const end = x(r.value);
            return (
              <g key={r.label + i} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: r.label,
                rows: [{ value: label, label: r.low != null ? `95% CI ${fmtValue(r.low, fmt, currency)} to ${fmtValue(r.high ?? null, fmt, currency)}` : title, color }] })}
                onPointerLeave={hide}>
                <rect className="viz-hit" x={0} y={i * band} width={width} height={band} />
                <text className="viz-label" x={labelW - 8} y={y + barH / 2 + 4} textAnchor="end">
                  {r.label.length > 30 ? `${r.label.slice(0, 29)}…` : r.label}
                </text>
                <path className="viz-mark" d={hBar(x(0), end, y, barH)} style={{ fill: color }} />
                {r.low != null && r.high != null && (
                  <g style={{ stroke: "var(--text-secondary)" }}>
                    <line x1={x(r.low)} x2={x(r.high)} y1={y + barH / 2} y2={y + barH / 2} strokeWidth={1} />
                    <line x1={x(r.low)} x2={x(r.low)} y1={y + barH / 2 - 4} y2={y + barH / 2 + 4} strokeWidth={1} />
                    <line x1={x(r.high)} x2={x(r.high)} y1={y + barH / 2 - 4} y2={y + barH / 2 + 4} strokeWidth={1} />
                  </g>
                )}
                <text className="viz-value" x={Math.max(end, x(r.high ?? r.value)) + 6} y={y + barH / 2 + 4}>{label}</text>
              </g>
            );
          })}
          <line className="viz-baseline" x1={x(0)} x2={x(0)} y1={0} y2={height - 20} />
        </svg>
      </ChartFrame>
    </div>
  );
}

/* ---------- Multi-series line chart with crosshair tooltip ---------- */

export interface LineSeries {
  name: string;
  points: { x: number; y: number | null }[];
  color?: string;
}

export function LineChart({ title, subtitle, series, xFmt = "number", yFmt = "number", currency = "IDR", markers = [],
  yDomain, height = 260, xLabel, area = false, zeroLine = false }: {
  title: string; subtitle?: string; series: LineSeries[]; xFmt?: Fmt; yFmt?: Fmt; currency?: string;
  markers?: { x: number; label: string }[]; yDomain?: [number, number]; height?: number; xLabel?: string; area?: boolean;
  zeroLine?: boolean;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const colored = series.map((s, i) => ({ ...s, color: s.color ?? SERIES[i % SERIES.length] }));
  const allX = colored.flatMap((s) => s.points.map((p) => p.x));
  const allY = colored.flatMap((s) => s.points.map((p) => p.y)).filter((v): v is number => v !== null && Number.isFinite(v));
  const endLabelW = colored.length > 1 ? Math.min(130, Math.max(...colored.map((s) => textWidth(s.name) + 14))) : 12;
  const margin = { l: 52, r: endLabelW, t: 10, b: xLabel ? 38 : 26 };
  const x = scaleLinear().domain([min(allX) ?? 0, max(allX) ?? 1]).range([margin.l, Math.max(margin.l + 60, width - margin.r)]);
  const y = scaleLinear().domain(yDomain ?? [Math.min(0, min(allY) ?? 0), max(allY) ?? 1]).nice().range([height - margin.b, margin.t]);
  const xs = useMemo(() => Array.from(new Set(allX)).sort((a, b) => a - b), [allX.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const gen = line<{ x: number; y: number | null }>().defined((p) => p.y !== null && Number.isFinite(p.y as number))
    .x((p) => x(p.x)).y((p) => y(p.y as number)).curve(curveMonotoneX);
  const areaPath = (pts: { x: number; y: number | null }[]) => {
    const valid = pts.filter((p) => p.y !== null);
    if (!valid.length) return "";
    const top = valid.map((p, i) => `${i ? "L" : "M"}${x(p.x)},${y(p.y as number)}`).join("");
    return `${top}L${x(valid[valid.length - 1].x)},${y(Math.max(y.domain()[0], 0))}L${x(valid[0].x)},${y(Math.max(y.domain()[0], 0))}Z`;
  };
  const onMove = (e: React.PointerEvent<SVGRectElement>) => {
    const px = e.nativeEvent.offsetX;
    const xv = x.invert(px);
    let nearest = xs[0];
    for (const v of xs) if (Math.abs(v - xv) < Math.abs(nearest - xv)) nearest = v;
    show({ x: x(nearest), y: e.nativeEvent.offsetY, title: fmtValue(nearest, xFmt, currency),
      rows: colored.map((s) => ({ value: fmtValue(s.points.find((p) => p.x === nearest)?.y ?? null, yFmt, currency), label: s.name, color: s.color })) });
  };
  const hovered = tip ? x.invert(tip.x) : null;
  const yTicks = y.ticks(5);
  const xTicks = x.ticks(Math.max(2, Math.floor(width / 110)));
  const summary = `${title}. ${colored.map((s) => s.name).join(", ")}.`;
  const lastPoints = colored.map((s) => {
    const valid = s.points.filter((p) => p.y !== null);
    return { s, p: valid[valid.length - 1] };
  });
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} summary={summary} width={width} tip={tip}
        legend={<Legend shape="line" items={colored.map((s) => ({ label: s.name, color: s.color }))} />}
        table={{ columns: [xLabel ?? "x", ...colored.map((s) => s.name)],
          rows: xs.map((xv) => [fmtValue(xv, xFmt, currency), ...colored.map((s) => fmtValue(s.points.find((p) => p.x === xv)?.y ?? null, yFmt, currency))]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">{yTicks.map((t) => <line key={t} x1={margin.l} x2={width - margin.r} y1={y(t)} y2={y(t)} />)}</g>
          <g className="viz-axis">
            {yTicks.map((t) => <text key={t} x={margin.l - 6} y={y(t) + 4} textAnchor="end">{fmtValue(t, yFmt, currency)}</text>)}
            {xTicks.map((t) => <text key={t} x={x(t)} y={height - margin.b + 16} textAnchor="middle">{fmtValue(t, xFmt, currency)}</text>)}
            {xLabel && <text x={(margin.l + width - margin.r) / 2} y={height - 4} textAnchor="middle">{xLabel}</text>}
          </g>
          <line className="viz-baseline" x1={margin.l} x2={width - margin.r} y1={height - margin.b} y2={height - margin.b} />
          {zeroLine && y.domain()[0] < 0 && <line className="viz-baseline" x1={margin.l} x2={width - margin.r} y1={y(0)} y2={y(0)} />}
          {markers.map((m) => (
            <g key={m.label}>
              <line x1={x(m.x)} x2={x(m.x)} y1={margin.t} y2={height - margin.b} style={{ stroke: "var(--text-muted)" }} strokeWidth={1} />
              <text className="viz-label" x={x(m.x) + 3} y={margin.t + 10}>{m.label}</text>
            </g>
          ))}
          {colored.map((s) => (
            <g key={s.name}>
              {area && colored.length === 1 && <path d={areaPath(s.points)} style={{ fill: s.color, opacity: 0.1 }} />}
              <path d={gen(s.points) ?? ""} fill="none" style={{ stroke: s.color }} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            </g>
          ))}
          {colored.length > 1 && lastPoints.map(({ s, p }) => p && (
            <text key={s.name} className="viz-value" x={x(p.x) + 6} y={y(p.y as number) + 4}>{s.name}</text>
          ))}
          {hovered !== null && tip && (
            <g>
              <line x1={tip.x} x2={tip.x} y1={margin.t} y2={height - margin.b} style={{ stroke: "var(--axis)" }} />
              {colored.map((s) => {
                const p = s.points.reduce((best, q) => (Math.abs(q.x - hovered) < Math.abs(best.x - hovered) ? q : best), s.points[0]);
                return p && p.y !== null ? <circle key={s.name} cx={x(p.x)} cy={y(p.y)} r={4} style={{ fill: s.color, stroke: "var(--surface-1)" }} strokeWidth={2} /> : null;
              })}
            </g>
          )}
          <rect className="viz-hit" x={margin.l} y={margin.t} width={Math.max(0, width - margin.l - margin.r)} height={height - margin.t - margin.b}
            onPointerMove={onMove} onPointerLeave={hide} />
        </svg>
      </ChartFrame>
    </div>
  );
}

/* ---------- Histogram (Monte Carlo distribution) ---------- */

export function Histogram({ title, subtitle, bins, markers = [], fmt = "money", currency = "IDR" }: {
  title: string; subtitle?: string; bins: { x0: number; x1: number; count: number }[]; markers?: { x: number; label: string }[];
  fmt?: Fmt; currency?: string;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const height = 220;
  const m = { l: 40, r: 12, t: 16, b: 26 };
  const x = scaleLinear().domain([bins[0]?.x0 ?? 0, bins[bins.length - 1]?.x1 ?? 1]).range([m.l, width - m.r]);
  const y = scaleLinear().domain([0, max(bins, (b) => b.count) ?? 1]).nice().range([height - m.b, m.t]);
  const total = bins.reduce((a, b) => a + b.count, 0) || 1;
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip}
        summary={`${title}. ${markers.map((mk) => `${mk.label} ${fmtValue(mk.x, fmt, currency)}`).join(", ")}`}
        table={{ columns: ["From", "To", "Runs", "Share"], rows: bins.map((b) => [fmtValue(b.x0, fmt, currency), fmtValue(b.x1, fmt, currency), b.count, pct(b.count / total, 1)]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">{y.ticks(4).map((t) => <line key={t} x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} />)}</g>
          <g className="viz-axis">
            {y.ticks(4).map((t) => <text key={t} x={m.l - 6} y={y(t) + 4} textAnchor="end">{t}</text>)}
            {x.ticks(4).map((t) => <text key={t} x={x(t)} y={height - 8} textAnchor="middle">{fmtValue(t, fmt, currency)}</text>)}
          </g>
          {bins.map((b, i) => {
            const bx = x(b.x0) + 1;
            const bw = Math.max(1, x(b.x1) - x(b.x0) - 2);
            return (
              <g key={i} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: `${fmtValue(b.x0, fmt, currency)} to ${fmtValue(b.x1, fmt, currency)}`,
                rows: [{ value: `${b.count} runs`, label: pct(b.count / total, 1), color: b.x1 <= 0 ? "var(--div-neg)" : "var(--series-1)" }] })} onPointerLeave={hide}>
                <rect className="viz-hit" x={bx - 1} y={m.t} width={bw + 2} height={height - m.t - m.b} />
                <path d={vBar(bx, bw, y(0), y(b.count), 2)} style={{ fill: b.x1 <= 0 ? "var(--div-neg)" : "var(--series-1)" }} />
              </g>
            );
          })}
          <line className="viz-baseline" x1={m.l} x2={width - m.r} y1={y(0)} y2={y(0)} />
          {markers.map((mk) => (
            <g key={mk.label}>
              <line x1={x(mk.x)} x2={x(mk.x)} y1={m.t - 4} y2={height - m.b} style={{ stroke: "var(--text-primary)" }} strokeWidth={1} />
              <text className="viz-strong" x={x(mk.x)} y={m.t - 6} textAnchor="middle">{mk.label}</text>
            </g>
          ))}
        </svg>
      </ChartFrame>
    </div>
  );
}

/* ---------- Coefficient plot (estimates with intervals) ---------- */

export function CoefficientPlot({ title, subtitle, data, reference = 0, logScale = false }: {
  title: string; subtitle?: string; data: { label: string; value: number | null; low?: number | null; high?: number | null; p?: number }[];
  reference?: number; logScale?: boolean;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const rows = data.filter((d) => d.value !== null) as { label: string; value: number; low?: number | null; high?: number | null; p?: number }[];
  const labelW = Math.min(220, Math.max(80, ...rows.map((r) => textWidth(r.label) + 10)));
  const band = 30;
  const height = rows.length * band + 26;
  const vals = rows.flatMap((r) => [r.value, r.low ?? r.value, r.high ?? r.value, reference]);
  const lo = min(vals) ?? 0;
  const hi = max(vals) ?? 1;
  const x = logScale
    ? scaleLog().domain([Math.max(1e-3, lo * 0.9), hi * 1.1]).range([labelW, width - 20])
    : scaleLinear().domain([lo, hi]).nice().range([labelW, width - 20]);
  const ticks = logScale ? (x as ReturnType<typeof scaleLog>).ticks(4) : (x as ReturnType<typeof scaleLinear>).ticks(5);
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip}
        summary={`${title}: ${rows.map((r) => `${r.label} ${num(r.value, 2)}`).join(", ")}`}
        table={{ columns: ["Term", "Estimate", "Low", "High", "p"], rows: rows.map((r) => [r.label, num(r.value, 3), num(r.low, 3), num(r.high, 3), r.p !== undefined ? num(r.p, 3) : ""]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">{ticks.map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={0} y2={height - 22} />)}</g>
          <g className="viz-axis">{ticks.map((t) => <text key={t} x={x(t)} y={height - 6} textAnchor="middle">{num(t, logScale ? 1 : 2)}</text>)}</g>
          <line x1={x(reference)} x2={x(reference)} y1={0} y2={height - 22} style={{ stroke: "var(--text-muted)" }} />
          {rows.map((r, i) => {
            const cy = i * band + band / 2;
            const sig = r.p !== undefined && r.p < 0.05;
            return (
              <g key={r.label} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: r.label,
                rows: [{ value: num(r.value, 3), label: r.low != null ? `95% CI ${num(r.low, 3)} to ${num(r.high, 3)}` : "estimate", color: "var(--series-1)" },
                  ...(r.p !== undefined ? [{ value: r.p < 0.001 ? "< .001" : num(r.p, 3), label: "p-value" }] : [])] })} onPointerLeave={hide}>
                <rect className="viz-hit" x={0} y={i * band} width={width} height={band} />
                <text className="viz-label" x={labelW - 8} y={cy + 4} textAnchor="end">{r.label.length > 34 ? `${r.label.slice(0, 33)}…` : r.label}</text>
                {r.low != null && r.high != null && <line x1={x(r.low)} x2={x(r.high)} y1={cy} y2={cy} style={{ stroke: "var(--series-1)" }} strokeWidth={2} strokeLinecap="round" />}
                <circle cx={x(r.value)} cy={cy} r={5} style={{ fill: sig ? "var(--series-1)" : "var(--surface-1)", stroke: "var(--series-1)" }} strokeWidth={2} />
              </g>
            );
          })}
        </svg>
      </ChartFrame>
      <div className="small muted">Filled points: p &lt; .05. Hollow points: not significant.</div>
    </div>
  );
}

/* ---------- Scatter / positioning map (few, directly labeled points) ---------- */

export function ScatterMap({ title, subtitle, points, xLabel, yLabel, xFmt = "number", currency = "IDR" }: {
  title: string; subtitle?: string; points: { name: string; x: number; y: number; self?: boolean }[]; xLabel: string; yLabel: string;
  xFmt?: Fmt; currency?: string;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const height = 240;
  const m = { l: 48, r: 24, t: 14, b: 38 };
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const x = scaleLinear().domain([(min(xs) ?? 0) * 0.8, (max(xs) ?? 1) * 1.15]).nice().range([m.l, width - m.r]);
  const y = scaleLinear().domain([Math.min(1, min(ys) ?? 1), Math.max(5, max(ys) ?? 5)]).nice().range([height - m.b, m.t]);
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip} summary={`${title}: ${points.map((p) => p.name).join(", ")}`}
        table={{ columns: ["Offer", xLabel, yLabel], rows: points.map((p) => [p.name, fmtValue(p.x, xFmt, currency), num(p.y, 1)]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">{y.ticks(4).map((t) => <line key={t} x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} />)}</g>
          <g className="viz-axis">
            {y.ticks(4).map((t) => <text key={t} x={m.l - 6} y={y(t) + 4} textAnchor="end">{t}</text>)}
            {x.ticks(4).map((t) => <text key={t} x={x(t)} y={height - m.b + 16} textAnchor="middle">{fmtValue(t, xFmt, currency)}</text>)}
            <text x={(m.l + width - m.r) / 2} y={height - 4} textAnchor="middle">{xLabel}</text>
            <text transform={`translate(12 ${(height - m.b) / 2}) rotate(-90)`} textAnchor="middle">{yLabel}</text>
          </g>
          {points.map((p, i) => (
            <g key={p.name} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: p.name,
              rows: [{ value: fmtValue(p.x, xFmt, currency), label: xLabel }, { value: num(p.y, 1), label: yLabel }] })} onPointerLeave={hide}>
              <circle cx={x(p.x)} cy={y(p.y)} r={14} className="viz-hit" />
              <circle cx={x(p.x)} cy={y(p.y)} r={p.self ? 7 : 5} style={{ fill: p.self ? SERIES[0] : SERIES[1 + (i % 2)], stroke: "var(--surface-1)" }} strokeWidth={2} />
              <text className={p.self ? "viz-strong" : "viz-value"} x={x(p.x) + 10} y={y(p.y) + 4}>{p.name}</text>
            </g>
          ))}
        </svg>
      </ChartFrame>
    </div>
  );
}

/* ---------- Column chart for ordered categories (ordinal ramp) ---------- */

export function OrdinalColumns({ title, subtitle, data, fmt = "number", currency = "IDR" }: {
  title: string; subtitle?: string; data: { label: string; value: number }[]; fmt?: Fmt; currency?: string;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const height = 220;
  const m = { l: 44, r: 8, t: 18, b: 28 };
  const x = scaleBand().domain(data.map((d) => d.label)).range([m.l, width - m.r]).paddingInner(0.3).paddingOuter(0.15);
  const y = scaleLinear().domain([0, max(data, (d) => d.value) ?? 1]).nice().range([height - m.b, m.t]);
  const ramp = ["var(--seq-700)", "var(--seq-600)", "var(--seq-500)", "var(--seq-400)", "var(--seq-300)", "var(--seq-250)"];
  const bw = Math.min(24 * 2, x.bandwidth());
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip} summary={`${title}: ${data.map((d) => `${d.label} ${fmtValue(d.value, fmt, currency)}`).join(", ")}`}
        table={{ columns: ["Stage", "Value"], rows: data.map((d) => [d.label, fmtValue(d.value, fmt, currency)]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">{y.ticks(4).map((t) => <line key={t} x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} />)}</g>
          <g className="viz-axis">
            {y.ticks(4).map((t) => <text key={t} x={m.l - 6} y={y(t) + 4} textAnchor="end">{fmtValue(t, fmt, currency)}</text>)}
          </g>
          {data.map((d, i) => {
            const bx = (x(d.label) ?? 0) + (x.bandwidth() - bw) / 2;
            return (
              <g key={d.label} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: d.label, rows: [{ value: fmtValue(d.value, fmt, currency), label: title }] })} onPointerLeave={hide}>
                <rect className="viz-hit" x={x(d.label)} y={m.t} width={x.bandwidth()} height={height - m.t - m.b} />
                <path d={vBar(bx, bw, y(0), y(d.value))} style={{ fill: ramp[Math.min(i, ramp.length - 1)] }} />
                <text className="viz-value" x={bx + bw / 2} y={y(d.value) - 4} textAnchor="middle">{fmtValue(d.value, fmt, currency)}</text>
                <text className="viz-label" x={bx + bw / 2} y={height - 10} textAnchor="middle">{d.label}</text>
              </g>
            );
          })}
          <line className="viz-baseline" x1={m.l} x2={width - m.r} y1={y(0)} y2={y(0)} />
        </svg>
      </ChartFrame>
    </div>
  );
}
