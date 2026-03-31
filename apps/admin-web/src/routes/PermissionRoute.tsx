import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "../lib/auth/auth-context";
import { canAccess } from "../lib/auth/permissions";
import type { UserRole } from "../types/api";

export function PermissionRoute({ children, allowedRoles }: { children: ReactNode; allowedRoles: UserRole[] }) {
  const { user } = useAuth();

  if (!canAccess(user?.role, allowedRoles)) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}