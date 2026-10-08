import { startTransition, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../lib/auth/auth-context";
import { ApiError } from "../lib/api/client";
import { useAppVersion } from "../lib/hooks/useAppVersion";

const LABELS = {
  eyebrow: "\u30d5\u30a7\u30fc\u30ba1 \u7ba1\u7406\u30b3\u30f3\u30bd\u30fc\u30eb",
  title: "VANZAI \u7ba1\u7406\u753b\u9762",
  copy: "\u6708\u6b21\u904b\u7528\u306e\u53c2\u7167\u7cfb\u3092 React \u7ba1\u7406\u753b\u9762\u3078\u79fb\u3059\u305f\u3081\u306e\u30d5\u30a7\u30fc\u30ba1\u30d9\u30fc\u30b9\u3067\u3059\u3002",
  refresh: "\u6700\u65b0\u7248\u3092\u53cd\u6620",
  username: "\u30e6\u30fc\u30b6\u30fc\u540d",
  password: "\u30d1\u30b9\u30ef\u30fc\u30c9",
  hide: "\u96a0\u3059",
  show: "\u8868\u793a",
  showAria: "\u8868\u793a\u3059\u308b",
  submitting: "\u8a8d\u8a3c\u4e2d...",
  login: "\u30ed\u30b0\u30a4\u30f3",
  networkError:
    "\u8a8d\u8a3c\u30b5\u30fc\u30d0\u30fc\u306b\u63a5\u7d9a\u3067\u304d\u307e\u305b\u3093\u3002\u30cd\u30c3\u30c8\u30ef\u30fc\u30af\u307e\u305f\u306fAPI\u306e\u72b6\u614b\u3092\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002",
  loginFailed: "\u30ed\u30b0\u30a4\u30f3\u51e6\u7406\u306b\u5931\u6557\u3057\u307e\u3057\u305f",
} as const;

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
        setError(LABELS.networkError);
      } else {
        setError(LABELS.loginFailed);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="login-screen">
      <section className="login-card">
        <p className="eyebrow">{LABELS.eyebrow}</p>
        <h1>{LABELS.title}</h1>
        <p className="login-copy">{LABELS.copy}</p>
        <div className="login-version-row">
          <span className="login-version-label">Ver.{currentVersion}</span>
          {hasUpdate ? (
            <button type="button" className="login-version-refresh" onClick={refreshNow}>
              {LABELS.refresh}
            </button>
          ) : null}
        </div>
        <p className="login-build-label">Build {currentBuildId}</p>
        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            {LABELS.username}
            <input value={username} onChange={(event) => setUsername(event.target.value)} required />
          </label>
          <label>
            {LABELS.password}
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
                aria-label={showPassword ? LABELS.hide : LABELS.showAria}
              >
                {showPassword ? LABELS.hide : LABELS.show}
              </button>
            </div>
          </label>
          {error ? <p className="form-error">{error}</p> : null}
          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? LABELS.submitting : LABELS.login}
          </button>
        </form>
      </section>
    </div>
  );
}
