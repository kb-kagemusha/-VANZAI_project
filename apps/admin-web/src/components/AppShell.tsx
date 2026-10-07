import { Link, Outlet } from "react-router-dom";
import { useState } from "react";

import { SideNav } from "./SideNav";
import { useAuth } from "../lib/auth/auth-context";
import { canAccess } from "../lib/auth/permissions";

const NAV_COLLAPSED_KEY = "vanzai.admin.navCollapsed";

const REGISTRATION_FORM_DEFINITIONS = [
  { key: "worker", label: "稼働者登録", path: "/public/registrations/worker" },
  { key: "supplier-individual", label: "個人下請け登録", path: "/public/registrations/supplier-individual" },
  { key: "supplier-corporation", label: "法人下請け登録", path: "/public/registrations/supplier-corporation" },
  { key: "introducer-identity", label: "紹介者本人確認", path: "/public/registrations/introducer-identity" },
] as const;

export function AppShell() {
  const { user } = useAuth();
  const [showRegistrationUrls, setShowRegistrationUrls] = useState(false);
  const [urlCopyMessage, setUrlCopyMessage] = useState<string | null>(null);
  const [navCollapsed, setNavCollapsed] = useState(() => window.localStorage.getItem(NAV_COLLAPSED_KEY) === "1");
  const canCheckRegistrationUrls = canAccess(user?.role, ["admin", "ops", "accounting"]);
  const registrationFormUrls = REGISTRATION_FORM_DEFINITIONS.map((item) => ({
    ...item,
    url: `${window.location.origin}${item.path}`,
  }));

  function openRegistrationUrls() {
    setUrlCopyMessage(null);
    setShowRegistrationUrls(true);
  }

  async function copyRegistrationUrl(url: string) {
    try {
      await navigator.clipboard.writeText(url);
      setUrlCopyMessage("URLをコピーしました");
    } catch {
      setUrlCopyMessage("URLのコピーに失敗しました");
    }
  }

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
      <main className="app-main">
        <header className="topbar">
          <div className="topbar-heading">
            <div className="topbar-kicker">
              <p className="eyebrow">VANZAI 管理画面</p>
            </div>
            <h1 className="topbar-title">案件・シフト・実績 一元管理</h1>
          </div>
          <div className="topbar-actions">
            {canCheckRegistrationUrls ? (
              <button type="button" className="ghost-button" onClick={openRegistrationUrls}>
                登録画面のURL確認
              </button>
            ) : null}
          </div>
        </header>
        <Outlet />
      </main>

      {showRegistrationUrls && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.35)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "1.5rem",
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowRegistrationUrls(false); }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 12,
              padding: "24px 28px",
              width: "min(100%, 760px)",
              boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
              display: "grid",
              gap: 16,
            }}
          >
            <div style={{ display: "grid", gap: 4 }}>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>登録画面のURL一覧</h3>
              <p style={{ margin: 0, fontSize: 13, color: "#6b7280" }}>
                実際の運用では token と PIN を含む公開リンクを発行して使用してください。下のURLは画面パス確認用です。
              </p>
            </div>

            <div style={{ display: "grid", gap: 10 }}>
              {registrationFormUrls.map((item) => (
                <div
                  key={item.key}
                  style={{
                    border: "1px solid #e5e7eb",
                    borderRadius: 10,
                    padding: "12px 14px",
                    display: "grid",
                    gap: 8,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                    <strong style={{ fontSize: 14 }}>{item.label}</strong>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      <button type="button" className="ghost-button" onClick={() => void copyRegistrationUrl(item.url)}>
                        URLをコピー
                      </button>
                      <a href={item.url} target="_blank" rel="noreferrer" className="ghost-button" style={{ textDecoration: "none" }}>
                        開く
                      </a>
                    </div>
                  </div>
                  <div style={{ fontSize: 12, color: "#475467", wordBreak: "break-all" }}>{item.url}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <div style={{ fontSize: 12, color: urlCopyMessage === "URLをコピーしました" ? "#16a34a" : "#b42318" }}>
                {urlCopyMessage ?? ""}
              </div>
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", flexWrap: "wrap" }}>
                <Link to="/operations/registration-requests" className="ghost-button" style={{ textDecoration: "none" }} onClick={() => setShowRegistrationUrls(false)}>
                  公開リンク発行へ
                </Link>
                <button type="button" className="ghost-button" onClick={() => setShowRegistrationUrls(false)}>
                  閉じる
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}