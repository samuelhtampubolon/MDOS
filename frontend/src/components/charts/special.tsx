/* Heatmap, waterfall, tornado, emotion curve, segment profiles, stacked shares and the mediation path diagram. */

import { max, min } from "d3-array";
import { scaleBand, scaleLinear } from "d3-scale";
import { money, num, pct } from "../../lib/format";
import { fmtValue, type Fmt } from "./basic";
import { ChartFrame, hBar, Legend, SERIES, textWidth, useTooltip, useWidth } from "./frame";

/* ---------- Heatmap: sequential (one hue) or diverging (two hues, gray midpoint) ---------- */

function mix(a: string, b: string, t: number): string {
  return `color-mix(in oklab, ${b} ${Math.round(Math.max(0, Math.min(1, t)) * 100)}%, ${a})`;
}

export function Heatmap({ title, subtitle, rows, cols, data, diverging = false, domain, fmt = "decimal" }: {
  title: string; subtitle?: string; rows: string[]; cols: string[]; data: (number | null)[][]; diverging?: boolean;
  domain?: [number, number]; fmt?: Fmt;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const values = data.flat().filter((v): v is number => v !== null && Number.isFinite(v));
  const [lo, hi] = domain ?? [diverging ? -1 : 0, max(values) ?? 1];
  const labelW = Math.min(170, Math.max(50, ...rows.map((r) => textWidth(r) + 10)));
  const colHead = Math.min(150, Math.max(36, ...cols.map((c) => textWidth(c.slice(0, 26)) * 0.72 + 12)));
  const cell = Math.max(18, Math.min(44, (width - labelW - 8) / Math.max(cols.length, 1)));
  const height = colHead + rows.length * cell + 4;
  // One ramp for cells and legend: t runs from 0 (low end) to 1 (high end).
  const ramp = (t: number) => diverging
    ? (t < 0.5 ? mix("var(--div-mid)", "var(--div-neg)", (0.5 - t) * 2) : mix("var(--div-mid)", "var(--div-pos)", (t - 0.5) * 2))
    : mix("var(--surface-1)", "var(--seq-600)", t);
  const color = (v: number | null) => {
    if (v === null || !Number.isFinite(v)) return "var(--surface-2)";
    if (!diverging && v === 0 && fmt === "number") return "var(--surface-2)";
    return ramp((v - lo) / (hi - lo || 1));
  };
  const textOn = (v: number | null) => {
    if (v === null) return "var(--text-muted)";
    const t = diverging ? Math.abs((v - lo) / (hi - lo) - 0.5) * 2 : (v - lo) / (hi - lo || 1);
    return t > 0.6 ? "#ffffff" : "var(--text-primary)";
  };
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip}
        summary={`${title}. ${rows.length} rows by ${cols.length} columns.`}
        table={{ columns: ["", ...cols], rows: rows.map((r, i) => [r, ...cols.map((_, j) => (data[i][j] === null ? "" : fmtValue(data[i][j], fmt)))]) }}>
        <svg width={width} height={height}>
          {cols.map((c, j) => (
            <text key={c} className="viz-label" transform={`translate(${labelW + j * cell + cell / 2} ${colHead - 6}) rotate(-35)`} textAnchor="start">
              {c.length > 26 ? `${c.slice(0, 25)}…` : c}
            </text>
          ))}
          {rows.map((r, i) => (
            <g key={r}>
              <text className="viz-label" x={labelW - 6} y={colHead + i * cell + cell / 2 + 4} textAnchor="end">{r.length > 24 ? `${r.slice(0, 23)}…` : r}</text>
              {cols.map((c, j) => {
                const v = data[i][j];
                return (
                  <g key={c} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: `${r} x ${c}`, rows: [{ value: v === null ? "n/a" : fmtValue(v, fmt), label: title }] })}
                    onPointerLeave={hide}>
                    <rect x={labelW + j * cell + 1} y={colHead + i * cell + 1} width={cell - 2} height={cell - 2} rx={3} style={{ fill: color(v) }} />
                    {cell >= 30 && v !== null && !(v === 0 && fmt === "number") && (
                      <text x={labelW + j * cell + cell / 2} y={colHead + i * cell + cell / 2 + 4} textAnchor="middle" style={{ fill: textOn(v), fontSize: 10.5 }}>
                        {fmt === "number" ? num(v) : num(v, 2)}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          ))}
        </svg>
        <div className="viz-scale">
          <span>{fmtValue(lo, fmt)}</span>
          <span className="viz-scale-steps" aria-hidden>
            {[0, 1 / 6, 2 / 6, 3 / 6, 4 / 6, 5 / 6, 1].map((t) => <span key={t} style={{ background: ramp(t) }} />)}
          </span>
          <span>{fmtValue(hi, fmt)}</span>
        </div>
      </ChartFrame>
    </div>
  );
}

/* ---------- Waterfall (profit bridge) ---------- */

export function Waterfall({ title, subtitle, steps, currency = "IDR" }: {
  title: string; subtitle?: string; steps: { label: string; value?: number; delta?: number; type: string }[]; currency?: string;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  let running = 0;
  const bars = steps.map((s) => {
    if (s.type === "total") {
      running = s.value ?? 0;
      return { ...s, start: 0, end: running };
    }
    const start = running;
    running += s.delta ?? 0;
    return { ...s, start, end: running };
  });
  const height = 240;
  const m = { l: 60, r: 10, t: 16, b: 46 };
  const x = scaleBand().domain(bars.map((_, i) => `${i}`)).range([m.l, width - m.r]).paddingInner(0.35).paddingOuter(0.1);
  const lo = Math.min(0, min(bars, (b) => Math.min(b.start, b.end)) ?? 0);
  const hi = Math.max(0, max(bars, (b) => Math.max(b.start, b.end)) ?? 1);
  const y = scaleLinear().domain([lo, hi]).nice().range([height - m.b, m.t]);
  const bw = Math.min(48, x.bandwidth());
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip}
        legend={<Legend items={[{ label: "Increase", color: "var(--div-pos)" }, { label: "Decrease", color: "var(--div-neg)" }, { label: "Total", color: "var(--deemph)" }]} />}
        summary={`${title}: ${bars.map((b) => `${b.label} ${money(b.type === "total" ? b.end : b.delta ?? 0, currency, { compact: true })}`).join(", ")}`}
        table={{ columns: ["Step", "Change", "Running total"], rows: bars.map((b) => [b.label, b.type === "total" ? "" : money(b.delta ?? 0, currency), money(b.end, currency)]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">{y.ticks(4).map((t) => <line key={t} x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} />)}</g>
          <g className="viz-axis">{y.ticks(4).map((t) => <text key={t} x={m.l - 6} y={y(t) + 4} textAnchor="end">{money(t, currency, { compact: true })}</text>)}</g>
          <line className="viz-baseline" x1={m.l} x2={width - m.r} y1={y(0)} y2={y(0)} />
          {bars.map((b, i) => {
            const bx = (x(`${i}`) ?? 0) + (x.bandwidth() - bw) / 2;
            const fill = b.type === "total" ? "var(--deemph)" : (b.delta ?? 0) >= 0 ? "var(--div-pos)" : "var(--div-neg)";
            const top = Math.min(y(b.start), y(b.end));
            const h = Math.max(1, Math.abs(y(b.start) - y(b.end)));
            const label = b.type === "total" ? money(b.end, currency, { compact: true }) : `${(b.delta ?? 0) >= 0 ? "+" : ""}${money(b.delta ?? 0, currency, { compact: true })}`;
            return (
              <g key={i} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: b.label, rows: [{ value: label, label: b.type === "total" ? "total" : "change", color: fill }] })} onPointerLeave={hide}>
                <rect className="viz-hit" x={x(`${i}`)} y={m.t} width={x.bandwidth()} height={height - m.t - m.b} />
                <rect x={bx} y={top} width={bw} height={h} rx={3} style={{ fill }} />
                <text className="viz-value" x={bx + bw / 2} y={top - 4} textAnchor="middle">{label}</text>
                <text className="viz-label" x={bx + bw / 2} y={height - m.b + 14} textAnchor="middle">
                  {b.label.length > 16 ? `${b.label.slice(0, 15)}…` : b.label}
                </text>
              </g>
            );
          })}
        </svg>
      </ChartFrame>
    </div>
  );
}

/* ---------- Tornado (sensitivity) ---------- */

export function Tornado({ title, subtitle, base, rows, fmt = "money", currency = "IDR", pctLabel }: {
  title: string; subtitle?: string; base: number; rows: { label: string; low: number; high: number }[]; fmt?: Fmt; currency?: string; pctLabel: string;
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const labelW = Math.min(230, Math.max(90, ...rows.map((r) => textWidth(r.label) + 10)));
  const band = 28;
  const height = rows.length * band + 26;
  const lo = Math.min(base, min(rows, (r) => Math.min(r.low, r.high)) ?? base);
  const hi = Math.max(base, max(rows, (r) => Math.max(r.low, r.high)) ?? base);
  const x = scaleLinear().domain([lo, hi]).nice().range([labelW, width - 16]);
  const barH = 16;
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip}
        legend={<Legend items={[{ label: `Assumption ${pctLabel} lower`, color: "var(--div-neg)" }, { label: `Assumption ${pctLabel} higher`, color: "var(--div-pos)" }]} />}
        summary={`${title}. Largest swing: ${rows[0]?.label ?? "none"}.`}
        table={{ columns: ["Assumption", `Result when ${pctLabel} lower`, `Result when ${pctLabel} higher`, "Swing"],
          rows: rows.map((r) => [r.label, fmtValue(r.low, fmt, currency), fmtValue(r.high, fmt, currency), fmtValue(Math.abs(r.high - r.low), fmt, currency)]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">{x.ticks(4).map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={0} y2={height - 22} />)}</g>
          <g className="viz-axis">{x.ticks(4).map((t) => <text key={t} x={x(t)} y={height - 6} textAnchor="middle">{fmtValue(t, fmt, currency)}</text>)}</g>
          {rows.map((r, i) => {
            const y = i * band + (band - barH) / 2;
            return (
              <g key={r.label} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: r.label,
                rows: [{ value: fmtValue(r.low, fmt, currency), label: `${pctLabel} lower`, color: "var(--div-neg)" }, { value: fmtValue(r.high, fmt, currency), label: `${pctLabel} higher`, color: "var(--div-pos)" }] })}
                onPointerLeave={hide}>
                <rect className="viz-hit" x={0} y={i * band} width={width} height={band} />
                <text className="viz-label" x={labelW - 8} y={y + barH / 2 + 4} textAnchor="end">{r.label.length > 36 ? `${r.label.slice(0, 35)}…` : r.label}</text>
                <path d={hBar(x(base), x(r.low), y, barH)} style={{ fill: "var(--div-neg)" }} />
                <path d={hBar(x(base), x(r.high), y, barH)} style={{ fill: "var(--div-pos)" }} />
              </g>
            );
          })}
          <line x1={x(base)} x2={x(base)} y1={0} y2={height - 22} style={{ stroke: "var(--text-primary)" }} />
        </svg>
      </ChartFrame>
    </div>
  );
}

/* ---------- Emotion curve across journey stages ---------- */

export function EmotionCurve({ title, subtitle, data }: { title: string; subtitle?: string; data: { label: string; value: number | null; n: number }[] }) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const step = (width - 56) / Math.max(1, data.length);
  const crowded = data.some((d) => textWidth(d.label) > step - 6);
  const height = crowded ? 242 : 230;
  const m = { l: 40, r: 16, t: 16, b: crowded ? 46 : 34 };
  const x = scaleBand().domain(data.map((d) => d.label)).range([m.l, width - m.r]).padding(0.5);
  const y = scaleLinear().domain([-1, 1]).range([height - m.b, m.t]);
  const pts = data.map((d) => ({ ...d, cx: (x(d.label) ?? 0) + x.bandwidth() / 2 }));
  const path = pts.filter((p) => p.value !== null).map((p, i) => `${i ? "L" : "M"}${p.cx},${y(p.value as number)}`).join("");
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip}
        summary={`${title}: ${data.map((d) => `${d.label} ${d.value === null ? "no mentions" : num(d.value, 2)}`).join(", ")}`}
        table={{ columns: ["Stage", "Mean sentiment", "Reviews"], rows: data.map((d) => [d.label, d.value === null ? "" : num(d.value, 2), d.n]) }}>
        <svg width={width} height={height}>
          <rect x={m.l} y={y(1)} width={width - m.l - m.r} height={y(0) - y(1)} style={{ fill: "var(--div-pos)", opacity: 0.05 }} />
          <rect x={m.l} y={y(0)} width={width - m.l - m.r} height={y(-1) - y(0)} style={{ fill: "var(--div-neg)", opacity: 0.05 }} />
          <g className="viz-grid">{[-1, -0.5, 0.5, 1].map((t) => <line key={t} x1={m.l} x2={width - m.r} y1={y(t)} y2={y(t)} />)}</g>
          <line className="viz-baseline" x1={m.l} x2={width - m.r} y1={y(0)} y2={y(0)} />
          <g className="viz-axis">
            {[-1, 0, 1].map((t) => <text key={t} x={m.l - 6} y={y(t) + 4} textAnchor="end">{t > 0 ? "+1" : t}</text>)}
            <text x={m.l + 4} y={m.t + 10} textAnchor="start">Positive</text>
            <text x={m.l + 4} y={height - m.b - 6} textAnchor="start">Negative</text>
          </g>
          <path d={path} fill="none" style={{ stroke: "var(--series-1)" }} strokeWidth={2} strokeLinejoin="round" />
          {pts.map((p, i) => (
            <g key={p.label} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: p.label,
              rows: [{ value: p.value === null ? "no mentions" : num(p.value, 2), label: `mean sentiment, ${p.n} reviews` }] })} onPointerLeave={hide}>
              <rect className="viz-hit" x={x(p.label)} y={m.t} width={x.bandwidth()} height={height - m.t - m.b} />
              {p.value !== null ? (
                <circle cx={p.cx} cy={y(p.value)} r={Math.min(9, 4 + Math.sqrt(p.n) / 2)}
                  style={{ fill: p.value >= 0 ? "var(--div-pos)" : "var(--div-neg)", stroke: "var(--surface-1)" }} strokeWidth={2} />
              ) : (
                <circle cx={p.cx} cy={y(0)} r={4} style={{ fill: "var(--surface-1)", stroke: "var(--axis)" }} strokeWidth={1.5} />
              )}
              <text className="viz-label" x={p.cx} y={height - m.b + 16 + (crowded && i % 2 ? 13 : 0)} textAnchor="middle">{p.label}</text>
            </g>
          ))}
        </svg>
      </ChartFrame>
      <div className="small muted">Dot size grows with the number of reviews mentioning the stage.</div>
    </div>
  );
}

/* ---------- Segment profiles: grouped bars of z-scores (diverging around zero) ---------- */

export function SegmentProfiles({ title, subtitle, variables, segments }: {
  title: string; subtitle?: string; variables: string[]; segments: { name: string; share: number; z: number[] }[];
}) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const shown = segments.slice(0, 3);
  const labelW = Math.min(170, Math.max(70, ...variables.map((v) => textWidth(v) + 10)));
  const groupH = shown.length * 14 + 14;
  const height = variables.length * groupH + 26;
  const ext = Math.max(1, max(shown.flatMap((s) => s.z.map(Math.abs))) ?? 1);
  const x = scaleLinear().domain([-ext, ext]).nice().range([labelW, width - 14]);
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip}
        legend={<Legend items={shown.map((s, i) => ({ label: `${s.name} (${pct(s.share)})`, color: SERIES[i] }))} />}
        summary={`${title}: ${shown.map((s) => s.name).join(", ")}`}
        table={{ columns: ["Variable", ...shown.map((s) => s.name)], rows: variables.map((v, i) => [v, ...shown.map((s) => num(s.z[i], 2))]) }}>
        <svg width={width} height={height}>
          <g className="viz-grid">{x.ticks(4).map((t) => <line key={t} x1={x(t)} x2={x(t)} y1={0} y2={height - 22} />)}</g>
          <g className="viz-axis">{x.ticks(4).map((t) => <text key={t} x={x(t)} y={height - 6} textAnchor="middle">{t > 0 ? `+${t}` : t} SD</text>)}</g>
          {variables.map((v, i) => (
            <g key={v}>
              <text className="viz-label" x={labelW - 8} y={i * groupH + groupH / 2 + 4} textAnchor="end">{v}</text>
              {shown.map((s, j) => {
                const y = i * groupH + 7 + j * 14;
                return (
                  <g key={s.name} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: v, rows: [{ value: `${s.z[i] > 0 ? "+" : ""}${num(s.z[i], 2)} SD`, label: s.name, color: SERIES[j] }] })} onPointerLeave={hide}>
                    <rect className="viz-hit" x={labelW} y={y - 1} width={width - labelW} height={14} />
                    <path d={hBar(x(0), x(s.z[i]), y, 12, 3)} style={{ fill: SERIES[j] }} />
                  </g>
                );
              })}
            </g>
          ))}
          <line className="viz-baseline" x1={x(0)} x2={x(0)} y1={0} y2={height - 22} />
        </svg>
      </ChartFrame>
    </div>
  );
}

/* ---------- Stacked shares (cross-tab rows as 100% bars) ---------- */

export function StackedShares({ title, subtitle, rows, cols, data }: { title: string; subtitle?: string; rows: string[]; cols: string[]; data: number[][] }) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const { tip, show, hide } = useTooltip();
  const shownCols = cols.slice(0, 8);
  const labelW = Math.min(150, Math.max(60, ...rows.map((r) => textWidth(r) + 10)));
  const band = 32;
  const height = rows.length * band + 24;
  const x = scaleLinear().domain([0, 1]).range([labelW, width - 10]);
  return (
    <div ref={ref}>
      <ChartFrame title={title} subtitle={subtitle} width={width} tip={tip}
        legend={<Legend items={shownCols.map((c, i) => ({ label: c, color: SERIES[i] }))} />}
        summary={`${title}. Shares by row.`}
        table={{ columns: ["", ...shownCols], rows: rows.map((r, i) => [r, ...shownCols.map((_, j) => pct(data[i][j], 1))]) }}>
        <svg width={width} height={height}>
          <g className="viz-axis">{[0, 0.5, 1].map((t) => <text key={t} x={x(t)} y={height - 6} textAnchor="middle">{pct(t)}</text>)}</g>
          {rows.map((r, i) => {
            let acc = 0;
            const y = i * band + 6;
            return (
              <g key={r}>
                <text className="viz-label" x={labelW - 8} y={y + 14} textAnchor="end">{r}</text>
                {shownCols.map((c, j) => {
                  const v = data[i][j] ?? 0;
                  const x0 = x(acc) + (j ? 1 : 0);
                  const x1 = x(acc + v) - 1;
                  acc += v;
                  const w = Math.max(0, x1 - x0);
                  const label = pct(v);
                  return (
                    <g key={c} onPointerMove={(e) => show({ x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY, title: r, rows: [{ value: pct(v, 1), label: c, color: SERIES[j] }] })} onPointerLeave={hide}>
                      <rect x={x0} y={y} width={w} height={20} rx={j === 0 || j === shownCols.length - 1 ? 3 : 0} style={{ fill: SERIES[j] }} />
                      {w > textWidth(label) + 10 && <text x={x0 + w / 2} y={y + 14} textAnchor="middle" style={{ fill: "#fff", fontSize: 11 }}>{label}</text>}
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
      </ChartFrame>
    </div>
  );
}

/* ---------- Mediation path diagram (not a chart: a labeled model sketch) ---------- */

export function PathDiagram({ x, m, y, paths, p }: { x: string; m: string; y: string; paths: Record<string, number>; p: Record<string, number> }) {
  const star = (v: number) => (v < 0.001 ? "***" : v < 0.01 ? "**" : v < 0.05 ? "*" : "");
  const box = (cx: number, cy: number, label: string) => (
    <g>
      <rect x={cx - 70} y={cy - 18} width={140} height={36} rx={8} style={{ fill: "var(--surface-2)", stroke: "var(--border-strong)" }} />
      <text x={cx} y={cy + 4} textAnchor="middle" className="viz-strong">{label.length > 20 ? `${label.slice(0, 19)}…` : label}</text>
    </g>
  );
  return (
    <svg viewBox="0 0 440 170" width="100%" style={{ maxWidth: 520 }} role="img"
      aria-label={`Mediation model: ${x} to ${m} (a = ${num(paths.a, 2)}), ${m} to ${y} (b = ${num(paths.b, 2)}), direct effect c' = ${num(paths.c_prime, 2)}`}>
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0L10,5L0,10z" style={{ fill: "var(--text-secondary)" }} />
        </marker>
      </defs>
      <g style={{ stroke: "var(--text-secondary)" }} strokeWidth={1.5} fill="none">
        <line x1={120} y1={122} x2={185} y2={58} markerEnd="url(#arrow)" />
        <line x1={255} y1={58} x2={320} y2={122} markerEnd="url(#arrow)" />
        <line x1={140} y1={140} x2={300} y2={140} markerEnd="url(#arrow)" />
      </g>
      {box(220, 40, m)}
      {box(80, 140, x)}
      {box(360, 140, y)}
      <text className="viz-value" x={128} y={80}>a = {num(paths.a, 2)}{star(p.a)}</text>
      <text className="viz-value" x={276} y={80}>b = {num(paths.b, 2)}{star(p.b)}</text>
      <text className="viz-value" x={220} y={162} textAnchor="middle">c' = {num(paths.c_prime, 2)}{star(p.c_prime)} (total c = {num(paths.c, 2)})</text>
    </svg>
  );
}

export { money };
