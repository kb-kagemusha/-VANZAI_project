/**
 * カレンダー（0.48.8）。出勤可能日・イベントごと・稼働者ごと・参加カレンダー（月）を1つのメニューにまとめ、
 * 上のボタンで表示を切り替える。見られる表示は権限で決まる（出勤可能日＝availability_read、ほか＝order_read）。
 */
import { useSearchParams } from "react-router-dom";

import { PageHeader } from "../components/PageHeader";
import { useAuth } from "../lib/auth/auth-context";
import { hasPermission } from "../lib/auth/permissions";
import { AvailabilityCalendarPage } from "./AvailabilityCalendarPage";
import { OrderOverviewBody } from "./OrderOverviewPage";
import { ParticipationCalendarPage } from "./ParticipationCalendarPage";
import "../styles/orderOverview.css";

type View = "availability" | "event" | "worker" | "participation";

const VIEWS: { key: View; label: string; permission: string; description: string }[] = [
  { key: "availability", label: "出勤可能日", permission: "availability_read", description: "スタッフが出勤できる日（◯・△・✗）と担当を、月または週で表示します。" },
  { key: "event", label: "イベントごと", permission: "order_read", description: "依頼済みのイベントを行に、月の1日から末日までを横に並べ、日ごとの稼働者の名前を表示します。" },
  { key: "worker", label: "稼働者ごと", permission: "order_read", description: "登録のある稼働者全員を行に（依頼がない人も含む）、月の1日から末日までを横に並べ、日ごとに参加するイベントを表示します。LINEの連携がまだの人には「LINE未連携」と表示します。" },
  { key: "participation", label: "参加カレンダー", permission: "order_read", description: "月のカレンダー（月曜始まり）で、日ごとにイベントと参加OK・変更確認待ち・未回答の人数を表示します。日付を押すと名前を表示します。" },
];

export function CalendarHubPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const allowed = VIEWS.filter((v) => hasPermission(user, v.permission));
  const requested = searchParams.get("view") as View | null;
  const current = allowed.find((v) => v.key === requested) ?? allowed[0];

  function choose(view: View) {
    // 月の指定は表示をまたいで残す（出勤可能日は自分で期間を持つ）
    const next = new URLSearchParams();
    next.set("view", view);
    const month = searchParams.get("month");
    if (month && view !== "availability") next.set("month", month);
    if (searchParams.get("test") && (view === "event" || view === "worker")) next.set("test", searchParams.get("test") as string);
    setSearchParams(next);
  }

  return (
    <div className="page-stack">
      <PageHeader title="カレンダー" eyebrow="運用" description={current?.key === "event" || current?.key === "worker" ? "" : current?.description ?? "表示できるカレンダーがありません。"} />
      {allowed.length > 1 ? (
        <div className="calendar-hub-tabs" role="tablist" aria-label="カレンダーの表示">
          {allowed.map((view) => (
            <button
              key={view.key}
              type="button"
              role="tab"
              aria-selected={current?.key === view.key}
              className={current?.key === view.key ? "is-active" : ""}
              onClick={() => choose(view.key)}
            >
              {view.label}
            </button>
          ))}
        </div>
      ) : null}
      {current?.key === "availability" ? <AvailabilityCalendarPage embedded /> : null}
      {current?.key === "event" || current?.key === "worker" ? <OrderOverviewBody /> : null}
      {current?.key === "participation" ? <ParticipationCalendarPage embedded /> : null}
    </div>
  );
}
