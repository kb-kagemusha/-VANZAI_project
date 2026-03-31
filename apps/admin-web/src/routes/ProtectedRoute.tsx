import { Navigate, Outlet, useLocation } from "react-router-dom";

import { LoadingOverlay } from "../components/LoadingOverlay";
import { useAuth } from "../lib/auth/auth-context";

export function ProtectedRoute() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <LoadingOverlay label="セッション復元中..." />;
  }

  if (status === "unauthenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}