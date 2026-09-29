import { useState } from "react";
import { useApi, useApprovals } from "../api/hooks";
import type { Approval } from "../api/types";
import { AGENT_LABELS, ApprovalCard } from "../components/domain";
import { Card, Empty, PageHeader, StatusBadge, Tabs } from "../components/ui";
import { dateTime, sentence } from "../lib/format";

export default function Approvals({ pid }: { pid: string }) {
  const [view, setView] = useState<"pending" | "history">("pending");
  const { data: pending } = useApprovals(pid);
  const { data: history } = useApi<Approval[]>([pid, "approvals-history"], view === "history" ? `/projects/${pid}/approvals?status=` : null);
  return (
    <div className="stack">
      <PageHeader eyebrow="Human gates" title="Approvals"
        description="Agents and teammates propose; people decide. Cleaning plans, insights, hypothesis verdicts, recommendations, decisions, experiment launches and final reports all wait here." />
      <Tabs value={view} onChange={setView} tabs={[{ key: "pending", label: `Waiting (${pending?.length ?? 0})` }, { key: "history", label: "History" }]} />
      {view === "pending" ? (
        !pending?.length ? <Empty title="Nothing is waiting for you">New requests appear here and in the sidebar count.</Empty> : (
          <Card><div className="stack">{pending.map((a) => <ApprovalCard key={a.id} pid={pid} approval={a} />)}</div></Card>
        )
      ) : (
        <Card>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Request</th><th>Requested by</th><th>Requested</th><th>Status</th><th>Decided</th><th>Rationale</th></tr></thead>
              <tbody>
                {(history ?? []).map((a) => (
                  <tr key={a.id}>
                    <td>{a.summary}</td>
                    <td className="small">{a.requested_by.startsWith("agent:") ? `${AGENT_LABELS[a.requested_by.slice(6)] ?? sentence(a.requested_by.slice(6))} agent` : "A person"}</td>
                    <td className="small">{dateTime(a.requested_at)}</td>
                    <td><StatusBadge status={a.status} /></td>
                    <td className="small">{dateTime(a.decided_at)}</td>
                    <td className="small secondary">{a.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
