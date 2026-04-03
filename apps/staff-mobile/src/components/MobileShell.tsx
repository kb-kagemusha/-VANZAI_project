import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";

import { MobileStatusBand } from "./MobileStatusBand";
import { getActuals, getAssignments, getWorkerAvailability, getWorkerAvailabilityPreferences, getWorkerNotices } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import { currentDateInput } from "../lib/formatters";
import { getAvailabilityTemplateDetail, normalizeStaffAvailabilityPreferences } from "../lib/settings/staffPreferences";
import { usePushNotification } from "../lib/hooks/usePushNotification";

const navItems = [
  { to: "/today", label: "今日" },
  { to: "/schedule", label: "予定" },
  { to: "/availability", label: "事前予定" },
  { to: "/actuals", label: "実績" },
  { to: "/expenses", label: "経費" },
  { to: "/notices", label: "通知" },
];

export function MobileShell() {
  const { user, logout } = useAuth();
  const today = currentDateInput();
  const pendingAssignmentsQuery = useQuery({
    queryKey: ["staff-schedule-pending"],
    queryFn: () =>
      getAssignments({
        work_date_from: today,
        response_status: "pending",
        sort_by: "work_date",
        sort_order: "asc",
        limit: 100,
      }),
    staleTime: 60_000,
  });
  const todayAssignmentsQuery = useQuery({
    queryKey: ["staff-today-assignments", today],
    queryFn: () =>
      getAssignments({
        work_date_from: today,
        work_date_to: today,
        sort_by: "work_date",
        sort_order: "asc",
        limit: 20,
      }),
    staleTime: 60_000,
  });
  const todayActualsQuery = useQuery({
    queryKey: ["staff-today-actuals", today],
    queryFn: () =>
      getActuals({
        work_date_from: today,
        work_date_to: today,
        sort_by: "work_date",
        sort_order: "asc",
        limit: 20,
      }),
    staleTime: 60_000,
  });
  const todayAvailabilityQuery = useQuery({
    queryKey: ["staff-today-availability", today],
    queryFn: () =>
      getWorkerAvailability({
        availability_date_from: today,
        availability_date_to: today,
        sort_by: "availability_date",
        sort_order: "asc",
        limit: 5,
      }),
    staleTime: 60_000,
  });
  const preferencesQuery = useQuery({
    queryKey: ["staff-availability-preferences"],
    queryFn: () => getWorkerAvailabilityPreferences(),
    staleTime: 60_000,
  });
  const noticesUnreadQuery = useQuery({
    queryKey: ["worker-notices-unread"],
    queryFn: () => getWorkerNotices({ unread_only: true, limit: 1 }),
    staleTime: 60_000,
  });

  const pendingCount = pendingAssignmentsQuery.data?.total ?? 0;
  const unreadNoticeCount = noticesUnreadQuery.data?.unread_count ?? 0;
  const todayAssignments = todayAssignmentsQuery.data?.items ?? [];
  const todayActuals = todayActualsQuery.data?.items ?? [];
  const todayAvailability = todayAvailabilityQuery.data?.items?.[0] ?? null;
  const preferences = normalizeStaffAvailabilityPreferences(preferencesQuery.data);
  const templateDetail = getAvailabilityTemplateDetail(today, preferences);
  const statusBandLoading = pendingAssignmentsQuery.isLoading || todayAssignmentsQuery.isLoading || todayActualsQuery.isLoading || todayAvailabilityQuery.isLoading || preferencesQuery.isLoading;
  const statusBandError = pendingAssignmentsQuery.isError || todayAssignmentsQuery.isError || todayActualsQuery.isError || todayAvailabilityQuery.isError || preferencesQuery.isError;

  const queryClient = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const { permission, requestPermission } = usePushNotification();
  const [onboardingDismissed, setOnboardingDismissed] = useState(false);

  const showOnboarding =
    typeof Notification !== "undefined" &&
    "PushManager" in window &&
    permission === "default" &&
    !onboardingDismissed;

  async function handleAllowPush() {
    await requestPermission();
    setOnboardingDismissed(true);
  }

  async function handleRefresh() {
    setRefreshing(true);
    await queryClient.invalidateQueries();
    setRefreshing(false);
  }

  return (
    <div className="mobile-shell">
      <header className="mobile-header">
        <div>
          <p className="mobile-eyebrow">STAFF MOBILE</p>
          <h1>VANZAI Crew</h1>
        </div>
        <div className="mobile-header-meta">
          <span>{user?.username}</span>
          <div className="mobile-header-actions">
            <NavLink to="/settings" className="secondary-button header-action-link">
              個人設定
            </NavLink>
            <button type="button" className="refresh-button" onClick={handleRefresh} disabled={refreshing} aria-label="データを更新">
              {refreshing ? "…" : "↺"}
            </button>
            <button type="button" onClick={logout}>ログアウト</button>
          </div>
        </div>
      </header>

      <MobileStatusBand
        todayAssignments={todayAssignments}
        todayActuals={todayActuals}
        pendingCount={pendingCount}
        todayAvailability={todayAvailability}
        templateStatus={templateDetail.status}
        templateReason={templateDetail.reason}
        isLoading={statusBandLoading}
        hasError={statusBandError}
      />

      <main className="mobile-main">
        <Outlet />
      </main>

      <nav className="mobile-nav" aria-label="モバイルナビゲーション">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => (isActive ? "mobile-nav-link active" : "mobile-nav-link")}
          >
            <span className="mobile-nav-label">{item.label}</span>
            {item.to === "/schedule" && pendingCount > 0 ? <span className="mobile-nav-badge">{pendingCount}</span> : null}
            {item.to === "/notices" && unreadNoticeCount > 0 ? <span className="mobile-nav-badge">{unreadNoticeCount}</span> : null}
          </NavLink>
        ))}
      </nav>

      {showOnboarding ? (
        <div className="push-onboarding-overlay" role="dialog" aria-modal="true" aria-label="プッシュ通知の設定">
          <div className="push-onboarding-card">
            <div className="push-onboarding-icon">🔔</div>
            <h2 className="push-onboarding-title">通知を受け取りますか？</h2>
            <p className="push-onboarding-body">
              シフト確定・変更・お知らせをリアルタイムで受け取れます。
            </p>
            <div className="push-onboarding-actions">
              <button type="button" className="primary-button" onClick={handleAllowPush}>
                通知を許可する
              </button>
              <button type="button" className="secondary-button" onClick={() => setOnboardingDismissed(true)}>
                後で
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}