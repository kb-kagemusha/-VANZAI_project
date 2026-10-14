import { formatStatus, formatTime } from "../lib/formatters";
import type { ActualListItem, AssignmentListItem, WorkerAvailabilityListItem } from "../types/api";

type MobileStatusBandProps = {
  todayAssignments: AssignmentListItem[];
  todayActuals: ActualListItem[];
  pendingCount: number;
  todayAvailability: WorkerAvailabilityListItem | null;
  templateStatus: string;
  templateReason: string;
  isLoading: boolean;
  hasError: boolean;
};

function normalizeAvailabilityStatus(status: string | null | undefined) {
  if (!status || status === "undecided") {
    return "";
  }

  if (status === "available") {
    return "available_all_day";
  }

  return status;
}

export function MobileStatusBand({
  todayAssignments,
  todayActuals,
  pendingCount,
  todayAvailability,
  templateStatus,
  templateReason,
  isLoading,
  hasError,
}: MobileStatusBandProps) {
  const activeActuals = todayActuals.filter((item) => item.start_time && !item.end_time);
  const completedActuals = todayActuals.filter((item) => item.end_time);
  const firstAssignment = todayAssignments[0];
  const availabilityStatus = normalizeAvailabilityStatus(todayAvailability?.status);
  const availabilitySource = availabilityStatus ? "保存済み" : templateStatus ? "自動候補" : "未登録";
  const availabilityLabel = availabilityStatus ? formatStatus(availabilityStatus) : templateStatus ? formatStatus(templateStatus) : "未登録";

  let headline = "本日の予定はありません";
  let summary = "回答待ちや打刻が発生したら、ここにその日の状況がまとまります。";

  if (isLoading) {
    headline = "本日の状況を確認中です";
    summary = "予定、打刻、事前予定をまとめて読み込んでいます。";
  } else if (hasError) {
    headline = "本日の状況を取得できませんでした";
    summary = "通信が安定したら自動で再取得されます。";
  } else if (activeActuals.length > 0) {
    headline = `${activeActuals.length}件が進行中です`;
    summary = `現在は ${firstAssignment?.project_name || activeActuals[0]?.project_name || "現場"} の対応中です。`;
  } else if (todayAssignments.length > 0) {
    headline = `今日は ${todayAssignments.length}件の予定があります`;
    summary = `${firstAssignment?.shift_label || "シフト"} / ${firstAssignment?.project_name || "案件"} が先頭です。`;
  } else if (pendingCount > 0) {
    headline = `回答待ちが ${pendingCount}件あります`;
    summary = "まずは予定確認を返して、未回答を減らしてください。";
  }

  return (
    <section className="mobile-status-band" aria-label="本日のクイック状況">
      <div className="mobile-status-band-copy">
        <p className="panel-label">クイック状況</p>
        <h2>{headline}</h2>
        <p>{summary}</p>
      </div>

      <div className="mobile-status-grid">
        <article className="mobile-status-card">
          <span className="mobile-status-kicker">今日の予定</span>
          <strong className="mobile-status-emphasis">{todayAssignments.length > 0 ? `${todayAssignments.length}件` : "なし"}</strong>
          <span className="mobile-status-meta">
            {todayAssignments.length > 0
              ? `${firstAssignment?.project_name || "案件"} / ${firstAssignment?.shift_label || "シフト指定なし"}`
              : "本日のアサインなし"}
          </span>
        </article>

        <article className="mobile-status-card">
          <span className="mobile-status-kicker">回答待ち</span>
          <strong className="mobile-status-emphasis">{pendingCount > 0 ? `${pendingCount}件` : "なし"}</strong>
          <span className="mobile-status-meta">{pendingCount > 0 ? "予定画面で返信できます" : "未回答はありません"}</span>
        </article>

        <article className="mobile-status-card">
          <span className="mobile-status-kicker">打刻状況</span>
          <strong className="mobile-status-emphasis">
            {activeActuals.length > 0 ? `出勤中 ${activeActuals.length}件` : completedActuals.length > 0 ? `完了 ${completedActuals.length}件` : "未着手"}
          </strong>
          <span className="mobile-status-meta">
            {activeActuals.length > 0
              ? `${formatTime(activeActuals[0]?.start_time)} から対応中`
              : completedActuals.length > 0
                ? `退勤済み ${completedActuals.length}件`
                : "打刻はまだありません"}
          </span>
        </article>

        <article className="mobile-status-card">
          <span className="mobile-status-kicker">今日の事前予定</span>
          <strong className="mobile-status-emphasis">{availabilityLabel}</strong>
          <span className="mobile-status-meta">
            {availabilitySource === "自動候補" && templateReason ? `${availabilitySource} / ${templateReason}` : availabilitySource}
          </span>
        </article>
      </div>
    </section>
  );
}