import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, getAssignments, getWorkerAvailability, getWorkerAvailabilityPreferences, upsertWorkerAvailability } from "../lib/api/client";
import { currentDateInput, currentMonthInput, formatDate, formatStatus, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";
import {
  availabilityStatusOptions as statusOptions,
  getAvailabilityTemplateDetail,
  normalizeStaffAvailabilityPreferences,
} from "../lib/settings/staffPreferences";

const weekdayLabels = ["日", "月", "火", "水", "木", "金", "土"];

type AvailabilityDraft = {
  status: string;
  notes: string;
};

function buildMonthDates(monthValue: string) {
  const [year, month] = monthValue.split("-").map(Number);
  const daysInMonth = new Date(year, month, 0).getDate();

  return Array.from({ length: daysInMonth }, (_, index) => {
    const day = String(index + 1).padStart(2, "0");
    return `${year}-${String(month).padStart(2, "0")}-${day}`;
  });
}

function buildCalendarCells(monthValue: string) {
  const [year, month] = monthValue.split("-").map(Number);
  const firstWeekday = new Date(year, month - 1, 1).getDay();
  const cells: Array<string | null> = Array.from({ length: firstWeekday }, () => null);

  cells.push(...buildMonthDates(monthValue));

  while (cells.length % 7 !== 0) {
    cells.push(null);
  }

  return cells;
}

function normalizeDraftStatus(status: string) {
  if (status === "available") {
    return "available_all_day";
  }

  if (status === "undecided") {
    return "";
  }

  return status;
}

function getStatusMeta(status: string) {
  const normalized = normalizeDraftStatus(status);
  return statusOptions.find((option) => option.value === normalized) || null;
}

function getNextStatus(status: string) {
  const normalized = normalizeDraftStatus(status);

  if (!normalized) {
    return statusOptions[0].value;
  }

  const currentIndex = statusOptions.findIndex((option) => option.value === normalized);
  if (currentIndex === -1) {
    return statusOptions[0].value;
  }

  return statusOptions[(currentIndex + 1) % statusOptions.length].value;
}

function resolveInitialSelectedDay(monthValue: string) {
  const today = currentDateInput();
  if (today.startsWith(monthValue)) {
    return today;
  }

  return buildMonthDates(monthValue)[0];
}

export function AvailabilityPage() {
  const queryClient = useQueryClient();
  const initialMonthValue = currentMonthInput();
  const [monthValue, setMonthValue] = useState(initialMonthValue);
  const [drafts, setDrafts] = useState<Record<string, AvailabilityDraft>>({});
  const [touchedDays, setTouchedDays] = useState<string[]>([]);
  const [selectedDay, setSelectedDay] = useState(resolveInitialSelectedDay(initialMonthValue));
  const [showNotesEditor, setShowNotesEditor] = useState(false);
  const [message, setMessage] = useState("");
  const periodKey = toPeriodKey(monthValue);
  const { from, to } = periodKeyToDateRange(periodKey);

  const preferencesQuery = useQuery({
    queryKey: ["staff-availability-preferences"],
    queryFn: () => getWorkerAvailabilityPreferences(),
  });

  const preferences = useMemo(() => normalizeStaffAvailabilityPreferences(preferencesQuery.data), [preferencesQuery.data]);

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
    const nextDrafts: Record<string, AvailabilityDraft> = {};
    for (const item of availabilityQuery.data?.items ?? []) {
      nextDrafts[item.availability_date] = {
        status: normalizeDraftStatus(item.status),
        notes: item.notes || "",
      };
    }
    for (const day of buildMonthDates(monthValue)) {
      if (!nextDrafts[day]) {
        const templateStatus = getAvailabilityTemplateDetail(day, preferences).status;
        if (templateStatus) {
          nextDrafts[day] = {
            status: templateStatus,
            notes: "",
          };
        }
      }
    }
    setDrafts(nextDrafts);
    setSelectedDay((current) => {
      const days = buildMonthDates(monthValue);
      return days.includes(current) ? current : resolveInitialSelectedDay(monthValue);
    });
    setTouchedDays([]);
    setShowNotesEditor(false);
  }, [availabilityQuery.data, monthValue, preferences]);

  const saveMutation = useMutation({
    mutationFn: async (payload: Array<{ availability_date: string; status: string; notes: string }>) =>
      Promise.all(payload.map((item) => upsertWorkerAvailability(item))),
    onSuccess: async () => {
      setMessage("事前予定を更新しました。");
      await queryClient.invalidateQueries({ queryKey: ["staff-availability", periodKey] });
    },
    onError: (error) => {
      setMessage(error instanceof ApiError ? error.message : "事前予定の更新に失敗しました。");
    },
  });

  const assignmentByDate = useMemo(() => {
    const mapping: Record<string, string[]> = {};
    for (const item of assignmentsQuery.data?.items ?? []) {
      mapping[item.work_date] = [...(mapping[item.work_date] || []), `${item.project_name} / ${item.shift_label || "シフト指定なし"}`];
    }
    return mapping;
  }, [assignmentsQuery.data]);

  const originalDrafts = useMemo(() => {
    const mapping: Record<string, AvailabilityDraft> = {};
    for (const item of availabilityQuery.data?.items ?? []) {
      mapping[item.availability_date] = {
        status: normalizeDraftStatus(item.status),
        notes: item.notes || "",
      };
    }
    return mapping;
  }, [availabilityQuery.data]);

  const days = buildMonthDates(monthValue);
  const calendarCells = buildCalendarCells(monthValue);
  const touchedDaySet = useMemo(() => new Set(touchedDays), [touchedDays]);
  const templateDetailsByDay = useMemo(() => {
    const mapping: Record<string, ReturnType<typeof getAvailabilityTemplateDetail>> = {};
    for (const day of days) {
      mapping[day] = getAvailabilityTemplateDetail(day, preferences);
    }
    return mapping;
  }, [days, preferences]);

  if (availabilityQuery.isLoading || assignmentsQuery.isLoading || preferencesQuery.isLoading) {
    return <div className="panel-card">事前予定を読み込み中...</div>;
  }

  if (availabilityQuery.isError || assignmentsQuery.isError || preferencesQuery.isError) {
    return (
      <div className="panel-card">
        <h2>事前予定を取得できませんでした</h2>
        <p>
          {availabilityQuery.error instanceof ApiError
            ? availabilityQuery.error.message
            : assignmentsQuery.error instanceof ApiError
              ? assignmentsQuery.error.message
              : preferencesQuery.error instanceof ApiError
                ? preferencesQuery.error.message
              : "API 疎通を確認してください。"}
        </p>
      </div>
    );
  }

  const dirtyDays = days.filter((day) => {
    const draft = drafts[day] || { status: "", notes: "" };
    const original = originalDrafts[day] || { status: "", notes: "" };
    return draft.status !== original.status || draft.notes !== original.notes;
  });

  function isAutoCandidateDay(day: string) {
    const draft = drafts[day] || { status: "", notes: "" };
    const templateDetail = templateDetailsByDay[day];
    return !originalDrafts[day] && !touchedDaySet.has(day) && Boolean(templateDetail?.status) && draft.status === templateDetail.status && !draft.notes;
  }

  const autoCandidateDays = days.filter((day) => isAutoCandidateDay(day));
  const autoCandidateSet = new Set(autoCandidateDays);
  const manualDirtyDays = dirtyDays.filter((day) => !autoCandidateSet.has(day));
  const selectedDraft = drafts[selectedDay] || { status: "", notes: "" };
  const selectedAssignments = assignmentByDate[selectedDay] || [];
  const selectedStatusMeta = getStatusMeta(selectedDraft.status);
  const selectedTemplateDetail = templateDetailsByDay[selectedDay] || { status: "", reason: "", source: null };
  const selectedIsAutoCandidate = isAutoCandidateDay(selectedDay);

  function resolveBaseDraft(day: string): AvailabilityDraft {
    const original = originalDrafts[day];
    if (original) {
      return original;
    }

    const templateStatus = templateDetailsByDay[day]?.status || "";
    return {
      status: templateStatus,
      notes: "",
    };
  }

  function updateDraft(day: string, nextDraft: AvailabilityDraft, markTouched = true) {
    setMessage("");
    setDrafts((current) => ({
      ...current,
      [day]: nextDraft,
    }));
    setTouchedDays((current) => {
      if (markTouched) {
        return current.includes(day) ? current : [...current, day];
      }
      return current.filter((value) => value !== day);
    });
  }

  function handleDayTap(day: string) {
    const draft = drafts[day] || resolveBaseDraft(day);
    updateDraft(day, { ...draft, status: getNextStatus(draft.status) });
    setSelectedDay(day);
  }

  function handleClearSelectedDay() {
    updateDraft(selectedDay, resolveBaseDraft(selectedDay), false);
    setShowNotesEditor(false);
  }

  function handleSaveAll() {
    if (dirtyDays.length === 0) {
      setMessage("変更はありません。");
      return;
    }

    saveMutation.mutate(
      dirtyDays.map((day) => {
        const draft = drafts[day] || { status: "", notes: "" };
        return {
          availability_date: day,
          status: draft.status || "undecided",
          notes: draft.notes,
        };
      }),
    );
  }

  return (
    <div className="page-stack">
      <section className="hero-panel tide">
        <p className="panel-label">事前予定登録</p>
        <div className="month-toolbar">
          <h2>{monthValue}</h2>
          <input
            type="month"
            value={monthValue}
            onChange={(event) => {
              setMessage("");
              setMonthValue(event.target.value);
            }}
          />
        </div>
        <p>1か月を一覧で見ながら、日付タップで事前予定を切り替えます。既に予定が入っている日はカレンダー内に件数を表示します。</p>
      </section>

      <section className="panel-card accent-sand">
        <p className="panel-label">入力方法</p>
        <p>日付をタップするたびに 稼働OK（1日） → 稼働OK（15時〜） → 稼働不可 → 事前相談 の順で切り替わります。自動候補は保存するまで確定せず、手動変更と見分けて表示します。</p>
        <Link to="/settings" className="text-link">個人設定で基本スケジュールを変更する</Link>
      </section>

      {message ? <div className="panel-card action-banner">{message}</div> : null}

      <section className="list-section">
        <div className="section-heading">
          <h2>月間カレンダー</h2>
          <span>{manualDirtyDays.length} 件手動変更 / {autoCandidateDays.length} 件自動候補</span>
        </div>

        <div className="calendar-weekdays">
          {weekdayLabels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>

        <div className="calendar-grid">
          {calendarCells.map((day, index) => {
            if (!day) {
              return <div key={`empty-${index}`} className="calendar-spacer" aria-hidden="true" />;
            }

            const draft = drafts[day] || { status: "", notes: "" };
            const assignments = assignmentByDate[day] || [];
            const statusMeta = getStatusMeta(draft.status);
            const dateValue = new Date(day);
            const isAutoCandidate = isAutoCandidateDay(day);

            return (
              <button
                key={day}
                type="button"
                className={`calendar-day ${draft.status ? `status-${draft.status}` : "status-blank"} ${selectedDay === day ? "selected" : ""}`}
                onClick={() => handleDayTap(day)}
                aria-label={`${formatDate(day)} ${draft.status ? formatStatus(draft.status) : "未登録"}${assignments.length > 0 ? " 予定あり" : ""}`}
              >
                <div className="calendar-day-top">
                  <strong className="calendar-day-number">{dateValue.getDate()}</strong>
                  <span className="calendar-day-weekday">{weekdayLabels[dateValue.getDay()]}</span>
                </div>
                <div className="calendar-day-body">
                  <span className="calendar-day-status">{statusMeta?.shortLabel || "未登録"}</span>
                  {assignments.length > 0 ? <span className="calendar-day-assignment">予定 {assignments.length}件</span> : null}
                  {draft.notes ? <span className="calendar-day-note">補足あり</span> : null}
                  {isAutoCandidate ? <span className="calendar-day-auto-badge">自動候補</span> : null}
                </div>
              </button>
            );
          })}
        </div>

        <article className="actual-card calendar-detail-card">
          <div className="assignment-header">
            <div>
              <p className="panel-label">選択中の日付</p>
              <h3>{formatDate(selectedDay)}</h3>
            </div>
            <span className={`status-pill ${selectedDraft.status ? `status-${selectedDraft.status}` : "status-pending"}`}>
              {selectedStatusMeta?.label || "未登録"}
            </span>
          </div>

          <div className="note-banner">日付タップで状態を切り替えます。未登録に戻したい日は下のボタンでクリアできます。</div>

          {selectedIsAutoCandidate ? (
            <div className="note-banner auto-candidate-banner">
              自動候補: {selectedTemplateDetail.reason} により {formatStatus(selectedTemplateDetail.status)} を表示しています。保存するまで確定しません。
            </div>
          ) : null}

          {!originalDrafts[selectedDay] && !selectedIsAutoCandidate && touchedDaySet.has(selectedDay) && selectedTemplateDetail.status ? (
            <div className="note-banner">この日は自動候補をもとに手動で調整中です。保存すると確定します。</div>
          ) : null}

          {selectedAssignments.length > 0 ? <div className="note-banner">予定: {selectedAssignments.join(" / ")}</div> : null}

          <div className="calendar-detail-actions">
            <button type="button" className="secondary-button" onClick={() => setShowNotesEditor((current) => !current)}>
              {showNotesEditor ? "補足入力を閉じる" : selectedDraft.notes ? "補足を編集" : "補足を入力"}
            </button>
            <button type="button" className="secondary-button" onClick={handleClearSelectedDay}>
              {originalDrafts[selectedDay] ? "保存済みに戻す" : selectedTemplateDetail.status ? "自動候補に戻す" : "未登録に戻す"}
            </button>
          </div>

          {showNotesEditor ? (
            <label className="calendar-notes-field">
              補足
              <textarea
                rows={3}
                value={selectedDraft.notes}
                placeholder="必要な補足がある日だけ入力"
                onChange={(event) => updateDraft(selectedDay, { ...selectedDraft, notes: event.target.value })}
              />
            </label>
          ) : selectedDraft.notes ? (
            <div className="note-banner">補足: {selectedDraft.notes}</div>
          ) : null}

          <div className="button-row">
            <button type="button" className="primary-button" onClick={handleSaveAll} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "保存中..." : `候補と変更を保存${dirtyDays.length > 0 ? ` (${dirtyDays.length}件)` : ""}`}
            </button>
          </div>
        </article>
      </section>
    </div>
  );
}