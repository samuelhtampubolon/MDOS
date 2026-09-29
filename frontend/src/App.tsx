import { useEffect, useState, type ReactNode } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useApprovals, useProject, useProjects } from "./api/hooks";
import { AuthProvider, useAuth } from "./auth";
import { ApiError, errorMessage } from "./api/client";
import { Callout, Icon, Spinner } from "./components/ui";
import { COPYRIGHT } from "./lib/about";
import Agents from "./pages/Agents";
import Approvals from "./pages/Approvals";
import DataPage from "./pages/Data";
import Experiments from "./pages/Experiments";
import Home from "./pages/Home";
import Journey from "./pages/journey/Journey";
import Login, { Locked } from "./pages/Login";
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
      <Link to="/" className="brand" aria-label="Marketing Decision OS home">
        <span className="brand-mark"><Icon name="journey" size={16} /></span>
        <span>
          <div className="brand-name">MDOS</div>
          <div className="brand-sub">Marketing Decision OS</div>
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
        <div className="row" style={{ gap: 6 }}>
          {mode === "local" && <Icon name="lock" size={12} />}
          {mode === "local" ? "Desktop: this computer only" : user?.organization}
        </div>
        {mode === "cloud" && (
          <button className="btn ghost sm" style={{ marginTop: 6, paddingLeft: 0 }} onClick={logout}>Sign out {user?.name}</button>
        )}
        <div className="legal">{COPYRIGHT}</div>
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
  const known = !!pid && projects.some((p) => p.id === pid);
  return (
    <label className="switcher">
      <span className="visually-hidden">Current project</span>
      <select className="select sm" value={known ? pid! : ""}
        onChange={(e) => e.target.value && navigate(`/p/${e.target.value}/${module}`)}>
        {!known && <option value="">Choose a project</option>}
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
      {open && <div className="scrim" aria-hidden onClick={() => setOpen(false)} />}
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

/** Placeholder shaped like a module page while the project loads. */
function PageSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the project">
      <span className="skeleton skeleton-line" style={{ width: 120 }} />
      <span className="skeleton" style={{ height: 28, width: "45%", margin: "8px 0 24px" }} />
      <span className="skeleton" style={{ height: 88, marginBottom: 24 }} />
      <span className="skeleton" style={{ height: 240 }} />
    </div>
  );
}

function ProjectRoute({ children }: { children: (pid: string) => ReactNode }) {
  const { pid = "" } = useParams();
  const { data: project, error, isLoading } = useProject(pid);
  const qc = useQueryClient();
  const demoStatus = project?.brief?.demo_status;
  const [wasBuilding, setWasBuilding] = useState(false);
  useEffect(() => {
    if (demoStatus === "building") setWasBuilding(true);
    else if (wasBuilding) {
      setWasBuilding(false);
      void qc.invalidateQueries({ queryKey: [pid] });
    }
  }, [demoStatus, wasBuilding, pid, qc]);
  if (isLoading) return <PageSkeleton />;
  if (error || !project) {
    const missing = error instanceof ApiError && (error.status === 404 || error.status === 403);
    return (
      <div className="empty">
        <h3>{missing ? "We can't find this project" : "This project could not be loaded"}</h3>
        <p>{missing ? "It may have been deleted, or the link belongs to another workspace." : errorMessage(error)}</p>
        <div className="row" style={{ marginTop: 16 }}>
          <Link to="/" className="btn primary">Go to your projects</Link>
          {!missing && <button className="btn" onClick={() => window.location.reload()}><Icon name="refresh" size={14} />Try again</button>}
        </div>
      </div>
    );
  }
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
  if (auth.status === "error") {
    return (
      <div className="content">
        <div className="empty">
          <h3>MDOS is not responding</h3>
          <p>The app could not reach its server ({auth.error}). If you use the desktop app, check that the MDOS window is still open.</p>
          <div style={{ marginTop: 16 }}>
            <button className="btn primary" onClick={() => window.location.reload()}><Icon name="refresh" size={14} />Try again</button>
          </div>
        </div>
      </div>
    );
  }
  if (auth.status === "signed_out") return <Login />;
  if (auth.status === "locked") return <Locked />;
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
