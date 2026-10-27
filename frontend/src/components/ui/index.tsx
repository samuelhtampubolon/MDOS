import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { Check, EvidenceRef } from "../../api/types";
import { sentence } from "../../lib/format";
import { Icon } from "./Icon";

export { Icon };

/* ---------- Layout primitives ---------- */

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-header">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="actions">{actions}</div>}
    </header>
  );
}

export function Card({ title, subtitle, actions, children, className = "", bodyClass = "" }: {
  title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="card-header">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <div className="card-sub">{subtitle}</div>}
          </div>
          {actions && <div className="actions">{actions}</div>}
        </div>
      )}
      <div className={`card-body ${bodyClass}`}>{children}</div>
    </section>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { key: T; label: ReactNode }[]; value: T; onChange: (key: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.key} role="tab" aria-selected={t.key === value} className={`tab ${t.key === value ? "active" : ""}`}
          onClick={() => onChange(t.key)}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <h3>{title}</h3>
      {children && <div className="small">{children}</div>}
      {action && <div style={{ marginTop: 12 }}>{action}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="row small muted" role="status">
      <span className="spinner" aria-hidden />
      {label}
    </span>
  );
}

export function Callout({ tone = "info", children, icon }: { tone?: "info" | "warning" | "critical" | "good"; children: ReactNode; icon?: string }) {
  const iconName = icon ?? (tone === "info" ? "info" : tone === "good" ? "check" : "alert");
  return (
    <div className={`callout ${tone === "info" ? "" : tone}`} role={tone === "critical" ? "alert" : undefined}>
      <span className="callout-icon"><Icon name={iconName} /></span>
      <div>{children}</div>
    </div>
  );
}

export function Stat({ label, value, delta, deltaTone, hint }: { label: string; value: ReactNode; delta?: ReactNode; deltaTone?: "up" | "down"; hint?: string }) {
  return (
    <div className="stat" title={hint}>
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {delta !== undefined && <span className={`stat-delta ${deltaTone ?? ""}`}>{delta}</span>}
    </div>
  );
}

/* ---------- Status and badges (status colors always pair with an icon and a label) ---------- */

const STATUS: Record<string, { tone: string; icon: string; label?: string }> = {
  succeeded: { tone: "good", icon: "check" }, done: { tone: "good", icon: "check" }, approved: { tone: "good", icon: "check" },
  supported: { tone: "good", icon: "check" }, final: { tone: "good", icon: "lock" }, adopted: { tone: "good", icon: "check" },
  completed: { tone: "good", icon: "check" }, ok: { tone: "good", icon: "check", label: "OK" },
  running: { tone: "info", icon: "refresh" }, queued: { tone: "info", icon: "refresh" }, draft: { tone: "", icon: "flag" },
  awaiting_approval: { tone: "warning", icon: "approvals", label: "Awaiting approval" }, pending: { tone: "warning", icon: "approvals" },
  warning: { tone: "warning", icon: "alert" }, inconclusive: { tone: "warning", icon: "alert" },
  proposed_supported: { tone: "warning", icon: "approvals", label: "Proposed: supported" },
  proposed_not_supported: { tone: "warning", icon: "approvals", label: "Proposed: not supported" },
  proposed_inconclusive: { tone: "warning", icon: "approvals", label: "Proposed: inconclusive" },
  failed: { tone: "critical", icon: "x" }, rejected: { tone: "critical", icon: "x" }, violated: { tone: "critical", icon: "x" },
  not_supported: { tone: "serious", icon: "x", label: "Not supported" }, cancelled: { tone: "", icon: "x" },
  high: { tone: "critical", icon: "alert", label: "High" }, medium: { tone: "serious", icon: "alert", label: "Medium" },
  low: { tone: "", icon: "info", label: "Low" }, untested: { tone: "", icon: "info", label: "Not yet tested" },
  not_applicable: { tone: "", icon: "info", label: "Not testable" }, skipped: { tone: "", icon: "chevron" },
  pending_step: { tone: "", icon: "chevron", label: "Pending" },
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const s = STATUS[status] ?? { tone: "", icon: "info" };
  return (
    <span className={`badge ${s.tone}`}>
      <Icon name={s.icon} size={12} />
      {label ?? s.label ?? sentence(status)}
    </span>
  );
}

export function Badge({ children, tone = "" }: { children: ReactNode; tone?: string }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export function OriginBadge({ origin }: { origin: string }) {
  const map: Record<string, [string, string]> = {
    user_data: ["User data", "info"], external: ["External", ""], synthetic_demo: ["Synthetic demo", "warning"],
    experiment: ["Experiment", "good"], model_generated: ["Model-generated", "serious"],
  };
  const [label, tone] = map[origin] ?? [sentence(origin), ""];
  return <Badge tone={tone}>{label}</Badge>;
}

export function ModelBadge() {
  return (
    <span className="badge serious" title="Wording drafted by Claude; numbers come from code and were checked.">
      <Icon name="sparkles" size={12} />Model-generated wording
    </span>
  );
}

export function EvidenceChips({ evidence, onOpen }: { evidence: EvidenceRef[]; onOpen?: (id: string) => void }) {
  if (!evidence.length) return <span className="small muted">No evidence linked</span>;
  return (
    <span className="row" style={{ gap: 4 }}>
      {evidence.map((e) =>
        onOpen ? (
          <button key={e.id} className={`chip code strength-${e.strength}`} title={`${e.title} (${e.strength})`} onClick={() => onOpen(e.id)}>
            {e.code}
          </button>
        ) : (
          <span key={e.id} className={`chip code strength-${e.strength}`} title={`${e.title} (${e.strength})`}>{e.code}</span>
        ),
      )}
    </span>
  );
}

export function ChecksList({ checks }: { checks: Check[] }) {
  if (!checks.length) return null;
  return (
    <ul className="list" style={{ margin: 0, padding: 0, listStyle: "none" }}>
      {checks.map((c, i) => (
        <li key={i} className="list-item" style={{ padding: "7px 0" }}>
          <StatusBadge status={c.status} />
          <div className="grow">
            <div style={{ fontWeight: 600, fontSize: 13 }}>{c.name}</div>
            <div className="small secondary">{c.detail}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ---------- Modal ---------- */

export function Modal({ title, open, onClose, children, footer, wide = false }: {
  title: string; open: boolean; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    ref.current?.focus();
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal ${wide ? "wide" : ""}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="btn ghost icon" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}

/* ---------- Toasts ---------- */

type Toast = { id: number; text: string; tone: "info" | "error" };
const ToastContext = createContext<(text: string, tone?: "info" | "error") => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: "info" | "error" = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "error" ? 7000 : 3500);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className={`toast ${t.tone}`}>{t.text}</div>)}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}

/* ---------- Key-value list ---------- */

export function KV({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="kv">
      {items.map(([k, v]) => (
        <div key={k} style={{ display: "contents" }}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}
