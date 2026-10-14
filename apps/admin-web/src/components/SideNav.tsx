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
  ScrollText,
  CreditCard,
  Receipt,
  UserRound,
  Tag,
  Database,
  ShieldCheck,
  MessageSquare,
  ScanLine,
  Eye,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";

import { NAV_ITEMS, canAccess } from "../lib/auth/permissions";
import { useAuth } from "../lib/auth/auth-context";
import { useAppVersion } from "../lib/hooks/useAppVersion";
import { formatRole } from "../lib/formatters";
import { NAV_GROUP_ORDER, navGroupFor } from "../pages/dashboardPreviewModel";
import { BrandMark } from "./BrandMark";

const NAV_ICONS: Record<string, LucideIcon> = {
  "/dashboard": LayoutDashboard,
  "/dashboard/preview": Eye,
  "/operations/availability-calendar": CalendarDays,
  "/operations/csv-import": Upload,
  "/operations/ocr": ScanLine,
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
  "/operations/order-requests": ScrollText,
  "/operations/notices": MessageSquare,
  "/operations/registration-requests": ClipboardList,
};

type SideNavProps = {
  collapsed: boolean;
  onToggleCollapsed: () => void;
};

export function SideNav({ collapsed, onToggleCollapsed }: SideNavProps) {
  const { user } = useAuth();
  const { currentVersion, hasUpdate, refreshNow } = useAppVersion();
  const displayedName = user?.display_name || user?.username || "";
  const visibleItems = NAV_ITEMS.filter((item) => canAccess(user?.role, item.allowedRoles));
  const sections = NAV_GROUP_ORDER.map((group) => ({
    group,
    items: visibleItems.filter((item) => navGroupFor(item.to) === group),
  })).filter((section) => section.items.length > 0);

  return (
    <aside className={`side-nav${collapsed ? " is-collapsed" : ""}`}>
      <div className="side-nav-body">
        <div className="side-nav-brand">
          <BrandMark size={collapsed ? 36 : 36} />
          {!collapsed ? (
            <div>
              <h2>VANZAI</h2>
              <p className="side-nav-version">ver.{currentVersion}</p>
            </div>
          ) : null}
          {hasUpdate ? (
            <button type="button" className="side-nav-version-update" onClick={refreshNow} aria-label="新しい版を反映">
              {collapsed ? "更新" : "新しい版を反映"}
            </button>
          ) : null}
        </div>
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
        <nav className="side-nav-links" aria-label="メインメニュー">
          {sections.map((section) => (
            <div key={section.group}>
              <p className="nav-group-label">{section.group}</p>
              {section.items.map((item) => {
                const Icon = NAV_ICONS[item.to];
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end
                    aria-label={collapsed ? item.label : undefined}
                    className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
                  >
                    {Icon ? <Icon className="nav-link-icon" size={20} aria-hidden="true" /> : null}
                    <span className="nav-link-text">
                      <span className="nav-link-label">{item.label}</span>
                    </span>
                  </NavLink>
                );
              })}
            </div>
          ))}
        </nav>
      </div>
      <NavLink
        to="/account/profile"
        className={({ isActive }) => `side-nav-user side-nav-user-button${isActive ? " is-active" : ""}`}
        aria-label={`${displayedName || "ユーザー"}のプロフィール`}
      >
        <span className="side-nav-avatar" aria-hidden="true">{displayedName.slice(0, 1) || "V"}</span>
        <span className="side-nav-user-copy">
          <span className="side-nav-user-name">{displayedName}</span>
          <span className="side-nav-user-role">{formatRole(user?.role)}</span>
        </span>
      </NavLink>
    </aside>
  );
}
