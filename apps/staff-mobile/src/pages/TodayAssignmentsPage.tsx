import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, checkInAssignment, checkOutAssignment, getActuals, getAssignments } from "../lib/api/client";
import { currentDateInput, formatCurrency, formatDate, formatStatus, formatTime, minutesToHours } from "../lib/formatters";

export function TodayAssignmentsPage() {
  const today = currentDateInput();
  const queryClient = useQueryClient();
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const assignmentsQuery = useQuery({
    queryKey: ["staff-today-assignments", today],
    queryFn: () =>
      getAssignments({
        work_date_from: today,
        work_date_to: today,
        sort_by: "work_date",
        sort_order: "asc",
        limit: 20,
      }),
  });

  const actualsQuery = useQuery({
    queryKey: ["staff-today-actuals", today],
    queryFn: () =>
      getActuals({
        work_date_from: today,
        work_date_to: today,
        sort_by: "work_date",
        sort_order: "asc",
        limit: 20,
      }),
  });

  const invalidateAttendanceQueries = async () => {
    await queryClient.invalidateQueries({ queryKey: ["staff-today-actuals", today] });
    await queryClient.invalidateQueries({ queryKey: ["staff-actuals"] });
  };

  const checkInMutation = useMutation({
    mutationFn: ({ assignmentId }: { assignmentId: string }) =>
      checkInAssignment(assignmentId, { action_time: new Date().toTimeString().slice(0, 8) }),
    onSuccess: async () => {
      setActionMessage("出勤を記録しました。");
      await invalidateAttendanceQueries();
    },
    onError: (error) => {
      setActionMessage(error instanceof ApiError ? error.message : "出勤打刻に失敗しました。");
    },
  });

  const checkOutMutation = useMutation({
    mutationFn: ({ assignmentId }: { assignmentId: string }) =>
      checkOutAssignment(assignmentId, { action_time: new Date().toTimeString().slice(0, 8), break_minutes_input: 0 }),
    onSuccess: async () => {
      setActionMessage("退勤を記録しました。");
      await invalidateAttendanceQueries();
    },
    onError: (error) => {
      setActionMessage(error instanceof ApiError ? error.message : "退勤打刻に失敗しました。");
    },
  });

  if (assignmentsQuery.isLoading || actualsQuery.isLoading) {
    return <div className="panel-card">本日のアサインを読み込み中...</div>;
  }

  if (assignmentsQuery.isError || actualsQuery.isError) {
    return (
      <div className="panel-card">
        <h2>本日のアサインを取得できませんでした</h2>
        <p>
          {assignmentsQuery.error instanceof ApiError
            ? assignmentsQuery.error.message
            : actualsQuery.error instanceof ApiError
              ? actualsQuery.error.message
              : "API 疎通を確認してください。"}
        </p>
      </div>
    );
  }

  const assignments = assignmentsQuery.data?.items ?? [];
  const actuals = actualsQuery.data?.items ?? [];
  const attendanceByAssignment = Object.fromEntries(
    actuals.filter((row) => row.assignment_id).map((row) => [row.assignment_id as string, row]),
  );
  const checkedInCount = actuals.filter((row) => row.start_time && !row.end_time).length;
  const completedCount = actuals.filter((row) => row.end_time).length;

  return (
    <div className="page-stack">
      <section className="hero-panel sunrise">
        <p className="panel-label">今日の動き</p>
        <h2>{formatDate(today)}</h2>
        <p>{assignments.length > 0 ? `${assignments.length} 件のアサインがあります。` : "本日のアサインはありません。"}</p>
      </section>

      <section className="panel-grid two-up">
        <article className="panel-card accent-orange">
          <p className="panel-label">出勤中</p>
          <strong>{checkedInCount} 件</strong>
          <p>現場入り済みで、まだ退勤していないアサイン数です。</p>
        </article>
        <article className="panel-card accent-blue">
          <p className="panel-label">退勤済み</p>
          <strong>{completedCount} 件</strong>
          <p>本日中に退勤完了まで記録された件数です。</p>
        </article>
      </section>

      {actionMessage ? <div className="panel-card action-banner">{actionMessage}</div> : null}

      <section className="list-section">
        <div className="section-heading">
          <h2>本日のアサイン</h2>
          <span>{assignments.length} 件</span>
        </div>

        {assignments.length === 0 ? (
          <div className="panel-card empty-card">本日の予定はまだありません。</div>
        ) : (
          assignments.map((assignment) => (
            <article key={assignment.id} className="assignment-card">
              <div className="assignment-header">
                <div>
                  <p className="panel-label">{assignment.project_name}</p>
                  <h3>{assignment.shift_label || "シフト指定なし"}</h3>
                </div>
                <span className={`status-pill status-${assignment.status}`}>{formatStatus(assignment.status)}</span>
              </div>
              {attendanceByAssignment[assignment.id] ? (
                <div className="inline-meta">
                  <strong>打刻</strong>
                  <span>
                    {formatTime(attendanceByAssignment[assignment.id].start_time)} - {formatTime(attendanceByAssignment[assignment.id].end_time)}
                  </span>
                  <span>{minutesToHours(attendanceByAssignment[assignment.id].calc_minutes_billable)}</span>
                </div>
              ) : null}
              <dl className="detail-grid">
                <div>
                  <dt>役割</dt>
                  <dd>{assignment.role_name}</dd>
                </div>
                <div>
                  <dt>日付</dt>
                  <dd>{formatDate(assignment.work_date)}</dd>
                </div>
                <div>
                  <dt>売上単価</dt>
                  <dd>{formatCurrency(assignment.locked_price_sales)}</dd>
                </div>
                <div>
                  <dt>外注単価</dt>
                  <dd>{formatCurrency(assignment.locked_price_outsource)}</dd>
                </div>
              </dl>
              <div className="button-row">
                {attendanceByAssignment[assignment.id]?.end_time ? (
                  <div className="note-banner">このアサインは退勤まで記録済みです。</div>
                ) : attendanceByAssignment[assignment.id]?.start_time ? (
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => checkOutMutation.mutate({ assignmentId: assignment.id })}
                    disabled={checkOutMutation.isPending && checkOutMutation.variables?.assignmentId === assignment.id}
                  >
                    {checkOutMutation.isPending && checkOutMutation.variables?.assignmentId === assignment.id ? "記録中..." : "退勤する"}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => checkInMutation.mutate({ assignmentId: assignment.id })}
                    disabled={checkInMutation.isPending && checkInMutation.variables?.assignmentId === assignment.id}
                  >
                    {checkInMutation.isPending && checkInMutation.variables?.assignmentId === assignment.id ? "記録中..." : "出勤する"}
                  </button>
                )}
              </div>
              {assignment.cancel_reason ? <p className="note-banner">取消理由: {assignment.cancel_reason}</p> : null}
            </article>
          ))
        )}
      </section>
    </div>
  );
}