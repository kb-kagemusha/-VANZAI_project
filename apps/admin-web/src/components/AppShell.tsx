import { Link, Outlet } from "react-router-dom";
import { useState } from "react";

import { SideNav } from "./SideNav";
import { useAuth } from "../lib/auth/auth-context";
import { formatRole } from "../lib/formatters";
import { updateProfile, ApiError } from "../lib/api/client";
import { useAppVersion } from "../lib/hooks/useAppVersion";

export function AppShell() {
  const { user, logout, refreshUser } = useAuth();
  const [showEdit, setShowEdit] = useState(false);
  const [editName, setEditName] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { currentVersion, hasUpdate, refreshNow } = useAppVersion();

  const displayedName = user?.display_name || user?.username;

  function openEdit() {
    setEditName(user?.display_name || user?.username || "");
    setEditError(null);
    setShowEdit(true);
  }

  async function handleSave() {
    if (!editName.trim()) {
      setEditError("表示名を入力してください");
      return;
    }
    setSaving(true);
    setEditError(null);
    try {
      await updateProfile({ display_name: editName.trim() });
      await refreshUser();
      setShowEdit(false);
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "更新に失敗しました");
    } finally {
      setSaving(false);
    }
  }

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
            <div className="topbar-version">
              <span className="topbar-version-label">Ver.{currentVersion}</span>
              {hasUpdate && (
                <button type="button" className="topbar-version-update" onClick={refreshNow}>
                  🔄 更新
                </button>
              )}
            </div>
            <div className="identity-card">
              <span className="identity-name">{displayedName}</span>
              <span className="identity-role">{formatRole(user?.role)}</span>
            </div>
            <button type="button" className="ghost-button" onClick={openEdit}>
              更新
            </button>
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

      {/* プロフィール編集モーダル */}
      {showEdit && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.35)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowEdit(false); }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 12,
              padding: "24px 28px",
              minWidth: 320,
              boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
            }}
          >
            <h3 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700 }}>プロフィール更新</h3>
            {editError && (
              <p style={{ color: "#ef4444", fontSize: 13, marginBottom: 10 }}>{editError}</p>
            )}
            <div style={{ display: "grid", gap: 14 }}>
              <label style={{ fontSize: 13, color: "#374151", display: "grid", gap: 4 }}>
                表示名
                <input
                  className="form-input"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="例: Sample User"
                  autoFocus
                  onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
                />
              </label>
              <p style={{ fontSize: 11, color: "#9ca3af", margin: 0 }}>
                ログインID（{user?.username}）は変わりません。
              </p>
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => setShowEdit(false)}
                >
                  キャンセル
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={saving}
                  onClick={handleSave}
                >
                  {saving ? "保存中..." : "保存"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}