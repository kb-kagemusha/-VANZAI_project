import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";

import { getAssignments } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import { currentDateInput } from "../lib/formatters";

const navItems = [
  { to: "/today", label: "今日" },
  { to: "/schedule", label: "予定" },
  { to: "/availability", label: "可否" },
  { to: "/actuals", label: "実績" },
  { to: "/expenses", label: "経費" },
];

export function MobileShell() {
  const { user, logout } = useAuth();
  const pendingAssignmentsQuery = useQuery({
    queryKey: ["staff-schedule-pending"],
    queryFn: () =>
      getAssignments({
        work_date_from: currentDateInput(),
        response_status: "pending",
        sort_by: "work_date",
        sort_order: "asc",
        limit: 100,
      }),
    staleTime: 60_000,
  });
  const pendingCount = pendingAssignmentsQuery.data?.total ?? 0;

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
          <button type="button" onClick={logout}>ログアウト</button>
        </div>
      </header>

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