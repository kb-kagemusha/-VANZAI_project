import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";

import { ErrorState } from "../components/ErrorState";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { getAvailabilityCalendar } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import type { CalendarDayInfo, CalendarWorkerRow } from "../types/api";

// ─── 日付ヘルパー ───────────────────────────────────────────────
function toDateStr(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

function buildDateRange(anchor: Date, mode: "month" | "week"): { from: Date; to: Date } {
  if (mode === "week") {
    return { from: anchor, to: addDays(anchor, 6) };
  }
  // 月表示: anchorが属する月の1日〜末日
  const from = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const to = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
  return { from, to };
}

function eachDay(from: Date, to: Date): Date[] {
  const days: Date[] = [];
  let cur = new Date(from);
  while (cur <= to) {
    days.push(new Date(cur));
    cur = addDays(cur, 1);
  }
  return days;
}

function formatMonthLabel(d: Date): string {
  return `${d.getFullYear()}年${d.getMonth() + 1}月`;
}

const DOW_LABELS = ["日", "月", "火", "水", "木", "金", "土"];

// ─── 出勤可否 ─────────────────────────────────────────────────
const AVAIL_LABEL: Record<string, { label: string; color: string }> = {
  available_all_day: { label: "◯", color: "#22c55e" },
  available: { label: "◯", color: "#22c55e" },
  available_after_15: { label: "△", color: "#f59e0b" },
  unavailable: { label: "✗", color: "#ef4444" },
  consult_required: { label: "要相談", color: "#8b5cf6" },
};

function AvailBadge({ status }: { status: string | null }) {
  if (!status) {
    return <span style={{ color: "#9ca3af", fontSize: 12 }}>−</span>;
  }
  const cfg = AVAIL_LABEL[status] ?? { label: status, color: "#6b7280" };
  return (
    <span style={{ color: cfg.color, fontWeight: 700, fontSize: 13 }}>
      {cfg.label}
    </span>
  );
}

// ─── 配置チップ ────────────────────────────────────────────────
const ASSIGN_STATUS_COLOR: Record<string, string> = {
  tentative: "#93c5fd",
  confirmed: "#6ee7b7",
  canceled: "#fca5a5",
};

function AssignChip({ name, status }: { name: string; status: string }) {
  return (
    <span
      title={name}
      style={{
        display: "inline-block",
        background: ASSIGN_STATUS_COLOR[status] ?? "#e5e7eb",
        borderRadius: 4,
        padding: "1px 4px",
        fontSize: 10,
        lineHeight: 1.4,
        maxWidth: 80,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
      }}
    >
      {name}
    </span>
  );
}

// ─── 資格表示 ──────────────────────────────────────────────────
const QUAL_DEFS: { key: keyof Pick<CalendarWorkerRow, "smoking_area_ok" | "has_p_shirt" | "has_best" | "stores_training_done" | "pioneer_training_done">; label: string }[] = [
  { key: "smoking_area_ok", label: "喫煙所" },
  { key: "has_p_shirt", label: "Pシャツ" },
  { key: "has_best", label: "ベスト" },
  { key: "stores_training_done", label: "stores研修" },
  { key: "pioneer_training_done", label: "開拓研修" },
];

function QualBadge({ value }: { value: boolean | null }) {
  if (value === null || value === undefined) return <span style={{ color: "#9ca3af" }}>−</span>;
  return (
    <span style={{ color: value ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
      {value ? "◯" : "✗"}
    </span>
  );
}

// ─── メインコンポーネント ─────────────────────────────────────
export function AvailabilityCalendarPage() {
  const { user } = useAuth();
  const today = useMemo(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    return d;
  }, []);

  const [mode, setMode] = useState<"month" | "week">("month");
  const [anchorDate, setAnchorDate] = useState<Date>(today);
  const [showQual, setShowQual] = useState(true);

  if (!user) return <Navigate to="/login" replace />;

  const { from, to } = buildDateRange(anchorDate, mode);
  const days = eachDay(from, to);
  const dateFromStr = toDateStr(from);
  const dateToStr = toDateStr(to);
  const todayStr = toDateStr(today);

  const calendarQuery = useQuery({
    queryKey: ["availability-calendar", dateFromStr, dateToStr],
    queryFn: () => getAvailabilityCalendar({ date_from: dateFromStr, date_to: dateToStr }),
  });

  // ─── ナビゲーション ─────────────────────────────────────────
  function prevPeriod() {
    setAnchorDate((prev) =>
      mode === "week" ? addDays(prev, -7) : new Date(prev.getFullYear(), prev.getMonth() - 1, 1)
    );
  }

  function nextPeriod() {
    setAnchorDate((prev) =>
      mode === "week" ? addDays(prev, 7) : new Date(prev.getFullYear(), prev.getMonth() + 1, 1)
    );
  }

  function goToday() {
    setAnchorDate(today);
  }

  const periodLabel =
    mode === "month"
      ? formatMonthLabel(from)
      : `${from.getMonth() + 1}/${from.getDate()} 〜 ${to.getMonth() + 1}/${to.getDate()}`;

  const workers = calendarQuery.data?.workers ?? [];

  // ─── レンダリング ─────────────────────────────────────────
  return (
    <div className="page-container">
      <PageHeader title="出勤可能日カレンダー" description="スタッフの出勤可能日とシフト担当を確認できます" />

      {/* ツールバー */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          flexWrap: "wrap",
          marginBottom: 12,
          padding: "8px 0",
        }}
      >
        {/* 期間ナビ */}
        <button className="btn btn-outline" onClick={prevPeriod}>
          ＜
        </button>
        <button className="btn btn-outline" onClick={goToday} style={{ minWidth: 64 }}>
          今日
        </button>
        <button className="btn btn-outline" onClick={nextPeriod}>
          ＞
        </button>
        <span style={{ fontWeight: 600, minWidth: 140, textAlign: "center" }}>{periodLabel}</span>

        {/* 月/週切り替え */}
        <div style={{ display: "flex", gap: 0, marginLeft: 8 }}>
          <button
            className={`btn ${mode === "month" ? "btn-primary" : "btn-outline"}`}
            style={{ borderRadius: "4px 0 0 4px" }}
            onClick={() => setMode("month")}
          >
            月
          </button>
          <button
            className={`btn ${mode === "week" ? "btn-primary" : "btn-outline"}`}
            style={{ borderRadius: "0 4px 4px 0" }}
            onClick={() => setMode("week")}
          >
            週
          </button>
        </div>

        {/* 資格表示切り替え */}
        <button
          className="btn btn-outline"
          style={{ marginLeft: "auto" }}
          onClick={() => setShowQual((v) => !v)}
        >
          資格情報 {showQual ? "▲ 折りたたむ" : "▼ 展開する"}
        </button>
      </div>

      {calendarQuery.isLoading && <LoadingOverlay />}
      {calendarQuery.isError && (
        <ErrorState title="データ読み込みエラー" description="カレンダーデータの読み込みに失敗しました。ページを再読み込みしてください。" />
      )}

      {/* カレンダーグリッド */}
      {!calendarQuery.isLoading && !calendarQuery.isError && (
        <div
          style={{
            overflowX: "auto",
            overflowY: "auto",
            maxHeight: "calc(100vh - 220px)",
            border: "1px solid #e5e7eb",
            borderRadius: 8,
          }}
        >
          <table
            style={{
              borderCollapse: "collapse",
              tableLayout: "fixed",
              width: "max-content",
              minWidth: "100%",
            }}
          >
            <colgroup>
              {/* 左固定列: 名前列と資格列 */}
              <col style={{ width: 130 }} />
              {showQual && QUAL_DEFS.map((q) => <col key={q.key} style={{ width: 64 }} />)}
              {/* 日付列 */}
              {days.map((d) => (
                <col key={toDateStr(d)} style={{ width: 72 }} />
              ))}
            </colgroup>

            {/* ヘッダー行 */}
            <thead>
              <tr>
                {/* 左上コーナー */}
                <th
                  style={{
                    position: "sticky",
                    left: 0,
                    zIndex: 20,
                    background: "#f3f4f6",
                    borderRight: "2px solid #d1d5db",
                    borderBottom: "1px solid #d1d5db",
                    padding: "6px 8px",
                    fontSize: 12,
                    textAlign: "left",
                    whiteSpace: "nowrap",
                  }}
                >
                  スタッフ
                </th>
                {/* 資格列ヘッダー */}
                {showQual &&
                  QUAL_DEFS.map((q, i) => (
                    <th
                      key={q.key}
                      style={{
                        position: "sticky",
                        left: 130 + i * 64,
                        zIndex: 20,
                        background: "#f3f4f6",
                        borderRight: i === QUAL_DEFS.length - 1 ? "2px solid #d1d5db" : "1px solid #e5e7eb",
                        borderBottom: "1px solid #d1d5db",
                        padding: "4px 2px",
                        fontSize: 10,
                        textAlign: "center",
                        whiteSpace: "nowrap",
                        color: "#6b7280",
                      }}
                    >
                      {q.label}
                    </th>
                  ))}
                {/* 日付列ヘッダー */}
                {days.map((d) => {
                  const ds = toDateStr(d);
                  const dow = d.getDay();
                  const isToday = ds === todayStr;
                  const isSun = dow === 0;
                  const isSat = dow === 6;
                  return (
                    <th
                      key={ds}
                      style={{
                        background: isToday
                          ? "#dbeafe"
                          : isSun
                            ? "#fff1f2"
                            : isSat
                              ? "#eff6ff"
                              : "#f9fafb",
                        borderBottom: "1px solid #d1d5db",
                        borderLeft: "1px solid #e5e7eb",
                        padding: "4px 2px",
                        fontSize: 11,
                        textAlign: "center",
                        whiteSpace: "nowrap",
                        fontWeight: isToday ? 700 : 400,
                        color: isSun ? "#ef4444" : isSat ? "#3b82f6" : "#374151",
                      }}
                    >
                      <div>{d.getDate()}</div>
                      <div style={{ fontSize: 10, color: isSun ? "#ef4444" : isSat ? "#3b82f6" : "#9ca3af" }}>
                        {DOW_LABELS[dow]}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>

            {/* ボディ */}
            <tbody>
              {workers.length === 0 && (
                <tr>
                  <td
                    colSpan={1 + (showQual ? QUAL_DEFS.length : 0) + days.length}
                    style={{ padding: 24, textAlign: "center", color: "#6b7280" }}
                  >
                    スタッフデータがありません
                  </td>
                </tr>
              )}
              {workers.map((worker, rowIndex) => (
                <WorkerRow
                  key={worker.id}
                  worker={worker}
                  days={days}
                  showQual={showQual}
                  todayStr={todayStr}
                  rowIndex={rowIndex}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 凡例 */}
      <div style={{ display: "flex", gap: 12, marginTop: 12, flexWrap: "wrap", fontSize: 11, color: "#6b7280" }}>
        <span>出勤可否:</span>
        {Object.entries(AVAIL_LABEL).slice(0, 4).map(([k, v]) => (
          <span key={k} style={{ color: v.color, fontWeight: 700 }}>
            {v.label} {k === "available_all_day" ? "出勤可" : k === "available_after_15" ? "15時〜可" : k === "unavailable" ? "不可" : "要相談"}
          </span>
        ))}
        <span style={{ marginLeft: 8 }}>配置:</span>
        {Object.entries(ASSIGN_STATUS_COLOR).map(([k, c]) => (
          <span key={k} style={{ background: c, padding: "1px 6px", borderRadius: 4 }}>
            {k === "tentative" ? "仮" : k === "confirmed" ? "確定" : "取消"}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── ワーカー行コンポーネント ─────────────────────────────────
function WorkerRow({
  worker,
  days,
  showQual,
  todayStr,
  rowIndex,
}: {
  worker: CalendarWorkerRow;
  days: Date[];
  showQual: boolean;
  todayStr: string;
  rowIndex: number;
}) {
  const rowBg = rowIndex % 2 === 0 ? "#ffffff" : "#f9fafb";
  const qualStickyLeft = 130;

  return (
    <tr>
      {/* スタッフ名（固定） */}
      <td
        style={{
          position: "sticky",
          left: 0,
          zIndex: 10,
          background: rowBg,
          borderRight: "2px solid #d1d5db",
          borderBottom: "1px solid #e5e7eb",
          padding: "6px 8px",
          fontSize: 13,
          fontWeight: 500,
          whiteSpace: "nowrap",
          maxWidth: 130,
          overflow: "hidden",
          textOverflow: "ellipsis",
          color: worker.is_active ? "#111827" : "#9ca3af",
        }}
        title={worker.name}
      >
        {worker.name}
        {!worker.is_active && (
          <span style={{ fontSize: 10, color: "#9ca3af", marginLeft: 4 }}>(無効)</span>
        )}
      </td>

      {/* 資格列（固定）*/}
      {showQual &&
        QUAL_DEFS.map((q, i) => (
          <td
            key={q.key}
            style={{
              position: "sticky",
              left: qualStickyLeft + i * 64,
              zIndex: 10,
              background: rowBg,
              borderRight: i === QUAL_DEFS.length - 1 ? "2px solid #d1d5db" : "1px solid #e5e7eb",
              borderBottom: "1px solid #e5e7eb",
              padding: "4px 2px",
              textAlign: "center",
              fontSize: 13,
            }}
          >
            <QualBadge value={worker[q.key] as boolean | null} />
          </td>
        ))}

      {/* 日付セル */}
      {days.map((d) => {
        const ds = toDateStr(d);
        const dayInfo: CalendarDayInfo | undefined = worker.days[ds];
        const isToday = ds === todayStr;

        return (
          <DayCell
            key={ds}
            dayInfo={dayInfo}
            isToday={isToday}
            rowBg={rowBg}
          />
        );
      })}
    </tr>
  );
}

// ─── 日付セルコンポーネント ──────────────────────────────────
function DayCell({
  dayInfo,
  isToday,
  rowBg,
}: {
  dayInfo: CalendarDayInfo | undefined;
  isToday: boolean;
  rowBg: string;
}) {
  const assignments = dayInfo?.assignments ?? [];
  const avStatus = dayInfo?.availability_status ?? null;

  return (
    <td
      style={{
        borderLeft: "1px solid #e5e7eb",
        borderBottom: "1px solid #e5e7eb",
        padding: "3px 3px",
        verticalAlign: "top",
        background: isToday ? "#eff6ff" : rowBg,
        minHeight: 40,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 2, alignItems: "center", minHeight: 36 }}>
        {/* 出勤可否 */}
        <AvailBadge status={avStatus} />

        {/* 配置チップ */}
        {assignments.map((a) => (
          <AssignChip key={a.id} name={a.project_name} status={a.status} />
        ))}
      </div>
    </td>
  );
}
