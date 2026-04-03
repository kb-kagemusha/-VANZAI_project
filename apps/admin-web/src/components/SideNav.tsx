import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  CalendarDays,
  Upload,
  ClipboardList,
  Users,
  Bell,
  Briefcase,
  Grid3X3,
  FileText,
  CreditCard,
  Receipt,
  UserRound,
  Tag,
  Database,
  ShieldCheck,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";

import { NAV_ITEMS, canAccess } from "../lib/auth/permissions";
import { useAuth } from "../lib/auth/auth-context";

const NAV_ICONS: Record<string, LucideIcon> = {
  "/dashboard": LayoutDashboard,
  "/operations/availability-calendar": CalendarDays,
  "/operations/csv-import": Upload,
  "/operations/actuals": ClipboardList,
  "/operations/assignments": Users,
  "/operations/assignment-responses": Bell,
  "/operations/projects": Briefcase,
  "/operations/shift-slots": Grid3X3,
  "/billing/invoices": FileText,
  "/billing/payouts": CreditCard,
  "/billing/expenses": Receipt,
  "/masters/workers": UserRound,
  "/masters/prices": Tag,
  "/masters/data": Database,
  "/audit-logs": ShieldCheck,
  "/operations/notices": MessageSquare,
};

export function SideNav() {
  const { user } = useAuth();

  return (
    <aside className="side-nav">
      <div className="side-nav-brand">
        <span className="brand-mark">V</span>
        <div>
          <p className="eyebrow">フェーズ1</p>
          <h2>管理画面</h2>
        </div>
      </div>
      <nav className="side-nav-links">
        {NAV_ITEMS.filter((item) => canAccess(user?.role, item.allowedRoles)).map((item) => {
          const Icon = NAV_ICONS[item.to];
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {Icon && (
                <Icon
                  size={16}
                  style={{ flexShrink: 0, opacity: 0.75, alignSelf: "center" }}
                  aria-hidden="true"
                />
              )}
              <span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                <span className="nav-link-label">{item.label}</span>
                <span className="nav-link-description">{item.description}</span>
              </span>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}