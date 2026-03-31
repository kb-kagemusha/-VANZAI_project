import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "../lib/auth/auth-context";

export function WorkerOnlyRoute() {
  const { user } = useAuth();

  if (user?.role !== "worker") {
    return <Navigate to="/403" replace />;
  }

  return <Outlet />;
}