import { WorkerName } from "../components/WorkerName";
/**
 * 参加カレンダーの横長の表示（0.48.6、0.48.8 で参加カレンダーに統合）。月の1日〜末日を横に並べ、依頼済みのイベントと稼働者を一覧する。
 * 表示は「イベントごと」（行＝イベント、マス＝その日の稼働者）と「稼働者ごと」（行＝稼働者、マス＝その日のイベント）を切り替える。
 * データは参加カレンダーと同じ（参加OK／変更確認待ち／未回答。同じ人は1日に1つだけ）。
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ErrorState } from "../components/ErrorState";
import { OrderRequestDetailDialog } from "../components/OrderRequestDetailDialog";
import { shiftMonth, todayInTokyo } from "../components/MonthCalendar";
import { ApiError, getParticipationCalendar, type ParticipationEvent } from "../lib/api/client";
import { categoryColor } from "../lib/calendarCategory";
import "../styles/orderOverview.css";

type Status = "ok" | "changing" | "unanswered" | "unavailable";
const STATUS_LABEL: Record<Status, string> = { ok: "参加OK", changing: "変更確認待ち", unanswered: "未回答", unavailable: "× 参加不可" };
const STATUSES: Status[] = ["ok", "changing", "unanswered", "unavailable"];


type EventRow = {
  seriesId: string;
  versionId: string;
  name: string;
  documentNumber: string;
  isTest: boolean;
  color: number;
  days: Map<string, ParticipationEvent>;
};
type WorkerCell = { seriesId: string; status: Status };
type WorkerRow = { workerId: string; name: string; isNewcomer?: boolean; lineLinked: boolean | null; days: Map<string, WorkerCell[]> };

/** 日付の欠けた所で分割。月の表示範囲を越えては結合しない。 */
function consecutiveRuns<T>(days: string[], valueOf: (day: string) => T | undefined): { start: number; items: T[] }[] {
  const runs: { start: number; items: T[] }[] = [];
  days.forEach((day, index) => {
    const item = valueOf(day);
    if (item === undefined) return;
    const last = runs[runs.length - 1];
    if (last && last.start + last.items.length === index) last.items.push(item);
    else runs.push({ start: index, items: [item] });
  });
  return runs;
}

function workerRuns(row: WorkerRow, days: string[]) {
  const ids = new Set([...row.days.values()].flatMap((cells) => cells.map((cell) => cell.seriesId)));
  const runs = [...ids].flatMap((seriesId) => [false, true].flatMap((refused) => consecutiveRuns(days, (day) => row.days.get(day)?.find((cell) => cell.seriesId === seriesId && (cell.status === "unavailable") === refused))));
  runs.sort((a, b) => a.start - b.start || b.items.length - a.items.length || a.items[0].seriesId.localeCompare(b.items[0].seriesId));
  const ends: number[] = [];
  return runs.map((run) => {
    let lane = ends.findIndex((end) => end < run.start);
    if (lane < 0) lane = ends.length;
    ends[lane] = run.start + run.items.length - 1;
    return { ...run, lane };
  });
}

function monthDays(month: string): string[] {
  const [year, mon] = month.split("-").map(Number);
  const count = new Date(Date.UTC(year, mon, 0)).getUTCDate();
  return Array.from({ length: count }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`);
}

function weekday(day: string): number {
  return new Date(`${day}T00:00:00+09:00`).getDay();
}

function firstLine(text: string): string {
  return (text || "").split("\n")[0].trim() || "案件";
}

/** 参加カレンダーの横長の表示（イベントごと・稼働者ごと）。表示の切り替えは参加カレンダーの画面が持つ。 */
export function OrderOverviewBody() {
  const [detailVersionId, setDetailVersionId] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const month = searchParams.get("month") || todayInTokyo().slice(0, 7);
  const mode = searchParams.get("view") === "worker" ? "worker" : "event";
  const includeTest = searchParams.get("test") === "1";
  const today = todayInTokyo();
  const days = useMemo(() => monthDays(month), [month]);

  function update(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null) next.delete(key);
      else next.set(key, value);
    }
    setSearchParams(next);
  }

  const query = useQuery({
    queryKey: ["order-overview", month, includeTest],
    queryFn: () => getParticipationCalendar({ month, includeTest, includeWorkers: true }),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

  const { events, workers } = useMemo(() => {
    const eventMap = new Map<string, EventRow>();
    const workerMap = new Map<string, WorkerRow>();
    // 登録のある稼働者は、依頼がなくても全員出す（登録の順＝ふりがな順）
    for (const worker of query.data?.workers ?? []) {
      workerMap.set(worker.worker_id, { workerId: worker.worker_id, name: worker.name, isNewcomer: worker.is_newcomer, lineLinked: worker.line_linked, days: new Map() });
    }
    const registeredCount = workerMap.size;
    for (const day of query.data?.days ?? []) {
      for (const event of day.events) {
        let row = eventMap.get(event.series_id);
        if (!row) {
          row = {
            seriesId: event.series_id,
            versionId: event.version_id,
            name: firstLine(event.project_name),
            documentNumber: event.document_number,
            isTest: Boolean(event.is_test),
            color: categoryColor(event.categories),
            days: new Map(),
          };
          eventMap.set(event.series_id, row);
        }
        row.days.set(day.date, event);
        for (const status of STATUSES) {
          for (const person of (event[status] ?? [])) {
            let worker = workerMap.get(person.worker_id);
            if (!worker) {
              worker = { workerId: person.worker_id, name: person.name, isNewcomer: person.is_newcomer, lineLinked: null, days: new Map() };
              workerMap.set(person.worker_id, worker);
            }
            const cells = worker.days.get(day.date) ?? [];
            cells.push({ seriesId: event.series_id, status });
            worker.days.set(day.date, cells);
          }
        }
      }
    }
    // イベントは最初の日の順、同じ日は名前の順。色は依頼書のカテゴリに固定する
    const eventRows = [...eventMap.values()].sort((a, b) => {
      const first = (row: EventRow) => [...row.days.keys()].sort()[0] ?? "";
      return first(a).localeCompare(first(b)) || a.name.localeCompare(b.name, "ja");
    });

    // 登録の順のまま。登録一覧にない人（無効にした人など）は後ろに名前の順で付ける
    const allWorkers = [...workerMap.values()];
    const workerRows = [...allWorkers.slice(0, registeredCount), ...allWorkers.slice(registeredCount).sort((a, b) => a.name.localeCompare(b.name, "ja"))];
    return { events: eventRows, workers: workerRows };
  }, [query.data]);
  const eventById = useMemo(() => new Map(events.map((e) => [e.seriesId, e])), [events]);

  const [year, mon] = month.split("-").map(Number);

  return (
    <div className="page-stack">
      <section className="card overview-toolbar">
        <div className="overview-month">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => update({ month: shiftMonth(month, -1) })} aria-label="前の月">‹ 前の月</button>
          <strong>{year}年{mon}月</strong>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => update({ month: shiftMonth(month, 1) })} aria-label="次の月">次の月 ›</button>
          {month !== today.slice(0, 7) ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => update({ month: null })}>今月</button>
          ) : null}
        </div>
        <p className="overview-legend">
          <span className="ov-person is-ok">参加OK</span>
          <span className="ov-person is-changing">変更確認待ち</span>
          <span className="ov-person is-unanswered">未回答</span>
          <span className="ov-person is-unavailable">× 参加不可</span>
        </p>
      </section>

      {query.isError ? (
        <ErrorState title="読み込めませんでした" description={query.error instanceof ApiError ? query.error.message : "時間をおいて再度お試しください。"} />
      ) : query.isLoading ? (
        <p className="order-field-hint">読み込んでいます…</p>
      ) : (mode === "event" ? events.length : workers.length) === 0 ? (
        <section className="card"><p className="order-field-hint">{mode === "event" ? "この月に依頼済みのイベントはありません。" : "登録のある稼働者がいません。"}</p></section>
      ) : (
        <section className="card overview-scroll" aria-label={`${year}年${mon}月の${mode === "event" ? "イベントごと" : "稼働者ごと"}の表示`}>
          <table className={`overview-grid is-${mode}`}>
            <thead>
              <tr>
                <th className="overview-head-name">{mode === "event" ? "イベント" : "稼働者"}</th>
                {days.map((day) => {
                  const wd = weekday(day);
                  return (
                    <th key={day} className={`overview-head-day${wd === 0 ? " is-sun" : wd === 6 ? " is-sat" : ""}${day === today ? " is-today" : ""}`}>
                      <span className="ov-day-num">{Number(day.slice(8))}</span>
                      <span className="ov-day-wd">{"日月火水木金土"[wd]}</span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {mode === "event"
                ? events.map((row) => (
                    <tr key={row.seriesId}>
                      <th className="overview-row-name" scope="row">
                        <span className={`ov-swatch ov-c${row.color}`} aria-hidden="true" />
                        <span className="ov-row-title">{row.name}</span>
                        <span className="ov-row-sub"><button type="button" className="ov-document-link" onClick={() => setDetailVersionId(row.versionId)}>{row.documentNumber}</button></span>
                      </th>
                      {(() => {
                        const runs = consecutiveRuns(days, (day) => row.days.get(day));
                        const cells = [];
                        let cursor = 0;
                        for (const run of runs) {
                          if (run.start > cursor) cells.push(<td key={`empty-${cursor}`} colSpan={run.start - cursor} className="overview-cell" />);
                          cells.push(<td key={run.start} colSpan={run.items.length} className="overview-cell overview-event-run-cell">
                            <div className={`ov-event-run ov-c${row.color}`} data-series-id={row.seriesId}
                              style={{ gridTemplateColumns: `repeat(${run.items.length}, minmax(0, 1fr))` }}>
                              {run.items.map((event, index) => {
                                const total = event.ok.length + event.changing.length + event.unanswered.length + (event.unavailable?.length ?? 0);
                                return <div key={days[run.start + index]} className={`ov-event-box ov-c${row.color}`}>
                                  <span className={`ov-event-name${index ? " is-repeat" : ""}`} aria-hidden={index > 0}>{row.name}</span>
                                  <span className="ov-count">参加OK {event.ok.length}人</span>
                                  {total === 0 ? <span className="ov-empty">まだ誰もいません</span> : null}
                                  {STATUSES.flatMap((status) => (event[status] ?? []).map((person) => <span key={`${status}-${person.worker_id}`} className={`ov-person is-${status}`} title={STATUS_LABEL[status]}>{status === "unavailable" ? "× " : ""}<WorkerName name={person.name} isNewcomer={person.is_newcomer} /></span>))}
                                </div>;
                              })}
                            </div>
                          </td>);
                          cursor = run.start + run.items.length;
                        }
                        if (cursor < days.length) cells.push(<td key={`empty-${cursor}`} colSpan={days.length - cursor} className="overview-cell" />);
                        return cells;
                      })()}
                    </tr>
                  ))
                : workers.map((row) => (
                    <tr key={row.workerId} data-worker-id={row.workerId}>
                      <th className="overview-row-name" scope="row">
                        <span className="ov-row-title"><WorkerName name={row.name} isNewcomer={row.isNewcomer} /></span>
                        {row.lineLinked === false ? <span className="ov-line-badge">LINE未連携</span> : null}
                        {row.lineLinked === null ? <span className="ov-row-sub">登録の一覧にない人</span> : null}
                      </th>
                      <td colSpan={days.length} className="overview-worker-track-cell">
                        <div className="ov-worker-track" style={{ gridTemplateColumns: `repeat(${days.length}, minmax(var(--overview-day-width), 1fr))`, backgroundSize: `${100 / days.length}% 100%` }}>
                          {workerRuns(row, days).map((run) => {
                            const event = eventById.get(run.items[0].seriesId);
                            if (!event) return null;
                            const state = run.items.every((item) => item.status === run.items[0].status) ? run.items[0].status : "mixed";
                            const label = `${Number(days[run.start].slice(8))}日〜${Number(days[run.start + run.items.length - 1].slice(8))}日（${run.items.length}日間）`;
                            return <div key={`${event.seriesId}-${run.start}`} className={`ov-worker-run ov-event-chip ov-c${event.color} is-${state}`}
                              data-series-id={event.seriesId} data-lane={run.lane} data-days={run.items.length}
                              style={{ gridColumn: `${run.start + 1} / span ${run.items.length}`, gridRow: run.lane + 1 }}
                              title={`${event.name}（${event.documentNumber}）${label}`}>
                              <span className="ov-worker-run-title">{event.name}{run.items.length > 1 ? <small className="ov-run-length">{run.items.length}日間</small> : null}</span>
                              <div className="ov-worker-run-days" style={{ gridTemplateColumns: `repeat(${run.items.length}, minmax(0, 1fr))` }}>
                                {run.items.map((item, index) => <small key={index}>{Number(days[run.start + index].slice(8))}日 {STATUS_LABEL[item.status]}</small>)}
                              </div>
                            </div>;
                          })}
                        </div>
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </section>
      )}
      {detailVersionId ? <OrderRequestDetailDialog versionId={detailVersionId} onClose={() => setDetailVersionId(null)} /> : null}
    </div>
  );
}
