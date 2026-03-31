import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../lib/auth/auth-context";

export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <div className="fullscreen-state">セッションを確認しています...</div>;
  }

  if (status !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}