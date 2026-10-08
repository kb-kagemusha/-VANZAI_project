import { Link } from "react-router-dom";

export function ForbiddenPage() {
  return (
    <div className="fullscreen-state forbidden-state">
      <div className="panel-card">
        <p className="panel-label">ACCESS DENIED</p>
        <h1>worker ロール専用です</h1>
        <p>この画面は staff-mobile の対象ロールに限定しています。</p>
        <Link to="/today" className="text-link">戻る</Link>
      </div>
    </div>
  );
}