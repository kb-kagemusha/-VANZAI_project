import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { changePassword } from "../lib/api/client";
import { ApiError } from "../lib/api/client";
import { PageHeader } from "../components/PageHeader";

export function ChangePasswordPage() {
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError("新しいパスワードと確認用パスワードが一致しません");
      return;
    }

    setSubmitting(true);
    try {
      await changePassword(currentPassword, newPassword);
      setSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("パスワード変更に失敗しました");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-container">
      <PageHeader title="パスワード変更" description="ログイン中のアカウントのパスワードを変更します" />
      <div className="card" style={{ maxWidth: "480px" }}>
        {success ? (
          <div style={{ display: "grid", gap: "1rem" }}>
            <p style={{ color: "var(--success, #16a34a)", fontWeight: 600 }}>
              ✓ パスワードを変更しました
            </p>
            <button
              type="button"
              className="primary-button"
              onClick={() => navigate("/dashboard")}
            >
              ダッシュボードへ戻る
            </button>
          </div>
        ) : (
          <form className="login-form" onSubmit={handleSubmit}>
            <label>
              現在のパスワード
              <div className="password-input-wrapper">
                <input
                  type={showCurrent ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowCurrent((v) => !v)}
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
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowNew((v) => !v)}
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
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </label>
            {error ? <p className="form-error">{error}</p> : null}
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                type="button"
                className="ghost-button"
                onClick={() => navigate(-1)}
                disabled={submitting}
              >
                キャンセル
              </button>
              <button type="submit" className="primary-button" disabled={submitting}>
                {submitting ? "変更中..." : "パスワードを変更"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
