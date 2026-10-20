import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth/auth-context";

export function ForbiddenPage() {
  const { logout } = useAuth();
  return (
    <div className="page-stack">
      <section className="forbidden-card">
        <p className="eyebrow">403</p>
        <h2>この画面にはアクセスできません</h2>
        <p>権限設定と対象案件の範囲を確認してください。</p>
        <div className="button-row"><Link to="/dashboard">利用できる画面へ戻る</Link><Link to="/account/profile">プロフィール</Link><button type="button" onClick={logout}>ログアウト</button></div>
      </section>
    </div>
  );
}
