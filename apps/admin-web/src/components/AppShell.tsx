import { Outlet } from "react-router-dom";
import { useState } from "react";
import { SideNav } from "./SideNav";

const NAV_COLLAPSED_KEY = "vanzai.admin.navCollapsed";

export function AppShell() {
  const [navCollapsed, setNavCollapsed] = useState(() => window.localStorage.getItem(NAV_COLLAPSED_KEY) === "1");
  function toggleNavCollapsed() {
    setNavCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(NAV_COLLAPSED_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <div className={`app-shell${navCollapsed ? " app-shell--nav-collapsed" : ""}`}>
      <SideNav collapsed={navCollapsed} onToggleCollapsed={toggleNavCollapsed} />
      <main className="app-main"><Outlet /></main>
    </div>
  );
}
