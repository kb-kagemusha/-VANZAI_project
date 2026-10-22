/**
 * 依頼の俯瞰カレンダー（0.48.6）。月の1日〜末日を横に並べ、依頼済みのイベントと稼働者を一覧する。
 * 表示は「イベントごと」（行＝イベント、マス＝その日の稼働者）と「稼働者ごと」（行＝稼働者、マス＝その日のイベント）を切り替える。
 * データは参加カレンダーと同じ（参加OK／変更確認待ち／未回答。同じ人は1日に1つだけ）。
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { ErrorState } from "../components/ErrorState";
import { shiftMonth, todayInTokyo } from "../components/MonthCalendar";
import { PageHeader } from "../components/PageHeader";
import { ApiError, getParticipationCalendar, type ParticipationEvent } from "../lib/api/client";
import "../styles/orderOverview.css";

type Status = "ok" | "changing" | "unanswered";
const STATUS_LABEL: Record<Status, string> = { ok: "参加OK", changing: "変更確認待ち", unanswered: "未回答" };
const STATUSES: Status[] = ["ok", "changing", "unanswered"];
const PALETTE_SIZE = 8;

type EventRow = {
  seriesId: string;
  name: string;
  documentNumber: string;
  siteName: string;
  isTest: boolean;
  color: number;
  days: Map<string, ParticipationEvent>;
};
type WorkerCell = { seriesId: string; status: Status };
type WorkerRow = { workerId: string; name: string; days: Map<string, WorkerCell[]> };

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

export function OrderOverviewPage() {
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
    queryFn: () => getParticipationCalendar({ month, includeTest }),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });

  const { events, workers } = useMemo(() => {
    const eventMap = new Map<string, EventRow>();
    const workerMap = new Map<string, WorkerRow>();
    for (const day of query.data?.days ?? []) {
      for (const event of day.events) {
        let row = eventMap.get(event.series_id);
        if (!row) {
          row = {
            seriesId: event.series_id,
            name: firstLine(event.project_name),
            documentNumber: event.document_number,
            siteName: firstLine(event.site_name ?? ""),
            isTest: Boolean(event.is_test),
            color: 0,
            days: new Map(),
          };
          eventMap.set(event.series_id, row);
        }
        row.days.set(day.date, event);
        for (const status of STATUSES) {
          for (const person of event[status]) {
            let worker = workerMap.get(person.worker_id);
            if (!worker) {
              worker = { workerId: person.worker_id, name: person.name, days: new Map() };
              workerMap.set(person.worker_id, worker);
            }
            const cells = worker.days.get(day.date) ?? [];
            cells.push({ seriesId: event.series_id, status });
            worker.days.set(day.date, cells);
          }
        }
      }
    }
    // イベントは最初の日の順、同じ日は名前の順。色はその順に割り当てる
    const eventRows = [...eventMap.values()].sort((a, b) => {
      const first = (row: EventRow) => [...row.days.keys()].sort()[0] ?? "";
      return first(a).localeCompare(first(b)) || a.name.localeCompare(b.name, "ja");
    });
    eventRows.forEach((row, index) => { row.color = index % PALETTE_SIZE; });
    const workerRows = [...workerMap.values()].sort((a, b) => a.name.localeCompare(b.name, "ja"));
    return { events: eventRows, workers: workerRows };
  }, [query.data]);
  const eventById = useMemo(() => new Map(events.map((e) => [e.seriesId, e])), [events]);

  const [year, mon] = month.split("-").map(Number);

  return (
    <div className="page-stack">
      <PageHeader
        title="依頼の俯瞰カレンダー"
        eyebrow="運用"
        description="依頼済みのイベント（確定した発注依頼書）を、月の1日から末日まで横に並べて表示します。「イベントごと」は各イベントの日ごとの稼働者、「稼働者ごと」は各稼働者の日ごとのイベントです。取消した依頼書は出しません。"
      />
      <section className="card overview-toolbar">
        <div className="overview-month">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => update({ month: shiftMonth(month, -1) })} aria-label="前の月">‹ 前の月</button>
          <strong>{year}年{mon}月</strong>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => update({ month: shiftMonth(month, 1) })} aria-label="次の月">次の月 ›</button>
          {month !== today.slice(0, 7) ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => update({ month: null })}>今月</button>
          ) : null}
        </div>
        <div className="overview-modes" role="group" aria-label="表示の切り替え">
          <button type="button" aria-pressed={mode === "event"} className={mode === "event" ? "is-active" : ""} onClick={() => update({ view: null })}>イベントごと</button>
          <button type="button" aria-pressed={mode === "worker"} className={mode === "worker" ? "is-active" : ""} onClick={() => update({ view: "worker" })}>稼働者ごと</button>
        </div>
        <label className="order-check overview-test">
          <input type="checkbox" checked={includeTest} onChange={(e) => update({ test: e.target.checked ? "1" : null })} />
          テストの依頼書も表示
        </label>
        <p className="overview-legend">
          <span className="ov-person is-ok">参加OK</span>
          <span className="ov-person is-changing">変更確認待ち</span>
          <span className="ov-person is-unanswered">未回答</span>
        </p>
      </section>

      {query.isError ? (
        <ErrorState title="読み込めませんでした" description={query.error instanceof ApiError ? query.error.message : "時間をおいて再度お試しください。"} />
      ) : query.isLoading ? (
        <p className="order-field-hint">読み込んでいます…</p>
      ) : (mode === "event" ? events.length : workers.length) === 0 ? (
        <section className="card"><p className="order-field-hint">{mode === "event" ? "この月に依頼済みのイベントはありません。" : "この月に依頼している稼働者はいません。"}</p></section>
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
                        <span className="ov-row-title">{row.isTest ? <span className="ov-test">テスト</span> : null}{row.name}</span>
                        <span className="ov-row-sub">{row.documentNumber}{row.siteName ? `・${row.siteName}` : ""}</span>
                      </th>
                      {days.map((day, index) => {
                        const event = row.days.get(day);
                        if (!event) return <td key={day} className="overview-cell" />;
                        const startsRun = !row.days.has(days[index - 1] ?? "");
                        const endsRun = !row.days.has(days[index + 1] ?? "");
                        const total = event.ok.length + event.changing.length + event.unanswered.length;
                        return (
                          <td key={day} className="overview-cell">
                            <div className={`ov-event-box ov-c${row.color}${startsRun ? " is-start" : ""}${endsRun ? " is-end" : ""}`}>
                              <span className={`ov-event-name${startsRun ? "" : " is-repeat"}`} aria-hidden={!startsRun}>{row.name}</span>
                              <span className="ov-count">参加OK {event.ok.length}人</span>
                              {total === 0 ? <span className="ov-empty">まだ誰もいません</span> : null}
                              {STATUSES.flatMap((status) => event[status].map((person) => (
                                <span key={`${status}-${person.worker_id}`} className={`ov-person is-${status}`} title={STATUS_LABEL[status]}>{person.name}</span>
                              )))}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))
                : workers.map((row) => (
                    <tr key={row.workerId}>
                      <th className="overview-row-name" scope="row"><span className="ov-row-title">{row.name}</span></th>
                      {days.map((day) => {
                        const cells = row.days.get(day) ?? [];
                        return (
                          <td key={day} className="overview-cell">
                            {cells.map((cell) => {
                              const event = eventById.get(cell.seriesId);
                              if (!event) return null;
                              return (
                                <span key={cell.seriesId} className={`ov-event-chip ov-c${event.color} is-${cell.status}`} title={`${event.name}（${event.documentNumber}）${STATUS_LABEL[cell.status]}`}>
                                  {event.isTest ? "［テスト］" : ""}{event.name}
                                  {cell.status !== "ok" ? <small>{STATUS_LABEL[cell.status]}</small> : null}
                                </span>
                              );
                            })}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
