import { Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState, useMemo } from "react";

import { ErrorState } from "../components/ErrorState";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { getAvailabilityCalendar, patchWorkerQuals } from "../lib/api/client";
import { useAuth } from "../lib/auth/auth-context";
import type { CalendarDayInfo, CalendarWorkerRow, WorkerQualsUpdateRequest } from "../types/api";

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
type QualDef = { key: string; label: string };
const QUAL_DEFS: QualDef[] = [
  { key: "smoking_area_ok", label: "喫煙所" },
  { key: "p_shirt_count", label: "Pシャツ" },
  { key: "has_best", label: "ベスト" },
  { key: "license_type", label: "免許" },
  { key: "stores_training_done", label: "stores研修" },
  { key: "pioneer_training_done", label: "開拓研修" },
];

function WorkerQualBadge({ qKey, value }: { qKey: string; value: unknown }) {
  if (qKey === "p_shirt_count") {
    const n = value as number | null;
    if (n === null || n === undefined) return <span style={{ color: "#9ca3af" }}>−</span>;
    if (n === 0) return <span style={{ color: "#ef4444", fontWeight: 700 }}>✗</span>;
    return <span style={{ color: "#22c55e", fontWeight: 700 }}>{n}枚</span>;
  }
  if (qKey === "license_type") {
    const lt = value as string | null;
    if (!lt || lt === "none") return <span style={{ color: "#ef4444", fontWeight: 700 }}>✗</span>;
    if (lt === "hiace_ok") return <span style={{ color: "#22c55e", fontWeight: 700, fontSize: 10 }}>ハイエース</span>;
    if (lt === "at_only") return <span style={{ color: "#f59e0b", fontWeight: 700, fontSize: 10 }}>AT限定</span>;
    return <span style={{ color: "#6b7280", fontSize: 10 }}>{lt}</span>;
  }
  const b = value as boolean | null;
  if (b === null || b === undefined) return <span style={{ color: "#9ca3af" }}>−</span>;
  return <span style={{ color: b ? "#22c55e" : "#ef4444", fontWeight: 700 }}>{b ? "◯" : "✗"}</span>;
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
  const [showEditModal, setShowEditModal] = useState(false);
  const [editQualsMap, setEditQualsMap] = useState<Record<string, WorkerQualsUpdateRequest>>({});
  const [isSaving, setIsSaving] = useState(false);

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

  function openEditModal() {
    const init: Record<string, WorkerQualsUpdateRequest> = {};
    workers.forEach((w) => {
      init[w.id] = {
        smoking_area_ok: w.smoking_area_ok,
        p_shirt_count: w.p_shirt_count,
        has_best: w.has_best,
        stores_training_done: w.stores_training_done,
        pioneer_training_done: w.pioneer_training_done,
        license_type: w.license_type,
      };
    });
    setEditQualsMap(init);
    setShowEditModal(true);
  }

  async function saveQuals() {
    setIsSaving(true);
    try {
      await Promise.all(
        workers.map((w) => {
          const eq = editQualsMap[w.id];
          if (!eq) return Promise.resolve();
          return patchWorkerQuals(w.id, eq);
        })
      );
      setShowEditModal(false);
      calendarQuery.refetch();
    } catch {
      alert("保存に失敗しました");
    } finally {
      setIsSaving(false);
    }
  }

  // ─── レンダリング ─────────────────────────────────────────
  return (
    <div className="page-container">
      <PageHeader title="出勤可能日カレンダー" description="スタッフの出勤可能日とシフト担当を確認できます" />

      {/* ツールバー */}
      <div style={{ marginBottom: 12, padding: "8px 0" }}>
        {/* 行1: ナビ + 月/週 切り替え */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
        </div>

        {/* 行2: 資格情報 折りたたみ + 編集 */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
          <button
            className="btn btn-outline"
            style={{ fontSize: 13 }}
            onClick={() => setShowQual((v) => !v)}
          >
            情報{showQual ? "◀ 折りたたむ" : "▶ 展開する"}
          </button>
          <button
            className="btn btn-outline"
            style={{ fontSize: 13 }}
            onClick={openEditModal}
            disabled={calendarQuery.isLoading || workers.length === 0}
          >
            ✏️ 資格を編集
          </button>
        </div>
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

      {/* 資格編集モーダル */}
      {showEditModal && (
        <div
          style={{
            position: "fixed", inset: 0, zIndex: 50,
            background: "rgba(0,0,0,0.45)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}
          onClick={(e) => { if (e.target === e.currentTarget) setShowEditModal(false); }}
        >
          <div
            style={{
              background: "#fff", borderRadius: 10, boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
              width: "min(96vw, 860px)", maxHeight: "80vh",
              display: "flex", flexDirection: "column",
            }}
          >
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontWeight: 700, fontSize: 16 }}>資格情報の編集</span>
              <button
                style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", fontSize: 20, color: "#6b7280" }}
                onClick={() => setShowEditModal(false)}
              >×</button>
            </div>
            <div style={{ overflowY: "auto", flex: 1, padding: "12px 0" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ background: "#f9fafb" }}>
                    <th style={{ padding: "6px 12px", textAlign: "left", fontWeight: 600, borderBottom: "1px solid #e5e7eb", whiteSpace: "nowrap" }}>スタッフ</th>
                    <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>喫煙所</th>
                    <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>Pシャツ</th>
                    <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>ベスト</th>
                    <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>免許</th>
                    <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>stores研修</th>
                    <th style={{ padding: "6px 8px", textAlign: "center", fontWeight: 600, borderBottom: "1px solid #e5e7eb" }}>開拓研修</th>
                  </tr>
                </thead>
                <tbody>
                  {workers.map((w, i) => {
                    const eq = editQualsMap[w.id] ?? {
                      smoking_area_ok: null, p_shirt_count: null, has_best: null,
                      stores_training_done: null, pioneer_training_done: null, license_type: null,
                    };
                    const rowBg = i % 2 === 0 ? "#fff" : "#f9fafb";
                    function update<K extends keyof WorkerQualsUpdateRequest>(field: K, val: WorkerQualsUpdateRequest[K]) {
                      setEditQualsMap((prev) => ({ ...prev, [w.id]: { ...prev[w.id], [field]: val } }));
                    }
                    const selStyle: React.CSSProperties = { fontSize: 12, padding: "2px 4px", border: "1px solid #d1d5db", borderRadius: 4, background: "#fff" };
                    return (
                      <tr key={w.id} style={{ background: rowBg }}>
                        <td style={{ padding: "6px 12px", borderBottom: "1px solid #f3f4f6", whiteSpace: "nowrap", fontWeight: 500 }}>
                          {w.name}
                        </td>
                        {/* 喫煙所 */}
                        <td style={{ padding: "4px 8px", textAlign: "center", borderBottom: "1px solid #f3f4f6" }}>
                          <select style={selStyle} value={eq.smoking_area_ok === null ? "" : String(eq.smoking_area_ok)}
                            onChange={(e) => update("smoking_area_ok", e.target.value === "" ? null : e.target.value === "true")}>
                            <option value="">−</option>
                            <option value="true">◯</option>
                            <option value="false">✗</option>
                          </select>
                        </td>
                        {/* Pシャツ */}
                        <td style={{ padding: "4px 8px", textAlign: "center", borderBottom: "1px solid #f3f4f6" }}>
                          <select style={selStyle} value={eq.p_shirt_count === null ? "" : String(eq.p_shirt_count)}
                            onChange={(e) => update("p_shirt_count", e.target.value === "" ? null : Number(e.target.value))}>
                            <option value="">−</option>
                            <option value="0">✗(なし)</option>
                            <option value="1">1枚</option>
                            <option value="2">2枚</option>
                          </select>
                        </td>
                        {/* ベスト */}
                        <td style={{ padding: "4px 8px", textAlign: "center", borderBottom: "1px solid #f3f4f6" }}>
                          <select style={selStyle} value={eq.has_best === null ? "" : String(eq.has_best)}
                            onChange={(e) => update("has_best", e.target.value === "" ? null : e.target.value === "true")}>
                            <option value="">−</option>
                            <option value="true">◯</option>
                            <option value="false">✗</option>
                          </select>
                        </td>
                        {/* 免許 */}
                        <td style={{ padding: "4px 8px", textAlign: "center", borderBottom: "1px solid #f3f4f6" }}>
                          <select style={selStyle} value={eq.license_type ?? ""}
                            onChange={(e) => update("license_type", e.target.value || null)}>
                            <option value="">−</option>
                            <option value="hiace_ok">ハイエース可</option>
                            <option value="at_only">AT限定</option>
                            <option value="none">✗(なし)</option>
                          </select>
                        </td>
                        {/* stores研修 */}
                        <td style={{ padding: "4px 8px", textAlign: "center", borderBottom: "1px solid #f3f4f6" }}>
                          <select style={selStyle} value={eq.stores_training_done === null ? "" : String(eq.stores_training_done)}
                            onChange={(e) => update("stores_training_done", e.target.value === "" ? null : e.target.value === "true")}>
                            <option value="">−</option>
                            <option value="true">◯</option>
                            <option value="false">✗</option>
                          </select>
                        </td>
                        {/* 開拓研修 */}
                        <td style={{ padding: "4px 8px", textAlign: "center", borderBottom: "1px solid #f3f4f6" }}>
                          <select style={selStyle} value={eq.pioneer_training_done === null ? "" : String(eq.pioneer_training_done)}
                            onChange={(e) => update("pioneer_training_done", e.target.value === "" ? null : e.target.value === "true")}>
                            <option value="">−</option>
                            <option value="true">◯</option>
                            <option value="false">✗</option>
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ padding: "12px 20px", borderTop: "1px solid #e5e7eb", display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <button className="btn btn-outline" onClick={() => setShowEditModal(false)} disabled={isSaving}>キャンセル</button>
              <button className="btn btn-primary" onClick={saveQuals} disabled={isSaving}>
                {isSaving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
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
            <WorkerQualBadge qKey={q.key} value={(worker as unknown as Record<string, unknown>)[q.key]} />
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

// ─── 出勤ステータス別セル背景色（スマホと同配色） ────────────────
const AVAIL_CELL_BG: Record<string, { bg: string; border: string; color: string }> = {
  available_all_day: {
    bg: "linear-gradient(180deg, rgba(226,247,236,0.96), rgba(207,240,223,0.9))",
    border: "rgba(13,122,85,0.18)",
    color: "#0d6d4d",
  },
  available: {
    bg: "linear-gradient(180deg, rgba(226,247,236,0.96), rgba(207,240,223,0.9))",
    border: "rgba(13,122,85,0.18)",
    color: "#0d6d4d",
  },
  available_after_15: {
    bg: "linear-gradient(180deg, rgba(235,243,255,0.96), rgba(221,235,252,0.92))",
    border: "rgba(21,74,120,0.18)",
    color: "#154a78",
  },
  unavailable: {
    bg: "linear-gradient(180deg, rgba(254,236,239,0.97), rgba(248,214,220,0.92))",
    border: "rgba(157,49,65,0.2)",
    color: "#8d2032",
  },
  consult_required: {
    bg: "linear-gradient(180deg, rgba(253,244,212,0.98), rgba(248,225,174,0.9))",
    border: "rgba(122,82,21,0.18)",
    color: "#7a5215",
  },
};

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

  const statusStyle = avStatus ? AVAIL_CELL_BG[avStatus] : null;
  const cellBg = isToday
    ? "linear-gradient(180deg, #dbeafe, #eff6ff)"
    : (statusStyle?.bg ?? rowBg);
  const cellBorder = isToday ? "rgba(59,130,246,0.3)" : (statusStyle?.border ?? "#e5e7eb");

  return (
    <td
      style={{
        borderLeft: `1px solid ${cellBorder}`,
        borderBottom: `1px solid ${cellBorder}`,
        padding: "3px 3px",
        verticalAlign: "top",
        background: cellBg,
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
