/* Authentication bootstrap: the desktop build gets a local session automatically; cloud mode uses accounts. */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, errorMessage, getToken, setToken } from "./api/client";
import type { User } from "./api/types";

interface AuthState {
  status: "loading" | "ready" | "signed_out" | "error";
  mode: "local" | "cloud";
  registration: boolean;
  user: User | null;
  error: string;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; name: string; organization: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<Omit<AuthState, "login" | "register" | "logout">>({
    status: "loading", mode: "local", registration: false, user: null, error: "",
  });

  const boot = useCallback(async () => {
    try {
      const mode = await api.get<{ mode: "local" | "cloud"; registration: boolean }>("/auth/mode");
      if (mode.mode === "local") {
        const session = await api.post<{ access_token: string; user: User }>("/auth/local-session");
        setToken(session.access_token);
        setState({ status: "ready", mode: "local", registration: false, user: session.user, error: "" });
        return;
      }
      if (getToken()) {
        try {
          const user = await api.get<User>("/auth/me");
          setState({ status: "ready", mode: "cloud", registration: mode.registration, user, error: "" });
          return;
        } catch {
          setToken(null);
        }
      }
      setState({ status: "signed_out", mode: "cloud", registration: mode.registration, user: null, error: "" });
    } catch (err) {
      setState((s) => ({ ...s, status: "error", error: errorMessage(err) }));
    }
  }, []);

  useEffect(() => {
    void boot();
  }, [boot]);

  const login = async (email: string, password: string) => {
    const res = await api.post<{ access_token: string; user: User }>("/auth/login", { email, password });
    setToken(res.access_token, true);
    setState((s) => ({ ...s, status: "ready", user: res.user, error: "" }));
  };
  const register = async (data: { email: string; password: string; name: string; organization: string }) => {
    const res = await api.post<{ access_token: string; user: User }>("/auth/register", data);
    setToken(res.access_token, true);
    setState((s) => ({ ...s, status: "ready", user: res.user, error: "" }));
  };
  const logout = () => {
    setToken(null);
    setState((s) => ({ ...s, status: "signed_out", user: null }));
  };

  return <AuthContext.Provider value={{ ...state, login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
