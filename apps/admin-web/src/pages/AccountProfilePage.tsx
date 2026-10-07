import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { ApiError, changePassword, updateProfile } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import { formatRole } from "../lib/formatters";

export function AccountProfilePage() {
  const { user, logout, refreshUser } = useAuth();
  const displayedName = user?.display_name || user?.username || "";
  const initial = displayedName.slice(0, 1) || "V";
  const isAdmin = user?.role === "admin";

  const [displayName, setDisplayName] = useState(displayedName);

  useEffect(() => {
    setDisplayName(displayedName);
  }, [displayedName]);
  const [nameSaving, setNameSaving] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [nameSaved, setNameSaved] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);

  async function handleName(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNameError(null);
    setNameSaved(false);
    const next = displayName.trim();
    if (!next) {
      setNameError("表示名を入力してください");
      return;
    }
    setNameSaving(true);
    try {
      await updateProfile({ display_name: next });
      await refreshUser();
      setNameSaved(true);
    } catch (err) {
      setNameError(err instanceof ApiError ? err.message : "更新に失敗しました");
    } finally {
      setNameSaving(false);
    }
  }

  async function handlePassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPasswordError(null);
    setPasswordSaved(false);
    if (newPassword !== confirmPassword) {
      setPasswordError("新しいパスワードと確認用パスワードが一致しません");
      return;
    }
    setPasswordSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setPasswordSaved(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setPasswordError(err instanceof ApiError ? err.message : "パスワード変更に失敗しました");
    } finally {
      setPasswordSubmitting(false);
    }
  }

  return (
    <section className="account-profile">
      <PageHeader
        eyebrow="アカウント"
        title="プロフィール"
        description="ログイン中のアカウントです。"
      />
      <article className="card account-profile-hero">
        <span className="account-profile-avatar" aria-hidden="true">{initial}</span>
        <div>
          <h2>{displayedName || "名前未設定"}</h2>
          <p>{formatRole(user?.role)}</p>
          <dl>
            <div>
              <dt>メール</dt>
              <dd>{user?.email || "未設定"}</dd>
            </div>
            <div>
              <dt>ユーザー名</dt>
              <dd>{user?.username || "未設定"}</dd>
            </div>
          </dl>
        </div>
      </article>

      <article className="card">
        <h2>表示名</h2>
        <p className="account-profile-note">ログインID（{user?.username || "未設定"}）は変わりません。</p>
        {nameSaved ? <p className="account-profile-status">表示名を保存しました。</p> : null}
        {nameError ? <p className="form-error" role="alert">{nameError}</p> : null}
        <form className="login-form" onSubmit={handleName}>
          <label>
            表示名
            <input
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              required
              autoComplete="nickname"
            />
          </label>
          <button type="submit" className="primary-button" disabled={nameSaving}>
            {nameSaving ? "保存中..." : "保存"}
          </button>
        </form>
      </article>

      <article className="card">
        <h2>パスワード変更</h2>
        {passwordSaved ? <p className="account-profile-status">パスワードを変更しました。</p> : null}
        {passwordError ? <p className="form-error" role="alert">{passwordError}</p> : null}
        <form className="login-form" onSubmit={handlePassword}>
          <label>
            現在のパスワード
            <div className="password-input-wrapper">
              <input
                type={showCurrent ? "text" : "password"}
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                required
                autoComplete="current-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowCurrent((value) => !value)}
                aria-label={showCurrent ? "隠す" : "表示する"}
              >
                {showCurrent ? "隠す" : "表示"}
              </button>
            </div>
          </label>
          <label>
            新しいパスワード（8文字以上）
            <div className="password-input-wrapper">
              <input
                type={showNew ? "text" : "password"}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowNew((value) => !value)}
                aria-label={showNew ? "隠す" : "表示する"}
              >
                {showNew ? "隠す" : "表示"}
              </button>
            </div>
          </label>
          <label>
            新しいパスワード（確認）
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              autoComplete="new-password"
            />
          </label>
          <button type="submit" className="primary-button" disabled={passwordSubmitting}>
            {passwordSubmitting ? "変更中..." : "パスワードを変更"}
          </button>
        </form>
      </article>

      {isAdmin ? (
        <article className="card">
          <h2>管理者</h2>
          <p className="account-profile-note">一覧から外した発注依頼書は、ここからだけ確認できます。</p>
          <Link className="primary-button" to="/operations/order-requests/deleted">
            削除済み案件一覧
          </Link>
        </article>
      ) : null}

      <article className="card">
        <button type="button" className="ghost-button" onClick={logout}>
          ログアウト
        </button>
      </article>
    </section>
  );
}
