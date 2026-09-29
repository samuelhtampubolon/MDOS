import { useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { useApprovals, useProject, useProjects } from "./api/hooks";
import { AuthProvider, useAuth } from "./auth";
import { Callout, Icon, Spinner } from "./components/ui";
import Agents from "./pages/Agents";
import Approvals from "./pages/Approvals";
import DataPage from "./pages/Data";
import Experiments from "./pages/Experiments";
import Home from "./pages/Home";
import Journey from "./pages/journey/Journey";
import Login from "./pages/Login";
import Reports from "./pages/Reports";
import Research from "./pages/research/Research";
import Settings from "./pages/Settings";
import Strategy from "./pages/strategy/Strategy";

const LAST_PROJECT = "mdos.lastProject";

function rememberProject(pid: string) {
  try {
    window.localStorage.setItem(LAST_PROJECT, pid);
  } catch {
    /* ignore */
  }
}

function lastProject(): string | null {
  try {
    return window.localStorage.getItem(LAST_PROJECT);
  } catch {
    return null;
  }
}

const MODULES = [
  { key: "research", label: "Research", icon: "research" },
  { key: "strategy", label: "Strategy", icon: "strategy" },
  { key: "journey", label: "Journey", icon: "journey" },
  { key: "data", label: "Data", icon: "data" },
  { key: "agents", label: "Agents", icon: "agents" },
  { key: "reports", label: "Reports", icon: "reports" },
  { key: "experiments", label: "Experiments", icon: "experiments" },
];

function Sidebar({ pid, open, onNavigate }: { pid: string | null; open: boolean; onNavigate: () => void }) {
  const { data: approvals } = useApprovals(pid ?? undefined);
  const { mode, user, logout } = useAuth();
  const pending = approvals?.length ?? 0;
  return (
    <nav className={`sidebar ${open ? "open" : ""}`} aria-label="Main navigation" onClick={onNavigate}>
      <Link to="/" className="brand">
        <span className="brand-mark"><Icon name="journey" size={18} /></span>
        <span>
          <div className="brand-name">Marketing Decision OS</div>
          <div className="brand-sub">Research · Strategy · Journey</div>
        </span>
      </Link>
      <NavLink to="/" end className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
        <Icon name="home" />Home
      </NavLink>
      <div className="nav-label">Project</div>
      {MODULES.map((m) =>
        pid ? (
          <NavLink key={m.key} to={`/p/${pid}/${m.key}`} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
            <Icon name={m.icon} />
            {m.label}
          </NavLink>
        ) : (
          <span key={m.key} className="nav-item disabled" title="Open a project first"><Icon name={m.icon} />{m.label}</span>
        ),
      )}
      {pid && (
        <NavLink to={`/p/${pid}/approvals`} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
          <Icon name="approvals" />Approvals
          {pending > 0 && <span className="count" aria-label={`${pending} pending`}>{pending}</span>}
        </NavLink>
      )}
      <div className="nav-label">Workspace</div>
      <NavLink to={pid ? `/p/${pid}/settings` : "/settings"} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
        <Icon name="settings" />Settings
      </NavLink>
      <div className="sidebar-footer">
        <div>{mode === "local" ? "Desktop mode (this computer)" : user?.organization}</div>
        {mode === "cloud" && (
          <button className="btn ghost sm" style={{ marginTop: 6, paddingLeft: 0 }} onClick={logout}>Sign out {user?.name}</button>
        )}
      </div>
    </nav>
  );
}

function ProjectSwitcher({ pid }: { pid: string | null }) {
  const { data: projects } = useProjects();
  const navigate = useNavigate();
  const location = useLocation();
  if (!projects?.length) return null;
  const module = location.pathname.split("/")[3] || "research";
  return (
    <label className="row" style={{ gap: 6 }}>
      <span className="visually-hidden">Current project</span>
      <select className="select sm" style={{ maxWidth: 360 }} value={pid ?? ""}
        onChange={(e) => e.target.value && navigate(`/p/${e.target.value}/${module}`)}>
        {!pid && <option value="">Choose a project</option>}
        {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </label>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<string>(() => document.documentElement.dataset.theme ?? "system");
  const cycle = () => {
    const next = theme === "system" ? "dark" : theme === "dark" ? "light" : "system";
    setTheme(next);
    if (next === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem("mdos.theme", next);
    } catch {
      /* ignore */
    }
  };
  return (
    <button className="btn ghost sm" onClick={cycle} title="Theme: system, dark, light" aria-label={`Theme: ${theme}`}>
      <Icon name={theme === "dark" ? "moon" : "sun"} size={14} />
      {theme === "system" ? "Auto" : theme === "dark" ? "Dark" : "Light"}
    </button>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const match = /^\/p\/([^/]+)/.exec(location.pathname);
  const pid = match ? match[1] : lastProject();
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (match) rememberProject(match[1]);
  }, [match?.[1]]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="shell">
      <Sidebar pid={pid} open={open} onNavigate={() => setOpen(false)} />
      <div className="main">
        <header className="topbar">
          <button className="btn ghost icon menu-button" aria-label="Open menu" onClick={() => setOpen(true)}><Icon name="menu" /></button>
          <ProjectSwitcher pid={match ? match[1] : null} />
          <div className="spacer" />
          <ThemeToggle />
        </header>
        <main className="content" id="main">{children}</main>
      </div>
    </div>
  );
}

function ProjectRoute({ children }: { children: (pid: string) => ReactNode }) {
  const { pid = "" } = useParams();
  const { data: project, error, isLoading } = useProject(pid);
  if (isLoading) return <Spinner />;
  if (error || !project) return <Callout tone="critical">This project was not found or you do not have access to it.</Callout>;
  return (
    <>
      {project.brief?.demo_status === "building" && (
        <div style={{ marginBottom: 16 }}>
          <Callout>
            <span className="row"><span className="spinner" aria-hidden /> The agents are building the demo project: research design, analysis,
              strategy scenarios and the journey map. This takes a few seconds.</span>
          </Callout>
        </div>
      )}
      {project.brief?.demo_status === "failed" && (
        <div style={{ marginBottom: 16 }}><Callout tone="critical">Demo seeding failed: {String(project.brief.demo_error ?? "")}</Callout></div>
      )}
      {children(pid)}
    </>
  );
}

function Routed() {
  const auth = useAuth();
  if (auth.status === "loading") return <div className="content"><Spinner label="Starting Marketing Decision OS" /></div>;
  if (auth.status === "error") return <div className="content"><Callout tone="critical">Could not reach the MDOS server: {auth.error}</Callout></div>;
  if (auth.status === "signed_out") return <Login />;
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/p/:pid" element={<ProjectRoute>{(pid) => <Navigate to={`/p/${pid}/research`} replace />}</ProjectRoute>} />
        <Route path="/p/:pid/research/:tab?" element={<ProjectRoute>{(pid) => <Research pid={pid} />}</ProjectRoute>} />
        <Route path="/p/:pid/strategy" element={<ProjectRoute>{(pid) => <Strategy pid={pid} />}</ProjectRoute>} />
        <Route path="/p/:pid/journey" element={<ProjectRoute>{(pid) => <Journey pid={pid} />}</ProjectRoute>} />
        <Route path="/p/:pid/data" element={<ProjectRoute>{(pid) => <DataPage pid={pid} />}</ProjectRoute>} />
        <Route path="/p/:pid/agents" element={<ProjectRoute>{(pid) => <Agents pid={pid} />}</ProjectRoute>} />
        <Route path="/p/:pid/reports" element={<ProjectRoute>{(pid) => <Reports pid={pid} />}</ProjectRoute>} />
        <Route path="/p/:pid/experiments" element={<ProjectRoute>{(pid) => <Experiments pid={pid} />}</ProjectRoute>} />
        <Route path="/p/:pid/approvals" element={<ProjectRoute>{(pid) => <Approvals pid={pid} />}</ProjectRoute>} />
        <Route path="/p/:pid/settings" element={<ProjectRoute>{(pid) => <Settings pid={pid} />}</ProjectRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routed />
    </AuthProvider>
  );
}
