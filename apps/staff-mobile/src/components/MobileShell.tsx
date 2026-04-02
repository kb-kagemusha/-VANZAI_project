import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";

import { MobileStatusBand } from "./MobileStatusBand";
import { getActuals, getAssignments, getWorkerAvailability, getWorkerAvailabilityPreferences } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import { currentDateInput } from "../lib/formatters";
import { getAvailabilityTemplateDetail, normalizeStaffAvailabilityPreferences } from "../lib/settings/staffPreferences";

const navItems = [
  { to: "/today", label: "今日" },
  { to: "/schedule", label: "予定" },
  { to: "/availability", label: "事前予定" },
  { to: "/actuals", label: "実績" },
  { to: "/expenses", label: "経費" },
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

  const pendingCount = pendingAssignmentsQuery.data?.total ?? 0;
  const todayAssignments = todayAssignmentsQuery.data?.items ?? [];
  const todayActuals = todayActualsQuery.data?.items ?? [];
  const todayAvailability = todayAvailabilityQuery.data?.items?.[0] ?? null;
  const preferences = normalizeStaffAvailabilityPreferences(preferencesQuery.data);
  const templateDetail = getAvailabilityTemplateDetail(today, preferences);
  const statusBandLoading = pendingAssignmentsQuery.isLoading || todayAssignmentsQuery.isLoading || todayActualsQuery.isLoading || todayAvailabilityQuery.isLoading || preferencesQuery.isLoading;
  const statusBandError = pendingAssignmentsQuery.isError || todayAssignmentsQuery.isError || todayActualsQuery.isError || todayAvailabilityQuery.isError || preferencesQuery.isError;

  return (
    <div className="mobile-shell">
      <header className="mobile-header">
        <div>
          <p className="mobile-eyebrow">STAFF MOBILE</p>
          <h1>VANZAI Crew</h1>
          <p className="mobile-copy">本日の動きと今月の実績を、現場でそのまま確認します。</p>
        </div>
        <div className="mobile-header-meta">
          <span>{user?.username}</span>
          <div className="mobile-header-actions">
            <NavLink to="/settings" className="secondary-button header-action-link">
              個人設定
            </NavLink>
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
          </NavLink>
        ))}
      </nav>
    </div>
  );
}