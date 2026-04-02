import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, getAssignments, updateAssignmentWorkerResponse } from "../lib/api/client";
import { currentMonthInput, formatCurrency, formatDate, formatDateTime, formatStatus, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";
import type { AssignmentListItem, PageResponse } from "../types/api";

export function SchedulePage() {
  const queryClient = useQueryClient();
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [message, setMessage] = useState<string | null>(null);
  const [responseNotes, setResponseNotes] = useState<Record<string, string>>({});
  const periodKey = toPeriodKey(monthValue);
  const { from, to } = periodKeyToDateRange(periodKey);

  const assignmentsQuery = useQuery({
    queryKey: ["staff-schedule", periodKey],
    queryFn: () =>
      getAssignments({
        work_date_from: from,
        work_date_to: to,
        sort_by: "work_date",
        sort_order: "asc",
        limit: 100,
      }),
  });

  const responseMutation = useMutation({
    mutationFn: ({ assignmentId, payload }: { assignmentId: string; payload: { response_status: "accepted" | "declined"; note?: string } }) =>
      updateAssignmentWorkerResponse(assignmentId, payload),
    onSuccess: async (updatedAssignment) => {
      setMessage("予定確認を更新しました。");
      setResponseNotes((current) => ({
        ...current,
        [updatedAssignment.id]: updatedAssignment.worker_response_note || "",
      }));
      queryClient.setQueryData<PageResponse<AssignmentListItem>>(["staff-schedule", periodKey], (previous) =>
        previous
          ? {
              ...previous,
              items: previous.items.map((item) => (item.id === updatedAssignment.id ? updatedAssignment : item)),
            }
          : undefined,
      );
      queryClient.setQueryData<PageResponse<AssignmentListItem>>(["staff-schedule-pending"], (previous) => {
        if (!previous) {
          return undefined;
        }

        const nextItems = previous.items.filter((item) => item.id !== updatedAssignment.id);
        return {
          ...previous,
          items: nextItems,
          total: nextItems.length,
        };
      });
      await queryClient.invalidateQueries({ queryKey: ["staff-schedule"], refetchType: "active" });
      await queryClient.invalidateQueries({ queryKey: ["staff-schedule-pending"], refetchType: "active" });
    },
    onError: (error) => {
      setMessage(error instanceof ApiError ? error.message : "予定確認の更新に失敗しました。");
    },
  });

  if (assignmentsQuery.isLoading) {
    return <div className="panel-card">予定を読み込み中...</div>;
  }

  if (assignmentsQuery.isError) {
    return (
      <div className="panel-card">
        <h2>予定を取得できませんでした</h2>
        <p>{assignmentsQuery.error instanceof ApiError ? assignmentsQuery.error.message : "API 疎通を確認してください。"}</p>
      </div>
    );
  }

  const assignments = assignmentsQuery.data?.items ?? [];
  const pendingAssignments = assignments.filter((assignment) => assignment.status !== "canceled" && assignment.worker_response_status === "pending");
  const acceptedCount = assignments.filter((assignment) => assignment.worker_response_status === "accepted").length;
  const declinedCount = assignments.filter((assignment) => assignment.worker_response_status === "declined").length;
  const pendingMutationId = responseMutation.isPending ? responseMutation.variables?.assignmentId : null;

  const submitResponse = (assignmentId: string, responseStatus: "accepted" | "declined") => {
    setMessage(null);
    const note = responseNotes[assignmentId]?.trim();
    responseMutation.mutate({
      assignmentId,
      payload: {
        response_status: responseStatus,
        note: note || undefined,
      },
    });
  };

  return (
    <div className="page-stack">
      <section className="hero-panel sunrise">
        <p className="panel-label">予定確認</p>
        <div className="month-toolbar">
          <h2>{monthValue}</h2>
          <input type="month" value={monthValue} onChange={(event) => setMonthValue(event.target.value)} />
        </div>
        <p>対象月の自分の配置を日付順に確認し、参加可否をそのまま返信します。</p>
      </section>

      {message ? <section className="panel-card note-banner action-banner">{message}</section> : null}

      {pendingAssignments.length > 0 ? (
        <section className="panel-card accent-orange">
          <p className="panel-label">確認待ち</p>
          <strong>{pendingAssignments.length} 件の予定が未回答です</strong>
          <p>次の確認対象: {formatDate(pendingAssignments[0]?.work_date)}</p>
        </section>
      ) : null}

      <section className="panel-grid four-up">
        <article className="panel-card accent-sand">
          <p className="panel-label">件数</p>
          <strong>{assignments.length} 件</strong>
        </article>
        <article className="panel-card accent-blue">
          <p className="panel-label">確認待ち</p>
          <strong>{pendingAssignments.length} 件</strong>
        </article>
        <article className="panel-card accent-green">
          <p className="panel-label">参加可</p>
          <strong>{acceptedCount} 件</strong>
        </article>
        <article className="panel-card accent-orange">
          <p className="panel-label">辞退</p>
          <strong>{declinedCount} 件</strong>
        </article>
      </section>

      <section className="list-section">
        <div className="section-heading">
          <h2>予定一覧</h2>
          <span>{assignments.length} 件</span>
        </div>

        {assignments.length === 0 ? (
          <div className="panel-card empty-card">対象月の予定はありません。</div>
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
              <div className="inline-meta response-meta">
                <span className={`status-pill status-${assignment.worker_response_status || "pending"}`}>
                  {assignment.worker_response_status ? formatStatus(assignment.worker_response_status) : "未設定"}
                </span>
                <span>依頼: {formatDateTime(assignment.worker_response_requested_at)}</span>
                {assignment.worker_response_at ? <span>回答: {formatDateTime(assignment.worker_response_at)}</span> : null}
              </div>
              <dl className="detail-grid">
                <div>
                  <dt>日付</dt>
                  <dd>{formatDate(assignment.work_date)}</dd>
                </div>
                <div>
                  <dt>役割</dt>
                  <dd>{assignment.role_name}</dd>
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
              {assignment.cancel_reason ? <p className="note-banner">取消理由: {assignment.cancel_reason}</p> : null}
              {assignment.status !== "canceled" ? (
                <div className="response-stack">
                  <label className="response-note-field">
                    連絡メモ
                    <textarea
                      rows={3}
                      value={responseNotes[assignment.id] ?? assignment.worker_response_note ?? ""}
                      onChange={(event) =>
                        setResponseNotes((current) => ({
                          ...current,
                          [assignment.id]: event.target.value,
                        }))
                      }
                      placeholder="集合や調整事項があれば入力"
                    />
                  </label>
                  <div className="response-actions">
                    <button
                      type="button"
                      className="primary-button"
                      onClick={() => submitResponse(assignment.id, "accepted")}
                      disabled={responseMutation.isPending && pendingMutationId === assignment.id}
                    >
                      {responseMutation.isPending && pendingMutationId === assignment.id ? "送信中..." : "参加可で返信"}
                    </button>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => submitResponse(assignment.id, "declined")}
                      disabled={responseMutation.isPending && pendingMutationId === assignment.id}
                    >
                      辞退で返信
                    </button>
                  </div>
                </div>
              ) : null}
            </article>
          ))
        )}
      </section>
    </div>
  );
}