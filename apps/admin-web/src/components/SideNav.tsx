import { useEffect, useId, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";
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
  ChevronsUpDown,
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
  onEditProfile: () => void;
};

export function SideNav({ collapsed, onToggleCollapsed, onEditProfile }: SideNavProps) {
  const { user, logout } = useAuth();
  const { currentVersion, hasUpdate, refreshNow } = useAppVersion();
  const [menuOpen, setMenuOpen] = useState(false);
  const userRef = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const displayedName = user?.display_name || user?.username || "";
  const visibleItems = NAV_ITEMS.filter((item) => canAccess(user?.role, item.allowedRoles));
  const sections = NAV_GROUP_ORDER.map((group) => ({
    group,
    items: visibleItems.filter((item) => navGroupFor(item.to) === group),
  })).filter((section) => section.items.length > 0);

  useEffect(() => {
    if (!menuOpen) {
      return;
    }
    const onPointerDown = (event: MouseEvent) => {
      if (!userRef.current?.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);

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
      <div className="side-nav-user" ref={userRef}>
        {menuOpen ? (
          <div className="side-nav-user-menu" id={menuId} role="menu">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setMenuOpen(false);
                onEditProfile();
              }}
            >
              プロフィール
            </button>
            <Link role="menuitem" to="/account/change-password" onClick={() => setMenuOpen(false)}>
              パスワード変更
            </Link>
            {user?.role === "admin" ? (
              <Link role="menuitem" to="/operations/order-requests/deleted" onClick={() => setMenuOpen(false)}>
                削除済み案件一覧
              </Link>
            ) : null}
            <button type="button" role="menuitem" onClick={logout}>
              ログアウト
            </button>
          </div>
        ) : null}
        <button
          type="button"
          className="side-nav-user-button"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-controls={menuId}
          onClick={() => setMenuOpen((current) => !current)}
        >
          <span className="side-nav-avatar" aria-hidden="true">{displayedName.slice(0, 1) || "V"}</span>
          <span className="side-nav-user-copy">
            <span className="side-nav-user-name">{displayedName}</span>
            <span className="side-nav-user-role">{formatRole(user?.role)}</span>
          </span>
          <ChevronsUpDown className="side-nav-user-chevron" size={16} aria-hidden="true" />
        </button>
      </div>
    </aside>
  );
}
