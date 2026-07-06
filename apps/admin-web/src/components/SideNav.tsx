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
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";

import { NAV_ITEMS, canAccess } from "../lib/auth/permissions";
import { useAuth } from "../lib/auth/auth-context";
import { BrandMark } from "./BrandMark";

const NAV_ICONS: Record<string, LucideIcon> = {
  "/dashboard": LayoutDashboard,
  "/operations/availability-calendar": CalendarDays,
  "/operations/csv-import": Upload,
  "/operations/ocr-paygate": ScanLine,
  "/operations/ocr-settlement": ScanLine,
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

type SideNavProps = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
};

export function SideNav({ collapsed, onToggleCollapsed }: SideNavProps) {
  const { user } = useAuth();

  return (
    <aside className={`side-nav${collapsed ? " is-collapsed" : ""}`}>
      <div className="side-nav-toggle-bar">
        <button
          type="button"
          className="side-nav-toggle"
          onClick={onToggleCollapsed}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "サイドバーを展開" : "サイドバーを縮小"}
        >
          {collapsed ? <ChevronRight size={18} aria-hidden="true" /> : <ChevronLeft size={18} aria-hidden="true" />}
        </button>
      </div>
      <div className="side-nav-body">
        <div className="side-nav-brand">
          <BrandMark size={collapsed ? 36 : 48} />
          {!collapsed ? (
            <div>
              <p className="eyebrow">{"\u30d5\u30a7\u30fc\u30ba1"}</p>
              <h2>{"\u7ba1\u7406\u753b\u9762"}</h2>
            </div>
          ) : null}
        </div>
        <nav className="side-nav-links" aria-label="メインメニュー">
        {NAV_ITEMS.filter((item) => canAccess(user?.role, item.allowedRoles)).map((item) => {
          const Icon = NAV_ICONS[item.to];
          return (
            <NavLink
              key={item.to}
              to={item.to}
              aria-label={collapsed ? item.label : undefined}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            >
              {Icon ? (
                <Icon
                  className="nav-link-icon"
                  size={collapsed ? 20 : 16}
                  aria-hidden="true"
                />
              ) : null}
              <span className="nav-link-text">
                <span className="nav-link-label">{item.label}</span>
                <span className="nav-link-description">{item.description}</span>
              </span>
            </NavLink>
          );
        })}
        </nav>
      </div>
    </aside>
  );
}