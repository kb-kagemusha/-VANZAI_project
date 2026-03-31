import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, getAssignments, getWorkerAvailability, upsertWorkerAvailability } from "../lib/api/client";
import { currentMonthInput, formatDate, formatStatus, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";

const statusOptions = [
  { value: "undecided", label: "未回答" },
  { value: "available", label: "対応可" },
  { value: "unavailable", label: "不可" },
];

function buildMonthDates(monthValue: string) {
  const [year, month] = monthValue.split("-").map(Number);
  const daysInMonth = new Date(year, month, 0).getDate();

  return Array.from({ length: daysInMonth }, (_, index) => {
    const day = String(index + 1).padStart(2, "0");
    return `${year}-${String(month).padStart(2, "0")}-${day}`;
  });
}

export function AvailabilityPage() {
  const queryClient = useQueryClient();
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [drafts, setDrafts] = useState<Record<string, { status: string; notes: string }>>({});
  const [message, setMessage] = useState("");
  const periodKey = toPeriodKey(monthValue);
  const { from, to } = periodKeyToDateRange(periodKey);

  const availabilityQuery = useQuery({
    queryKey: ["staff-availability", periodKey],
    queryFn: () =>
      getWorkerAvailability({
        availability_date_from: from,
        availability_date_to: to,
        sort_by: "availability_date",
        sort_order: "asc",
        limit: 100,
      }),
  });

  const assignmentsQuery = useQuery({
    queryKey: ["staff-availability-assignments", periodKey],
    queryFn: () =>
      getAssignments({
        work_date_from: from,
        work_date_to: to,
        sort_by: "work_date",
        sort_order: "asc",
        limit: 100,
      }),
  });

  useEffect(() => {
    const nextDrafts: Record<string, { status: string; notes: string }> = {};
    for (const item of availabilityQuery.data?.items ?? []) {
      nextDrafts[item.availability_date] = {
        status: item.status,
        notes: item.notes || "",
      };
    }
    setDrafts(nextDrafts);
  }, [availabilityQuery.data, monthValue]);

  const saveMutation = useMutation({
    mutationFn: (payload: { availability_date: string; status: string; notes: string }) => upsertWorkerAvailability(payload),
    onSuccess: async () => {
      setMessage("稼働可否を更新しました。");
      await queryClient.invalidateQueries({ queryKey: ["staff-availability", periodKey] });
    },
    onError: (error) => {
      setMessage(error instanceof ApiError ? error.message : "稼働可否の更新に失敗しました。");
    },
  });

  const assignmentByDate = useMemo(() => {
    const mapping: Record<string, string[]> = {};
    for (const item of assignmentsQuery.data?.items ?? []) {
      mapping[item.work_date] = [...(mapping[item.work_date] || []), `${item.project_name} / ${item.shift_label || "シフト指定なし"}`];
    }
    return mapping;
  }, [assignmentsQuery.data]);

  if (availabilityQuery.isLoading || assignmentsQuery.isLoading) {
    return <div className="panel-card">稼働可否を読み込み中...</div>;
  }

  if (availabilityQuery.isError || assignmentsQuery.isError) {
    return (
      <div className="panel-card">
        <h2>稼働可否を取得できませんでした</h2>
        <p>
          {availabilityQuery.error instanceof ApiError
            ? availabilityQuery.error.message
            : assignmentsQuery.error instanceof ApiError
              ? assignmentsQuery.error.message
              : "API 疎通を確認してください。"}
        </p>
      </div>
    );
  }

  const days = buildMonthDates(monthValue);

  return (
    <div className="page-stack">
      <section className="hero-panel tide">
        <p className="panel-label">稼働可否入力</p>
        <div className="month-toolbar">
          <h2>{monthValue}</h2>
          <input type="month" value={monthValue} onChange={(event) => setMonthValue(event.target.value)} />
        </div>
        <p>日付ごとに対応可否を登録します。予定がある日は下段に表示します。</p>
      </section>

      {message ? <div className="panel-card action-banner">{message}</div> : null}

      <section className="list-section">
        <div className="section-heading">
          <h2>日別入力</h2>
          <span>{days.length} 日</span>
        </div>

        {days.map((day) => {
          const draft = drafts[day] || { status: "undecided", notes: "" };
          const assignments = assignmentByDate[day] || [];

          return (
            <article key={day} className="actual-card">
              <div className="assignment-header">
                <div>
                  <p className="panel-label">{formatDate(day)}</p>
                  <h3>{formatStatus(draft.status)}</h3>
                </div>
                <select
                  value={draft.status}
                  onChange={(event) => setDrafts((current) => ({ ...current, [day]: { ...draft, status: event.target.value } }))}
                >
                  {statusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <textarea
                rows={2}
                value={draft.notes}
                placeholder="補足があれば入力"
                onChange={(event) => setDrafts((current) => ({ ...current, [day]: { ...draft, notes: event.target.value } }))}
              />
              {assignments.length > 0 ? (
                <div className="note-banner">
                  予定: {assignments.join(" / ")}
                </div>
              ) : null}
              <div className="button-row">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => saveMutation.mutate({ availability_date: day, status: draft.status, notes: draft.notes })}
                  disabled={saveMutation.isPending}
                >
                  {saveMutation.isPending ? "保存中..." : "保存する"}
                </button>
              </div>
            </article>
          );
        })}
      </section>
    </div>
  );
}