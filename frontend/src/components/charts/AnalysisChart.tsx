/* Maps chart specs produced by the analytics engine to chart components. */

import type { ChartSpec } from "../../api/types";
import { BarChart, CoefficientPlot, LineChart, type Fmt } from "./basic";
import { EmotionCurve, Heatmap, PathDiagram, SegmentProfiles, StackedShares } from "./special";

type Any = Record<string, unknown>;

export function AnalysisChart({ spec, currency = "IDR" }: { spec: ChartSpec; currency?: string }) {
  const s = spec as Any;
  switch (spec.type) {
    case "bar":
      return <BarChart title={spec.title} data={(s.data as Any[]).map((d) => ({ label: String(d.label), value: d.value as number,
        low: d.low as number | undefined, high: d.high as number | undefined }))} fmt={(s.format as Fmt) ?? "number"} currency={currency} />;
    case "coefficients":
      return <CoefficientPlot title={spec.title} reference={(s.reference as number) ?? 0} logScale={Boolean(s.log_scale)}
        data={(s.data as Any[]).map((d) => ({ label: String(d.label), value: d.value as number, low: d.low as number, high: d.high as number, p: d.p as number }))} />;
    case "heatmap":
      return <Heatmap title={spec.title} rows={(s.labels as string[]) ?? (s.rows as string[])} cols={(s.labels as string[]) ?? (s.cols as string[])}
        data={s.data as (number | null)[][]} diverging={Array.isArray(s.domain)} domain={s.domain as [number, number] | undefined}
        fmt={Array.isArray(s.domain) ? "decimal" : "number"} />;
    case "stacked_bar":
      return <StackedShares title={spec.title} rows={s.rows as string[]} cols={s.cols as string[]} data={s.data as number[][]} />;
    case "price_curves": {
      const data = s.data as Any[];
      const keys: [string, string][] = [["too_cheap", "Too cheap"], ["cheap", "Cheap"], ["expensive", "Expensive"], ["too_expensive", "Too expensive"]];
      const markers = Object.entries((s.markers as Record<string, number | null>) ?? {}).filter(([, v]) => v !== null)
        .map(([k, v]) => ({ x: v as number, label: k }));
      return <LineChart title={spec.title} subtitle="Share of respondents at each price" xFmt="money" yFmt="percent" currency={currency}
        xLabel="Price" markers={markers} yDomain={[0, 1]}
        series={keys.map(([k, name]) => ({ name, points: data.map((d) => ({ x: d.price as number, y: d[k] as number })) }))} />;
    }
    case "demand_curve": {
      const data = s.data as Any[];
      return (
        <div className="grid grid-2">
          <LineChart title="Willing to buy by price" subtitle="Share answering yes, with the tested prices" xFmt="money" yFmt="percent"
            currency={currency} yDomain={[0, 1]} xLabel="Price"
            series={[{ name: "Willing to buy", points: data.map((d) => ({ x: d.price as number, y: d.share as number })) }]} />
          <LineChart title="Revenue index by price" subtitle="Price times share willing (per potential customer)" xFmt="money" yFmt="money"
            currency={currency} xLabel="Price" area
            series={[{ name: "Revenue index", points: data.map((d) => ({ x: d.price as number, y: d.revenue_index as number })) }]} />
        </div>
      );
    }
    case "line":
      return <LineChart title={spec.title} xLabel={s.x_label as string} yFmt="decimal" xFmt="decimal"
        series={(s.series as Any[]).map((se) => ({ name: String(se.label), points: (se.points as Any[]).map((p) => ({ x: p.x as number, y: p.y as number })) }))} />;
    case "segment_profiles":
      return <SegmentProfiles title={spec.title} variables={s.variables as string[]} segments={s.segments as { name: string; share: number; z: number[] }[]} />;
    case "emotion_curve":
      return <EmotionCurve title={spec.title} data={(s.data as Any[]).map((d) => ({ label: String(d.label), value: d.value as number | null, n: d.n as number }))} />;
    case "path_diagram":
      return (
        <figure className="viz">
          <figcaption className="viz-head"><div className="viz-title">{spec.title}</div></figcaption>
          <PathDiagram x={s.x as string} m={s.m as string} y={s.y as string} paths={s.paths as Record<string, number>} p={s.p as Record<string, number>} />
          <div className="small muted">* p &lt; .05, ** p &lt; .01, *** p &lt; .001. Paths are unstandardized OLS coefficients.</div>
        </figure>
      );
    default:
      return null;
  }
}
