import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";
import { getDashboard } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import { NAV_ITEMS, canView, hasPermission } from "../lib/auth/permissions";
import { currentMonthInput, toPeriodKey } from "../lib/formatters";
import { DashboardPage } from "./DashboardPage";

export function RoleDashboardPage() {
  const { user } = useAuth();
  const fullDashboard = ["invoice_read", "payout_read", "price_read", "soft_close"].every(p => hasPermission(user, p));
  const query = useQuery({ queryKey: ["role-dashboard", user?.role, user?.permissions], queryFn: () => getDashboard(toPeriodKey(currentMonthInput())), enabled: !fullDashboard && hasPermission(user, "project_read") });
  if (fullDashboard) return <DashboardPage />;
  return <div className="page-stack"><PageHeader title="ダッシュボード" description="閲覧できる業務と、今月の確認事項を表示します。" />
    <section className="card access-form"><h2>業務メニュー</h2><div className="access-grid">{NAV_ITEMS.filter(item => !item.to.startsWith("/dashboard") && canView(user, item.to, item.allowedRoles)).map(item => <Link key={item.to} to={item.to}>{item.label}</Link>)}</div></section>
    {query.isError && <p role="alert">確認事項を取得できませんでした。</p>}
    {query.data && <section className="card access-form"><h2>今月の確認事項</h2>{query.data.unprocessed_items.filter(item => ["assignment_variance", "pending_assignment_response", "escalated_assignment_response"].includes(item.item_type)).map(item => <p key={item.item_type}>{({assignment_variance: "予定と実績の差異", pending_assignment_response: "予定確認の未回答", escalated_assignment_response: "予定確認の要対応"} as Record<string, string>)[item.item_type]}：{item.count}件</p>)}</section>}
  </div>;
}
