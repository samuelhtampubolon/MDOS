/* Layered lineage graph: data sources on the left, decisions and tests on the right.
   Nodes stay neutral; status is carried by the stroke (solid green = approved, dashed = draft or proposed)
   and spelled out in the tooltip and the table view. Clicking a node traces its full chain. */

import { useMemo, useState } from "react";
import type { GraphData } from "../api/types";
import { sentence } from "../lib/format";
import { ChartFrame, useTooltip } from "./charts/frame";

const KINDS: Record<string, { layer: number; label: string }> = {
  dataset: { layer: 0, label: "Dataset" },
  dataset_version: { layer: 1, label: "Version" },
  analysis: { layer: 2, label: "Analysis" },
  evidence: { layer: 3, label: "Evidence" },
  hypothesis: { layer: 4, label: "Hypothesis" },
  insight: { layer: 4, label: "Insight" },
  pain_point: { layer: 4, label: "Pain point" },
  recommendation: { layer: 5, label: "Recommendation" },
  scenario: { layer: 5, label: "Scenario" },
  journey: { layer: 5, label: "Journey" },
  experiment: { layer: 5, label: "Experiment" },
  decision: { layer: 6, label: "Decision" },
};
const LAYER_TITLES = ["Sources", "Versions", "Analyses", "Evidence", "Findings", "Plans and tests", "Decisions"];
const KIND_ORDER = Object.keys(KINDS);

const NODE_W = 172;
const NODE_H = 26;
const ROW = 32;
const COL = NODE_W + 52;
const TOP = 26;

function statusClass(status?: string): string {
  if (!status) return "";
  if (status.startsWith("proposed")) return "proposed";
  if (status === "draft" || status === "idea" || status === "pending") return "draft";
  if (["approved", "supported", "adopted", "final", "completed", "succeeded"].includes(status)) return "approved";
  return "";
}

/** Pointer position relative to the chart plot (the graph scrolls inside it). */
function relative(e: React.PointerEvent<SVGGElement>): { x: number; y: number } {
  const host = e.currentTarget.ownerSVGElement?.parentElement?.parentElement;
  const r = host?.getBoundingClientRect();
  return { x: e.clientX - (r?.left ?? 0), y: e.clientY - (r?.top ?? 0) };
}

function trace(start: string, next: Map<string, string[]>): Set<string> {
  const seen = new Set<string>();
  const stack = [start];
  while (stack.length) {
    const id = stack.pop() as string;
    for (const n of next.get(id) ?? []) {
      if (!seen.has(n)) {
        seen.add(n);
        stack.push(n);
      }
    }
  }
  return seen;
}

export function LineageGraph({ data, title = "Evidence graph", subtitle, only }: { data: GraphData; title?: string; subtitle?: string; only?: string[] }) {
  const { tip, show, hide } = useTooltip();
  const [focus, setFocus] = useState<string | null>(null);
  const layout = useMemo(() => {
    const nodes = data.nodes.filter((n) => KINDS[n.kind] && (!only || only.includes(n.kind)));
    const ids = new Set(nodes.map((n) => n.id));
    const edges = data.edges.filter((e) => ids.has(e.from) && ids.has(e.to));
    const preds = new Map<string, string[]>();
    const succs = new Map<string, string[]>();
    for (const e of edges) {
      preds.set(e.to, [...(preds.get(e.to) ?? []), e.from]);
      succs.set(e.from, [...(succs.get(e.from) ?? []), e.to]);
    }
    const layers: (typeof nodes)[] = LAYER_TITLES.map(() => []);
    for (const n of nodes) layers[KINDS[n.kind].layer].push(n);
    const pos = new Map<string, { x: number; y: number; layer: number }>();
    layers.forEach((layer, li) => {
      const bary = (id: string) => {
        const ys = (preds.get(id) ?? []).map((p) => pos.get(p)).filter((p): p is { x: number; y: number; layer: number } => Boolean(p) && (p as { layer: number }).layer < li).map((p) => p.y);
        return ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : Number.MAX_SAFE_INTEGER;
      };
      const scored = layer.map((n) => ({ n, b: bary(n.id) }));
      scored.sort((a, b) => KIND_ORDER.indexOf(a.n.kind) - KIND_ORDER.indexOf(b.n.kind) || a.b - b.b || a.n.label.localeCompare(b.n.label));
      scored.forEach(({ n }, i) => pos.set(n.id, { x: 8 + li * COL, y: TOP + i * ROW, layer: li }));
    });
    const used = layers.map((l, i) => (l.length ? i : -1)).filter((i) => i >= 0);
    const width = 16 + (Math.max(...used, 0) + 1) * COL - 52;
    const height = TOP + Math.max(...layers.map((l) => l.length), 1) * ROW + 44;
    return { nodes, edges, preds, succs, pos, width, height, used };
  }, [data, only]);

  const highlighted = useMemo(() => {
    if (!focus) return null;
    return new Set([focus, ...trace(focus, layout.preds), ...trace(focus, layout.succs)]);
  }, [focus, layout]);

  const byId = new Map(layout.nodes.map((n) => [n.id, n]));
  const table = {
    columns: ["Kind", "Item", "Status", "Comes from"],
    rows: layout.nodes.map((n) => [KINDS[n.kind].label, n.label, sentence(n.status ?? n.strength ?? ""),
      (layout.preds.get(n.id) ?? []).map((p) => byId.get(p)?.label ?? "").join("; ")]),
  };
  const width = Math.max(layout.width, 320);
  return (
    <ChartFrame title={title} subtitle={subtitle ?? "Click any item to trace where it came from and what it feeds. Click again to clear."}
      table={table} tip={tip} width={width}
      summary={`${title}: ${layout.nodes.length} items and ${layout.edges.length} links from data sources to decisions.`}
      legend={
        <ul className="viz-legend" aria-label="Legend">
          <li><svg width="22" height="12" aria-hidden><rect x="1" y="1" width="20" height="10" rx="3" style={{ fill: "var(--surface-1)", stroke: "var(--good)" }} /></svg>Approved or supported</li>
          <li><svg width="22" height="12" aria-hidden><rect x="1" y="1" width="20" height="10" rx="3" strokeDasharray="3 2" style={{ fill: "var(--surface-1)", stroke: "var(--border-strong)" }} /></svg>Draft or proposed</li>
          <li><svg width="22" height="12" aria-hidden><path d="M1,6 H21" strokeDasharray="4 3" style={{ stroke: "var(--text-secondary)" }} /></svg>Result fed back as evidence</li>
        </ul>
      }>
      <div style={{ overflow: "auto", maxHeight: 680 }}>
        <svg width={width} height={layout.height}>
          <defs>
            <marker id="lg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0L10,5L0,10z" style={{ fill: "var(--axis)" }} />
            </marker>
          </defs>
          {layout.used.map((li) => (
            <text key={li} className="viz-label" x={8 + li * COL} y={14} style={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", fontSize: 10 }}>
              {LAYER_TITLES[li]}
            </text>
          ))}
          {layout.edges.map((e, i) => {
            const a = layout.pos.get(e.from);
            const b = layout.pos.get(e.to);
            if (!a || !b) return null;
            const same = b.layer === a.layer;
            const back = b.layer < a.layer;
            const on = !highlighted || (highlighted.has(e.from) && highlighted.has(e.to));
            const d = same
              ? `M${a.x},${a.y + NODE_H / 2} C${a.x - 16},${a.y + NODE_H / 2} ${b.x - 16},${b.y + NODE_H / 2} ${b.x - 2},${b.y + NODE_H / 2}`
              : back
              ? `M${a.x + NODE_W / 2},${a.y + NODE_H} C${a.x + NODE_W / 2},${a.y + NODE_H + 70} ${b.x + NODE_W / 2},${b.y + NODE_H + 70} ${b.x + NODE_W / 2},${b.y + NODE_H + 2}`
              : `M${a.x + NODE_W},${a.y + NODE_H / 2} C${a.x + NODE_W + 26},${a.y + NODE_H / 2} ${b.x - 26},${b.y + NODE_H / 2} ${b.x - 2},${b.y + NODE_H / 2}`;
            return <path key={i} d={d} className="graph-edge" markerEnd="url(#lg-arrow)" strokeDasharray={back ? "4 3" : undefined}
              style={{ opacity: on ? 1 : 0.12, stroke: back ? "var(--text-secondary)" : undefined, strokeWidth: highlighted && on ? 1.5 : 1 }} />;
          })}
          {layout.nodes.map((n) => {
            const p = layout.pos.get(n.id);
            if (!p) return null;
            const on = !highlighted || highlighted.has(n.id);
            const text = n.label.length > 27 ? `${n.label.slice(0, 26)}…` : n.label;
            return (
              <g key={n.id} className={`graph-node ${statusClass(n.status)}`} transform={`translate(${p.x} ${p.y})`} style={{ opacity: on ? 1 : 0.25, cursor: "pointer" }}
                role="button" tabIndex={0} aria-label={`${KINDS[n.kind].label}: ${n.label}${n.status ? `, ${sentence(n.status)}` : ""}`}
                onClick={() => setFocus((f) => (f === n.id ? null : n.id))}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setFocus((f) => (f === n.id ? null : n.id))}
                onPointerMove={(e) => show({ ...relative(e), title: n.label,
                  rows: [{ value: KINDS[n.kind].label, label: [n.status && sentence(n.status), n.strength && `${n.strength} evidence`, n.origin && sentence(n.origin)].filter(Boolean).join(" · ") }] })}
                onPointerLeave={hide}>
                <rect width={NODE_W} height={NODE_H} rx={6} strokeWidth={focus === n.id ? 2.5 : 1.5} />
                <text x={8} y={17}>{text}</text>
              </g>
            );
          })}
        </svg>
      </div>
    </ChartFrame>
  );
}
