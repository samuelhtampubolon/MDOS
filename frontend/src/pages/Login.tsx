import { useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth";
import { Callout, Icon } from "../components/ui";

export default function Login() {
  const { login, register, registration } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [form, setForm] = useState({ email: "", password: "", name: "", organization: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "login") await login(form.email, form.password);
      else await register(form);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: "100%", display: "grid", placeItems: "center", padding: 16 }}>
      <form className="card" style={{ width: "min(420px, 100%)" }} onSubmit={submit}>
        <div className="card-body stack">
          <div className="brand" style={{ padding: 0 }}>
            <span className="brand-mark"><Icon name="journey" size={18} /></span>
            <span>
              <div className="brand-name">Marketing Decision OS</div>
              <div className="brand-sub">From business question to defensible evidence</div>
            </span>
          </div>
          <h1>{mode === "login" ? "Sign in" : "Create your workspace"}</h1>
          {error && <Callout tone="critical">{error}</Callout>}
          {mode === "register" && (
            <>
              <div className="field">
                <label htmlFor="name">Your name</label>
                <input id="name" className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="org">Organization</label>
                <input id="org" className="input" required value={form.organization} onChange={(e) => setForm({ ...form, organization: e.target.value })} />
              </div>
            </>
          )}
          <div className="field">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" className="input" required autoComplete="email" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" type="password" className="input" required minLength={mode === "register" ? 10 : 1}
              autoComplete={mode === "login" ? "current-password" : "new-password"} value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
            {mode === "register" && <span className="hint">At least 10 characters.</span>}
          </div>
          <button className="btn primary lg" disabled={busy}>{busy ? "Please wait" : mode === "login" ? "Sign in" : "Create workspace"}</button>
          {registration && (
            <button type="button" className="btn ghost" onClick={() => setMode(mode === "login" ? "register" : "login")}>
              {mode === "login" ? "New here? Create a workspace" : "Already have an account? Sign in"}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
