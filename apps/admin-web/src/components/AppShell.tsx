import { Link, Outlet } from "react-router-dom";

import { SideNav } from "./SideNav";
import { useAuth } from "../lib/auth/auth-context";
import { formatRole } from "../lib/formatters";

export function AppShell() {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <SideNav />
      <main className="app-main">
        <header className="topbar">
          <div>
            <p className="eyebrow">VANZAI 管理画面</p>
            <h1 className="topbar-title">案件・シフト・実績 一元管理</h1>
          </div>
          <div className="topbar-actions">
            <div className="identity-card">
              <span className="identity-name">{user?.username}</span>
              <span className="identity-role">{formatRole(user?.role)}</span>
            </div>
            <Link to="/account/change-password" className="ghost-button" style={{ textDecoration: "none" }}>
              パスワード変更
            </Link>
            <button type="button" className="ghost-button" onClick={logout}>
              ログアウト
            </button>
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}