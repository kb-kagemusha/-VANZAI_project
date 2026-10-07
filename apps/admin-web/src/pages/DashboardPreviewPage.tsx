import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import {
  Bell,
  Briefcase,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  CreditCard,
  Database,
  Eye,
  FileText,
  Grid3X3,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  MessageSquare,
  Receipt,
  ScanLine,
  ScrollText,
  Settings,
  ShieldCheck,
  Sun,
  Tag,
  Upload,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";

import { BrandMark } from "../components/BrandMark";
import { ApiError, getDashboard } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import { NAV_ITEMS, canAccess } from "../lib/auth/permissions";
import { currentMonthInput, formatDate, formatPeriodKey, formatRole, formatStatus, minutesToHours, toPeriodKey } from "../lib/formatters";
import { useAppVersion } from "../lib/hooks/useAppVersion";
import {
  KPI_ITEMS,
  NAV_GROUP_ORDER,
  activeNavPath,
  closingBarState,
  navGroupFor,
  previewStatusLabel,
  previewStatusTone,
  unprocessedCount,
} from "./dashboardPreviewModel";
import type { DashboardClosingStatus, DashboardUnprocessedItem, DashboardVarianceAlert } from "../types/api";
import { PreviewDemoBoard } from "./PreviewDemoBoard";
import { PreviewProfile } from "./PreviewProfile";
import { readSealColor, SEAL_KEY } from "./previewSeal";
import "../styles/apex-preview.css";

const THEME_KEY = "vanzai.preview.theme";

const NARROW_QUERY = "(max-width: 1099px)";
const FOCUSABLE_SELECTOR = "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])";

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

type PendingAssignmentResponseDetail = {
  assignment_id: string;
  project_name: string;
  worker_name: string;
  work_date: string;
  shift_label: string | null;
  escalation_level: "watch" | "escalate";
  escalation_reasons: string[];
};

function useMatchMedia(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);

  useEffect(() => {
    const media = window.matchMedia(query);
    const onChange = () => setMatches(media.matches);
    onChange();
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

function listFocusable(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)].filter((element) => element.getClientRects().length > 0);
}

function setInert(element: HTMLElement | null, inert: boolean) {
  if (!element) {
    return;
  }
  if (inert) {
    element.setAttribute("inert", "");
    return;
  }
  element.removeAttribute("inert");
}

export function DashboardPreviewPage() {
  const { user, logout } = useAuth();
  const { currentVersion } = useAppVersion();
  const location = useLocation();
  const isNarrow = useMatchMedia(NARROW_QUERY);
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [showBilling, setShowBilling] = useState(false);
  const [darkMode, setDarkMode] = useState(() => window.localStorage.getItem(THEME_KEY) === "dark");
  const [sealColor, setSealColor] = useState(readSealColor);
  const [accountOpen, setAccountOpen] = useState(false);
  const periodKey = toPeriodKey(monthValue);
  const sidebarRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const accountRef = useRef<HTMLDivElement>(null);
  const drawerWasOpen = useRef(false);
  const sidebarId = useId();
  const sidebarTitleId = useId();

  const dashboardQuery = useQuery({
    queryKey: ["dashboard-preview", periodKey],
    queryFn: () => getDashboard(periodKey),
    placeholderData: undefined,
  });

  const visibleItems = NAV_ITEMS.filter((item) => canAccess(user?.role, item.allowedRoles));
  const activeTo = activeNavPath(location.pathname, visibleItems.map((item) => item.to));
  const sections = NAV_GROUP_ORDER.map((group) => ({
    group,
    items: visibleItems.filter((item) => navGroupFor(item.to) === group),
  })).filter((section) => section.items.length > 0);
  const displayedName = user?.display_name || user?.username || "";
  const initial = displayedName.slice(0, 1) || "V";
  const showProfile = location.pathname.startsWith("/dashboard/preview/profile");
  const rootClass = [
    "apex-preview",
    !isNarrow && collapsed ? "is-collapsed" : "",
    isNarrow ? "is-narrow" : "",
    isNarrow && drawerOpen ? "is-drawer-open" : "",
    darkMode ? "is-dark" : "",
  ].filter(Boolean).join(" ");

  useEffect(() => {
    if (!isNarrow) {
      setDrawerOpen(false);
    }
  }, [isNarrow]);

  useEffect(() => {
    if (!accountOpen) return;
    const onPointer = (event: MouseEvent) => {
      if (!accountRef.current?.contains(event.target as Node)) setAccountOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setAccountOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [accountOpen]);

  useEffect(() => {
    setInert(mainRef.current, isNarrow && drawerOpen);
    setInert(sidebarRef.current, isNarrow && !drawerOpen);
  }, [isNarrow, drawerOpen]);

  useEffect(() => {
    if (drawerOpen) {
      closeButtonRef.current?.focus();
      drawerWasOpen.current = true;
      return;
    }
    if (drawerWasOpen.current && isNarrow) {
      menuButtonRef.current?.focus();
    }
    drawerWasOpen.current = false;
  }, [drawerOpen, isNarrow]);

  useEffect(() => {
    if (!drawerOpen) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setDrawerOpen(false);
        return;
      }
      if (event.key !== "Tab") {
        return;
      }
      const sidebar = sidebarRef.current;
      if (!sidebar) {
        return;
      }
      const focusable = listFocusable(sidebar);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey) {
        if (active === first || !sidebar.contains(active)) {
          event.preventDefault();
          last.focus();
        }
        return;
      }
      if (active === last || !sidebar.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [drawerOpen]);

  return (
    <div className={rootClass}>
      {isNarrow && drawerOpen ? (
        <div
          className="apex-preview__backdrop"
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => setDrawerOpen(false)}
        />
      ) : null}
      <aside
        ref={sidebarRef}
        className="apex-preview__sidebar"
        aria-label="メインメニュー"
        id={sidebarId}
        role={isNarrow && drawerOpen ? "dialog" : undefined}
        aria-modal={isNarrow && drawerOpen ? true : undefined}
        aria-labelledby={sidebarTitleId}
      >
        <h2 id={sidebarTitleId} className="apex-preview__sr">メニュー</h2>
        <div className="apex-preview__brand">
          <BrandMark size={36} />
          <div className="apex-preview__brand-copy">
            <p className="apex-preview__brand-name">VANZAI</p>
            <p className="apex-preview__brand-meta">Ver.{currentVersion}</p>
          </div>
        </div>
        <div className="apex-preview__sidebar-tools">
          {isNarrow ? (
            <button ref={closeButtonRef} type="button" className="apex-preview__icon-button" onClick={() => setDrawerOpen(false)}>
              <ChevronLeft size={18} aria-hidden="true" />
              <span className="apex-preview__sr">メニューを閉じる</span>
            </button>
          ) : (
            <button
              type="button"
              className="apex-preview__icon-button apex-preview__collapse"
              aria-expanded={!collapsed}
              onClick={() => setCollapsed((current) => !current)}
            >
              {collapsed ? <ChevronRight size={18} aria-hidden="true" /> : <ChevronLeft size={18} aria-hidden="true" />}
              <span className="apex-preview__sr">{collapsed ? "サイドバーを広げる" : "サイドバーを折りたたむ"}</span>
              <span className="apex-preview__tooltip" aria-hidden="true">{collapsed ? "サイドバーを広げる" : "サイドバーを折りたたむ"}</span>
            </button>
          )}
        </div>
        <nav className="apex-preview__nav">
          {sections.map((section) => (
            <div key={section.group} className="apex-preview__group">
              <p className="apex-preview__group-label">{section.group}</p>
              {section.items.map((item) => {
                const Icon = NAV_ICONS[item.to] ?? LayoutDashboard;
                const isActive = item.to === activeTo;
                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={isActive ? "apex-preview__nav-link is-active" : "apex-preview__nav-link"}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <Icon aria-hidden="true" />
                    <span className="apex-preview__nav-label">{item.label}</span>
                    <span className="apex-preview__tooltip" aria-hidden="true">{item.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <Link to="/dashboard/preview/profile" className="apex-preview__user" aria-current={showProfile ? "page" : undefined}>
          <span className="apex-preview__avatar" style={{ background: sealColor }} aria-hidden="true">{initial}</span>
          <div className="apex-preview__user-copy">
            <p className="apex-preview__user-name">{displayedName}</p>
            <p className="apex-preview__user-role">{formatRole(user?.role)}</p>
          </div>
          <span className="apex-preview__tooltip" aria-hidden="true">{displayedName}</span>
        </Link>
      </aside>
      <div ref={mainRef} className="apex-preview__main">
        <header className="apex-preview__header">
          <button
            ref={menuButtonRef}
            type="button"
            className="apex-preview__menu"
            aria-expanded={drawerOpen}
            aria-controls={sidebarId}
            onClick={() => setDrawerOpen(true)}
          >
            <Menu size={18} aria-hidden="true" />
            <span className="apex-preview__sr">メニュー</span>
          </button>
          {showProfile ? null : (
            <label className="apex-preview__month">
              対象月
              <input type="month" value={monthValue} onChange={(event) => setMonthValue(event.target.value)} />
            </label>
          )}
          <div className="apex-preview__header-actions">
            <Link className="apex-preview__header-link" to="/dashboard">現行のダッシュボード</Link>
            <button
              type="button"
              className="apex-preview__theme"
              aria-pressed={darkMode}
              onClick={() => {
                setDarkMode((current) => {
                  const next = !current;
                  window.localStorage.setItem(THEME_KEY, next ? "dark" : "light");
                  return next;
                });
              }}
            >
              {darkMode ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
              {darkMode ? "ライト" : "ダーク"}
            </button>
            <div className="apex-preview__account" ref={accountRef}>
              <button
                type="button"
                className="apex-preview__account-button"
                aria-haspopup="menu"
                aria-expanded={accountOpen}
                aria-label={`${displayedName || "ユーザー"}のメニュー`}
                onClick={() => setAccountOpen((current) => !current)}
              >
                <span className="apex-preview__avatar" style={{ background: sealColor }} aria-hidden="true">{initial}</span>
              </button>
              {accountOpen ? (
                <div className="apex-preview__account-menu" role="menu">
                  <Link role="menuitem" to="/dashboard/preview/profile" onClick={() => setAccountOpen(false)}>
                    <Settings size={16} aria-hidden="true" />
                    設定
                  </Link>
                  <button type="button" role="menuitem" onClick={logout}>
                    <LogOut size={16} aria-hidden="true" />
                    ログアウト
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>
        <div className="apex-preview__content">
          {showProfile ? (
            <PreviewProfile
              user={user}
              displayedName={displayedName}
              sealColor={sealColor}
              onSealColor={(color) => {
                setSealColor(color);
                window.localStorage.setItem(SEAL_KEY, color);
              }}
            />
          ) : (
            <>
              <div className="apex-preview__heading-block">
                <div className="apex-preview__title-row">
                  <h1 className="apex-preview__title">見た目プレビュー</h1>
                  <button
                    type="button"
                    className={showBilling ? "apex-preview__billing is-active" : "apex-preview__billing"}
                    aria-pressed={showBilling}
                    onClick={() => setShowBilling((current) => !current)}
                  >
                    請求
                  </button>
                </div>
                <p className="apex-preview__lead">
                  {showBilling ? "上段は選択月で優先して処理する残件" : "通常は概況のグラフです。請求を開くと、今の件数と締めを表示します。"}
                </p>
                <p className="apex-preview__note">締めと月次生成は現行のダッシュボードで行います。</p>
              </div>
              {showBilling ? (
                <PreviewBody
                  periodKey={periodKey}
                  isLoading={!dashboardQuery.isSuccess && !dashboardQuery.isError}
                  isError={dashboardQuery.isError}
                  errorMessage={dashboardQuery.error instanceof ApiError ? dashboardQuery.error.message : "ダッシュボードを取得できませんでした。"}
                  items={dashboardQuery.isSuccess ? dashboardQuery.data.unprocessed_items : null}
                  closingRows={dashboardQuery.isSuccess ? dashboardQuery.data.closing_status : null}
                  varianceAlerts={dashboardQuery.isSuccess ? dashboardQuery.data.variance_alerts : null}
                />
              ) : (
                <PreviewDemoBoard />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function PreviewBody({
  periodKey,
  isLoading,
  isError,
  errorMessage,
  items,
  closingRows,
  varianceAlerts,
}: {
  periodKey: string;
  isLoading: boolean;
  isError: boolean;
  errorMessage: string;
  items: DashboardUnprocessedItem[] | null;
  closingRows: DashboardClosingStatus[] | null;
  varianceAlerts: DashboardVarianceAlert[] | null;
}) {
  if (isError) {
    return <p className="apex-preview__status is-error" role="alert">{errorMessage}</p>;
  }
  if (isLoading || !items || !closingRows || !varianceAlerts) {
    return <p className="apex-preview__status" role="status">読み込み中</p>;
  }

  const pendingDetails = (items.find((item) => item.item_type === "pending_assignment_response")?.details ?? []) as PendingAssignmentResponseDetail[];
  const escalatedCount = unprocessedCount(items, "escalated_assignment_response");
  const pendingCount = unprocessedCount(items, "pending_assignment_response");
  const bar = closingBarState(closingRows);

  return (
    <>
      <section className="apex-preview__kpis" aria-label="未処理件数" data-period={periodKey}>
        {KPI_ITEMS.map((item) => (
          <article key={item.itemType} className="apex-preview__card">
            <p className="apex-preview__kpi-label">{item.label}</p>
            <p className="apex-preview__kpi-value">{unprocessedCount(items, item.itemType).toLocaleString("ja-JP")}</p>
          </article>
        ))}
      </section>
      <section className="apex-preview__split">
        <article className="apex-preview__card">
          <h2 className="apex-preview__section-title">締め状況</h2>
          {closingRows.length === 0 ? (
            <p className="apex-preview__empty">この月の行はありません</p>
          ) : (
            <div className="apex-preview__table-scroll">
              <table className="apex-preview__table">
                <thead>
                  <tr>
                    <th>案件</th>
                    <th>対象月</th>
                    <th>状態</th>
                  </tr>
                </thead>
                <tbody>
                  {closingRows.map((row) => {
                    const tone = previewStatusTone(row.status);
                    return (
                      <tr key={`${row.project_id}-${row.period_key}`}>
                        <td>{row.project_name}</td>
                        <td>{formatPeriodKey(row.period_key)}</td>
                        <td>
                          <span className={`apex-preview__pill is-${tone}`}>{previewStatusLabel(row.status, formatStatus)}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </article>
        <article className="apex-preview__card">
          <h2 className="apex-preview__section-title">仮締め・本締め済み</h2>
          <ClosingBar bar={bar} />
          <div className="apex-preview__counts">
            <p className={escalatedCount > 0 ? "apex-preview__count is-attention" : "apex-preview__count"}>要対応 {escalatedCount.toLocaleString("ja-JP")} 件</p>
            <p className={pendingCount > 0 ? "apex-preview__count is-attention" : "apex-preview__count"}>
              {pendingCount === 0 ? "未回答なし" : `予定確認未回答 ${pendingCount.toLocaleString("ja-JP")} 件`}
            </p>
          </div>
        </article>
      </section>
      <section className="apex-preview__stack">
        <article className="apex-preview__card">
          <h2 className="apex-preview__section-title">差異アラート</h2>
          {varianceAlerts.length === 0 ? (
            <p className="apex-preview__empty">この月の行はありません</p>
          ) : (
            <div className="apex-preview__table-scroll">
              <table className="apex-preview__table">
                <thead>
                  <tr>
                    <th>案件</th>
                    <th>稼働者</th>
                    <th>日付</th>
                    <th>予定</th>
                    <th>実績</th>
                    <th>差分</th>
                  </tr>
                </thead>
                <tbody>
                  {varianceAlerts.map((row) => (
                    <tr key={`${row.project_name}-${row.worker_name}-${row.work_date}-${row.variance_minutes}`}>
                      <td>{row.project_name}</td>
                      <td>{row.worker_name}</td>
                      <td>{formatDate(row.work_date)}</td>
                      <td>{minutesToHours(row.planned_minutes)}</td>
                      <td>{minutesToHours(row.actual_minutes)}</td>
                      <td>{minutesToHours(row.variance_minutes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
        <article className="apex-preview__card">
          <h2 className="apex-preview__section-title">予定確認未回答</h2>
          {pendingDetails.length === 0 ? (
            <p className="apex-preview__empty">この月の行はありません</p>
          ) : (
            <div className="apex-preview__table-scroll">
              <table className="apex-preview__table">
                <thead>
                  <tr>
                    <th>案件</th>
                    <th>稼働者</th>
                    <th>稼働日</th>
                    <th>シフト</th>
                    <th>対応水準</th>
                    <th>条件</th>
                  </tr>
                </thead>
                <tbody>
                  {pendingDetails.map((row) => (
                    <tr key={row.assignment_id}>
                      <td>{row.project_name}</td>
                      <td>{row.worker_name}</td>
                      <td>{formatDate(row.work_date)}</td>
                      <td>{row.shift_label || "-"}</td>
                      <td>
                        <span className={`apex-preview__pill ${row.escalation_level === "escalate" ? "is-warning" : "is-neutral"}`}>
                          {row.escalation_level === "escalate" ? "要対応" : "監視中"}
                        </span>
                      </td>
                      <td>{row.escalation_reasons.length > 0 ? row.escalation_reasons.join(" / ") : "継続確認中"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </section>
    </>
  );
}

function ClosingBar({ bar }: { bar: ReturnType<typeof closingBarState> }) {
  if (bar.kind === "empty") {
    return <p className="apex-preview__bar-label">対象なし</p>;
  }
  if (bar.kind === "mismatch") {
    return <p className="apex-preview__bar-label">案件と行が一致しません</p>;
  }
  return (
    <div>
      <p className="apex-preview__bar-label">仮締め・本締め済み</p>
      <div className="apex-preview__bar" aria-hidden="true">
        <div className="apex-preview__bar-fill" style={{ width: `${bar.percent}%` }} />
      </div>
      <p className="apex-preview__bar-meta">
        <span>{bar.closed.toLocaleString("ja-JP")} / {bar.total.toLocaleString("ja-JP")} 件</span>
        <span>{bar.percent}%</span>
      </p>
    </div>
  );
}
