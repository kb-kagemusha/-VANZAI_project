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
  ScanLine,
  type LucideIcon,
} from "lucide-react";

import { NAV_ITEMS, canAccess } from "../lib/auth/permissions";
import { useAuth } from "../lib/auth/auth-context";
import { BrandMark } from "./BrandMark";

const NAV_ICONS: Record<string, LucideIcon> = {
  "/dashboard": LayoutDashboard,
  "/operations/availability-calendar": CalendarDays,
  "/operations/csv-import": Upload,
  "/operations/ocr-receipt": ScanLine,
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
  "/operations/registration-requests": ClipboardList,
};

export function SideNav() {
  const { user } = useAuth();

  return (
    <aside className="side-nav">
      <div className="side-nav-brand">
        <BrandMark />
        <div>
          <p className="eyebrow">繝輔ぉ繝ｼ繧ｺ1</p>
          <h2>邂｡逅・判髱｢</h2>
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
