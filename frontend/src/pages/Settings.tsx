import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import { useApi, useAudit, useProject, useProjectMutation, useProvider } from "../api/hooks";
import { useAuth } from "../auth";
import { AGENT_LABELS } from "../components/domain";
import { Callout, Card, Icon, KV, PageHeader, useToast } from "../components/ui";
import { dateTime, sentence } from "../lib/format";

type Theme = "system" | "light" | "dark";

function applyTheme(theme: Theme) {
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  try {
    window.localStorage.setItem("mdos.theme", theme);
  } catch {
    /* storage unavailable: the choice lasts for this session only */
  }
}

export default function Settings({ pid }: { pid?: string }) {
  return (
    <div className="stack">
      <PageHeader eyebrow="Settings" title={pid ? "Project and workspace settings" : "Workspace settings"} />
      <div className="grid grid-2">
        <Appearance />
        <Workspace />
      </div>
      <Provider />
      {pid && <ProjectSettings pid={pid} />}
    </div>
  );
}

function Appearance() {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.dataset.theme as Theme | undefined) ?? "system");
  return (
    <Card title="Appearance">
      <div className="field" style={{ maxWidth: 260 }}>
        <label htmlFor="theme">Theme</label>
        <select id="theme" className="select" value={theme} onChange={(e) => { const t = e.target.value as Theme; setTheme(t); applyTheme(t); }}>
          <option value="system">Match my device</option><option value="light">Light</option><option value="dark">Dark</option>
        </select>
        <span className="hint">Charts use a color-blind-safe palette in both themes, and every chart has a table view.</span>
      </div>
    </Card>
  );
}

function Workspace() {
  const { mode, user } = useAuth();
  const { data: health } = useHealth();
  return (
    <Card title="Workspace">
      <KV items={[
        ["Mode", mode === "local" ? "Desktop (runs only on this computer)" : "Cloud (team accounts)"],
        ["Signed in as", user ? `${user.name} (${user.email})` : ""],
        ["Organization", user?.organization ?? ""],
        ["Version", health?.version ?? ""],
      ]} />
      {mode === "local" && (
        <div style={{ marginTop: 10 }}>
          <Callout>Desktop mode keeps all data in a local folder and only accepts connections from this computer. Use the cloud deployment to collaborate.</Callout>
        </div>
      )}
    </Card>
  );
}

/** The health endpoint lives outside the versioned API. */
function useHealth() {
  const [data, setData] = useState<{ version: string; mode: string } | null>(null);
  useEffect(() => {
    fetch("/api/health").then((r) => (r.ok ? r.json() : null)).then(setData).catch(() => setData(null));
  }, []);
  return { data };
}

function Provider() {
  const { data: provider } = useProvider();
  if (!provider) return null;
  return (
    <Card title="AI drafting" subtitle="Claude drafts wording for agents; statistics, simulations and gates never depend on it.">
      <div className="grid grid-2">
        <KV items={[
          ["Status", provider.mode === "claude" ? "Claude is on" : "Offline (deterministic drafting)"],
          ["Model", provider.model ?? "None"],
          ["Effort", provider.effort ?? "None"],
        ]} />
        <div className="stack-sm">
          <div className="small secondary">{provider.note}</div>
          <div className="small">To change it, set these on the server and restart:</div>
          <pre className="pre" style={{ margin: 0 }}>{`ANTHROPIC_API_KEY=...        # turns Claude on
MDOS_LLM_MODEL=claude-opus-5-5
MDOS_LLM_EFFORT=medium       # low, medium or high
MDOS_LLM_FALLBACKS=true      # server-side model fallback`}</pre>
        </div>
      </div>
    </Card>
  );
}

function ProjectSettings({ pid }: { pid: string }) {
  const { data: project } = useProject(pid);
  const { data: audit } = useAudit(pid);
  const { data: members } = useApi<{ user_id: string; email: string; name: string; role: string }[]>([pid, "members"], `/projects/${pid}/members`);
  const { mode } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [member, setMember] = useState({ email: "", role: "editor" });
  const [confirm, setConfirm] = useState("");
  const addMember = useProjectMutation(pid, () => api.post(`/projects/${pid}/members`, member));
  const [filter, setFilter] = useState("");
  if (!project) return null;
  const rows = (audit ?? []).filter((a) => !filter || `${a.action} ${a.entity_type} ${a.actor_id}`.toLowerCase().includes(filter.toLowerCase()));
  const remove = async () => {
    try {
      await api.del(`/projects/${pid}`);
      await qc.invalidateQueries({ queryKey: ["projects"] });
      try {
        window.localStorage.removeItem("mdos.lastProject");
      } catch {
        /* ignore */
      }
      toast("Project deleted.");
      navigate("/");
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  };
  return (
    <>
      <div className="grid grid-2">
        <Card title="Members" subtitle={`People with access to ${project.name}`}>
          <div className="stack-sm">
            {(members ?? []).map((m) => (
              <div key={m.user_id} className="list-item" style={{ padding: "6px 0" }}>
                <div className="grow"><div style={{ fontWeight: 600 }}>{m.name}</div><div className="small muted">{m.email}</div></div>
                <span className="badge">{sentence(m.role)}</span>
              </div>
            ))}
            {mode === "cloud" && project.my_role === "owner" && (
              <form className="row" onSubmit={(e) => { e.preventDefault(); addMember.mutate(undefined, {
                onSuccess: () => { toast("Member added."); setMember({ email: "", role: "editor" }); }, onError: (er) => toast(errorMessage(er), "error"),
              }); }}>
                <input className="input sm" type="email" required placeholder="colleague@company.com" aria-label="Member email" value={member.email}
                  onChange={(e) => setMember({ ...member, email: e.target.value })} />
                <select className="select sm" aria-label="Role" value={member.role} onChange={(e) => setMember({ ...member, role: e.target.value })}>
                  <option value="viewer">Viewer</option><option value="editor">Editor</option><option value="owner">Owner</option>
                </select>
                <button className="btn sm primary" disabled={addMember.isPending}>Add</button>
              </form>
            )}
            {mode === "local" && <span className="small muted">Sharing needs the cloud deployment.</span>}
          </div>
        </Card>
        <Card title="Delete project" subtitle="Removes the project, its data files and its history. This cannot be undone.">
          <div className="stack-sm">
            <label className="small" htmlFor="del-confirm">Type the project name to confirm: <strong>{project.name}</strong></label>
            <input id="del-confirm" className="input" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            <div><button className="btn danger" disabled={confirm !== project.name} onClick={remove}><Icon name="trash" size={14} />Delete project</button></div>
          </div>
        </Card>
      </div>
      <Card title="Audit log" subtitle="Every change by people and agents, newest first."
        actions={<input className="input sm" placeholder="Filter" aria-label="Filter audit log" value={filter} onChange={(e) => setFilter(e.target.value)} />}>
        <div className="table-wrap" style={{ maxHeight: 520 }}>
          <table className="table">
            <thead><tr><th>When</th><th>Who</th><th>Action</th><th>Item</th></tr></thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td className="small" style={{ whiteSpace: "nowrap" }}>{dateTime(a.created_at)}</td>
                  <td className="small">{a.actor_type === "agent" ? `${AGENT_LABELS[a.actor_id.replace("agent:", "")] ?? a.actor_id} agent` : sentence(a.actor_type)}</td>
                  <td><code className="small">{a.action}</code></td>
                  <td className="small secondary">{sentence(a.entity_type)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
