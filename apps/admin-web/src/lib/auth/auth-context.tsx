import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  ApiError,
  clearStoredAccessToken,
  ensurePersistentSession,
  getCurrentUser,
  getStoredAccessToken,
  getStoredRefreshToken,
  refreshStoredSession,
  requestToken,
  setStoredSession,
} from "../api/client";
import { DASHBOARD_ROLES, canAccess } from "./permissions";
import type { AuthUser } from "../../types/api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function canUseAdminConsole(user: AuthUser): boolean {
  return canAccess(user.role, DASHBOARD_ROLES);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    let active = true;

    async function restoreSession() {
      for (let attempt = 0; attempt < 3; attempt += 1) {
        if (!getStoredAccessToken()) {
          await refreshStoredSession();
        }
        if (!getStoredAccessToken()) {
          if (active) {
            setStatus("unauthenticated");
          }
          return;
        }

        try {
          const currentUser = await getCurrentUser();
          if (!canUseAdminConsole(currentUser)) {
            clearStoredAccessToken();
            if (active) {
              setUser(null);
              setStatus("unauthenticated");
            }
            return;
          }
          try {
            await ensurePersistentSession();
          } catch {
            // 更新用トークンの保存に失敗しても、今のログインは維持する
          }
          if (active) {
            setUser(currentUser);
            setStatus("authenticated");
          }
          return;
        } catch (error) {
          const status = error instanceof ApiError ? error.status : 0;
          if (status === 403) {
            clearStoredAccessToken();
            if (active) {
              setUser(null);
              setStatus("unauthenticated");
            }
            return;
          }
          const sessionGone = !getStoredAccessToken() && !getStoredRefreshToken();
          if (status === 401 && sessionGone) {
            if (active) {
              setUser(null);
              setStatus("unauthenticated");
            }
            return;
          }
          if (attempt < 2) {
            await new Promise((resolve) => window.setTimeout(resolve, 800));
            continue;
          }
          if (active) {
            setUser(null);
            setStatus("unauthenticated");
          }
        }
      }
    }

    function handleUnauthorized() {
      if (active) {
        startTransition(() => {
          setUser(null);
          setStatus("unauthenticated");
        });
      }
    }

    restoreSession();
    window.addEventListener("vanzai:unauthorized", handleUnauthorized);

    return () => {
      active = false;
      window.removeEventListener("vanzai:unauthorized", handleUnauthorized);
    };
  }, []);

  const value: AuthContextValue = {
    status,
    user,
    async login(username: string, password: string) {
      const token = await requestToken(username, password);
      setStoredSession(token.access_token, token.refresh_token);
      const currentUser = await getCurrentUser();
      if (!canUseAdminConsole(currentUser)) {
        clearStoredAccessToken();
        setUser(null);
        setStatus("unauthenticated");
        throw new ApiError(403, "このアカウントは管理画面を利用できません");
      }
      setUser(currentUser);
      setStatus("authenticated");
    },
    logout() {
      clearStoredAccessToken();
      setUser(null);
      setStatus("unauthenticated");
    },
    async refreshUser() {
      const currentUser = await getCurrentUser();
      if (!canUseAdminConsole(currentUser)) {
        clearStoredAccessToken();
        setUser(null);
        setStatus("unauthenticated");
        throw new ApiError(403, "このアカウントは管理画面を利用できません");
      }
      setUser(currentUser);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}