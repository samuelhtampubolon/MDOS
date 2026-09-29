// MDOS, Marketing Decision OS. Copyright © 2026 Samuel Hasudungan Tampubolon. Released under the MIT License.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { ApiError } from "./api/client";
import { ToastProvider } from "./components/ui";
// Bundled typefaces (served from this origin, so they work offline and under the Content Security Policy).
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-sans/latin-ext-400.css";
import "@fontsource/ibm-plex-sans/latin-ext-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";
import "./styles/charts.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5_000,
      // Retry once for network and server errors; a 4xx answer (not found, no access) will not change on retry.
      retry: (failures, error) => failures < 1 && !(error instanceof ApiError && error.status < 500),
      refetchOnWindowFocus: false,
      placeholderData: (prev: unknown) => prev,
    },
  },
});

try {
  const theme = window.localStorage.getItem("mdos.theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
} catch {
  /* storage unavailable */
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ToastProvider>
          <App />
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
