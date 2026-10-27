/* Authentication bootstrap. The session is an HttpOnly cookie set by the server; this app never sees or stores it.

   Desktop: the MDOS window opens the browser with a per-launch key in the address fragment (#key=...). The key is
   read once, removed from the address bar, and exchanged for a session. Without it the app shows a locked screen.
   Cloud: email and password accounts. */

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError, errorMessage, onUnauthorized } from "./api/client";
import type { User } from "./api/types";

type Status = "loading" | "ready" | "signed_out" | "locked" | "error";

interface ModeInfo {
  mode: "local" | "cloud";
  registration: boolean;
  local_key_required?: boolean;
}

interface AuthState {
  status: Status;
  mode: "local" | "cloud";
  registration: boolean;
  user: User | null;
  error: string;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; name: string; organization: string }) => Promise<void>;
  logout: () => Promise<void>;
  logoutEverywhere: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

let launchKey: string | null | undefined;

/** Read the desktop launch key once and remove it from the address bar and history. */
function takeLaunchKey(): string | null {
  if (launchKey !== undefined) return launchKey;
  const match = /(?:^#|&)key=([^&]+)/.exec(window.location.hash);
  launchKey = match ? decodeURIComponent(match[1]) : null;
  if (match) window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search);
  return launchKey;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [state, setState] = useState<Omit<AuthState, "login" | "register" | "logout" | "logoutEverywhere">>({
    status: "loading", mode: "local", registration: false, user: null, error: "",
  });
  const modeRef = useRef<ModeInfo | null>(null);

  const openLocalSession = useCallback(async (info: ModeInfo): Promise<boolean> => {
    const key = takeLaunchKey();
    if (info.local_key_required && !key) return false;
    try {
      const session = await api.post<{ user: User }>("/auth/local-session", key ? { key } : {});
      setState({ status: "ready", mode: "local", registration: false, user: session.user, error: "" });
      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return false;
      throw err;
    }
  }, []);

  const boot = useCallback(async () => {
    try {
      const info = await api.get<ModeInfo>("/auth/mode");
      modeRef.current = info;
      const freshLaunch = info.mode === "local" && takeLaunchKey();
      if (!freshLaunch) {
        try {
          const user = await api.get<User>("/auth/me");
          setState({ status: "ready", mode: info.mode, registration: info.registration, user, error: "" });
          return;
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 401)) throw err;
        }
      }
      if (info.mode === "local") {
        if (!(await openLocalSession(info))) {
          setState({ status: "locked", mode: "local", registration: false, user: null, error: "" });
        }
        return;
      }
      setState({ status: "signed_out", mode: "cloud", registration: info.registration, user: null, error: "" });
    } catch (err) {
      setState((s) => ({ ...s, status: "error", error: errorMessage(err) }));
    }
  }, [openLocalSession]);

  useEffect(() => {
    void boot();
  }, [boot]);

  // A session can end while the app is open: it expired, the account signed out everywhere, or MDOS restarted.
  const recovering = useRef(false);
  useEffect(() => {
    onUnauthorized(() => {
      if (recovering.current) return;
      recovering.current = true;
      const info = modeRef.current;
      const end = (status: Status) => {
        qc.clear();
        setState((s) => ({ ...s, status, user: null }));
      };
      if (info?.mode !== "local") {
        end("signed_out");
        recovering.current = false;
        return;
      }
      openLocalSession(info)
        .then((ok) => (ok ? void qc.invalidateQueries() : end("locked")))
        .catch(() => end("locked"))
        .finally(() => { recovering.current = false; });
    });
    return () => onUnauthorized(null);
  }, [qc, openLocalSession]);

  const login = async (email: string, password: string) => {
    const res = await api.post<{ user: User }>("/auth/login", { email, password });
    qc.clear();
    setState((s) => ({ ...s, status: "ready", user: res.user, error: "" }));
  };
  const register = async (data: { email: string; password: string; name: string; organization: string }) => {
    const res = await api.post<{ user: User }>("/auth/register", data);
    qc.clear();
    setState((s) => ({ ...s, status: "ready", user: res.user, error: "" }));
  };
  const signedOut = () => {
    qc.clear();
    setState((s) => ({ ...s, status: "signed_out", user: null }));
  };
  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } finally {
      signedOut();
    }
  };
  const logoutEverywhere = async () => {
    await api.post("/auth/logout-all");
    signedOut();
  };

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout, logoutEverywhere }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
