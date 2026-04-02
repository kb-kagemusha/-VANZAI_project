import { startTransition, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth/auth-context";
import { ApiError } from "../lib/api/client";

export function LoginPage() {
  const { login, status } = useAuth();
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
        navigate("/today", { replace: true });
      });
    }
  }, [navigate, status]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      await login(username, password);
      const from = (location.state as { from?: string } | null)?.from || "/today";
      startTransition(() => {
        navigate(from, { replace: true });
      });
    } catch (submitError) {
      if (submitError instanceof ApiError) {
        setError(submitError.message);
      } else {
        setError("ログイン処理に失敗しました");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <section className="login-card mobile-login-card">
        <p className="eyebrow">PHASE 5 PREP</p>
        <h1>VANZAI Staff Mobile</h1>
        <p className="login-copy">
          まずは当日のアサイン確認と月次実績確認から、worker ロール向けの導線を切り出します。
        </p>
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
                aria-label={showPassword ? "パスワードを隠す" : "パスワードの表示を切り替える"}
              >
                {showPassword ? "非表示" : "表示"}
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