import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";

import { App } from "./app/App";
import { AuthProvider } from "./lib/auth/auth-context";
import { queryClient } from "./lib/query/query-client";
import { applyStoredTheme, ThemeProvider } from "./lib/theme";
import "./styles/global.css";

applyStoredTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <BrowserRouter>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          <App />
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  </BrowserRouter>,
);