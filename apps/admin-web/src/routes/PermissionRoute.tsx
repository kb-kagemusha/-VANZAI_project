import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useAuth } from "../lib/auth/auth-context";
import { NAV_ITEMS, canView } from "../lib/auth/permissions";
import type { UserRole } from "../types/api";

export function PermissionRoute({ children, allowedRoles }: { children: ReactNode; allowedRoles: UserRole[] }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!canView(user, location.pathname, allowedRoles)) {
    if (location.pathname === "/dashboard") {
      const first = NAV_ITEMS.find(item => !item.to.startsWith("/dashboard") && canView(user, item.to, item.allowedRoles));
      if (first) return <Navigate to={first.to} replace />;
    }
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}
