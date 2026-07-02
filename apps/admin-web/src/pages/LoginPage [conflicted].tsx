import { startTransition, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth/auth-context";
import { ApiError } from "../lib/api/client";
import { useAppVersion } from "../lib/hooks/useAppVersion";

export function LoginPage() {
  const { login, status } = useAuth();
  const { currentVersion, currentBuildId, hasUpdate, refreshNow } = useAppVersion();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (status === "authenticated") {
      startTransition(() => {
        navigate("/dashboard", { replace: true });
      });
    }
  }, [navigate, status]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login(username, password);
      const from = (location.state as { from?: string } | null)?.from || "/dashboard";
      startTransition(() => {
        navigate(from, { replace: true });
      });
    } catch (submitError) {
      if (submitError instanceof ApiError) {
        setError(submitError.message);
      } else if (submitError instanceof TypeError) {
        setError("認証サーバーに接続できません。ネットワークまたはAPIの状態を確認してください。");
      } else {
        setError("ログイン処理に失敗しました");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <section className="login-card">
        <p className="eyebrow">フェーズ1 管理コンソール</p>
        <h1>VANZAI 管理画面</h1>
        <p className="login-copy">
          月次運用の参照系を React 管理画面へ移すためのフェーズ1ベースです。
        </p>
        <div className="login-version-row">
          <span className="login-version-label">Ver.{currentVersion}</span>
          {hasUpdate ? (
            <button type="button" className="login-version-refresh" onClick={refreshNow}>
              最新版を反映
            </button>
          ) : null}
        </div>
        <p className="login-build-label">Build {currentBuildId}</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            ユーザー名
            <input value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            パスワード
            <div className="password-input-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "隠す" : "表示する"}
              >
                {showPassword ? "隠す" : "表示"}
              </button>
            </div>
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "認証中..." : "ログイン"}
          </button>
        </form>
      </section>
    </div>
  );
}