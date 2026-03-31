import { NavLink } from "react-router-dom";

import { NAV_ITEMS, canAccess } from "../lib/auth/permissions";
import { useAuth } from "../lib/auth/auth-context";

export function SideNav() {
  const { user } = useAuth();

  return (
    <aside className="side-nav">
      <div className="side-nav-brand">
        <span className="brand-mark">V</span>
        <div>
          <p className="eyebrow">フェーズ1</p>
          <h2>管理画面</h2>
        </div>
      </div>
      <nav className="side-nav-links">
        {NAV_ITEMS.filter((item) => canAccess(user?.role, item.allowedRoles)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
          >
            <span className="nav-link-label">{item.label}</span>
            <span className="nav-link-description">{item.description}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}