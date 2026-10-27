import { WorkerName } from "../components/WorkerName";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ErrorState } from "../components/ErrorState";
import { MonthCalendar, todayInTokyo } from "../components/MonthCalendar";
import { PageHeader } from "../components/PageHeader";
import { ApiError, getParticipationCalendar, type ParticipationDay, type ParticipationEvent, type ParticipationPerson } from "../lib/api/client";
import { categoryColor } from "../lib/calendarCategory";
import "../styles/monthCalendar.css";
import "../styles/orderOverview.css";

function dayLabel(day: string): string {
  const [, m, d] = day.split("-").map(Number);
  const weekday = "日月火水木金土"[new Date(`${day}T00:00:00+09:00`).getDay()];
  return `${m}月${d}日（${weekday}）`;
}

/** 参加カレンダー（統合計画 ①、D-07）：イベントごとに、日ごとの参加OK／変更確認待ち／未回答の人数。 */
export function ParticipationCalendarPage({ embedded = false }: { embedded?: boolean } = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const month = searchParams.get("month") || todayInTokyo().slice(0, 7);
  const includeTest = searchParams.get("test") === "1";
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const query = useQuery({
    queryKey: ["participation-calendar", month, includeTest],
    queryFn: () => getParticipationCalendar({ month, includeTest }),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
  const byDay = useMemo(() => new Map((query.data?.days ?? []).map((d) => [d.date, d])), [query.data]);
  const selected = selectedDay ? byDay.get(selectedDay) : undefined;

  return (
    <div className="page-stack">
      {embedded ? null : <PageHeader
        title="参加カレンダー"
        description="正式の発注依頼書について、イベントごと・日ごとの参加OKの人数を表示します。運営確定方式では運営の決定後に参加OKになります。従来方式は受諾で参加OKです。確認待ち＝前の版で受諾済みで新しい版は未回答、未回答＝送付済みでまだ返事がない人です。同じ人は1日に1つにだけ数えます。テストの依頼書と取消した依頼書は出しません。"
        eyebrow="運用"
      />}
      {query.isError ? (
        <ErrorState title="参加カレンダーを読み込めませんでした" description={query.error instanceof ApiError ? query.error.message : "時間をおいて再度お試しください。"} />
      ) : (
        <div className="participation-layout">
          <section className="card participation-calendar">
            <MonthCalendar
              month={month}
              onMonthChange={(next) => { setSelectedDay(null); setSearchParams((current) => { const params = new URLSearchParams(current); params.set("month", next); return params; }); }}
              renderDay={(day) => <DayCell day={day} data={byDay.get(day)} selected={selectedDay === day} onSelect={setSelectedDay} />}
            />
            <p className="participation-legend"><span className="pc-ok">OK</span>参加OK　<span className="pc-changing">確認</span>変更確認待ち　<span className="pc-unanswered">未</span>未回答　<span className="pc-unavailable">×</span>参加不可</p>
          </section>
          <section className="card participation-detail">
            {selected ? (
              <>
                <h3>{dayLabel(selected.date)}</h3>
                {selected.events.map((event) => <EventDetail key={event.series_id} event={event} />)}
              </>
            ) : (
              <p className="order-field-hint">日付を押すと、その日のイベントと参加者が表示されます。</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function DayCell({ day, data, selected, onSelect }: { day: string; data?: ParticipationDay; selected: boolean; onSelect: (day: string) => void }) {
  const today = day === todayInTokyo();
  return (
    <button type="button" className={`pc-day${selected ? " is-selected" : ""}${today ? " is-today" : ""}`} onClick={() => onSelect(day)}>
      <span className="pc-day-num">{Number(day.slice(8))}</span>
      {(data?.events ?? []).map((event) => (
        <span key={event.series_id} className={`pc-event ov-c${categoryColor(event.categories)}`} title={event.project_name}>
          <span className="pc-event-name">{(event.project_name || "").split("\n")[0] || event.document_number}</span>
          <span className="pc-ok">{event.ok.length}</span>
          {event.pending?.length ? <span className="pc-changing">待{event.pending.length}</span> : null}
      {event.changing.length > 0 ? <span className="pc-changing">{event.changing.length}</span> : null}
          {event.unanswered.length > 0 ? <span className="pc-unanswered">{event.unanswered.length}</span> : null}
          {event.unavailable?.length ? <span className="pc-unavailable">×{event.unavailable.length}</span> : null}
        </span>
      ))}
    </button>
  );
}

function EventDetail({ event }: { event: ParticipationEvent }) {
  return (
    <div className="pc-detail-event">
      <strong>{event.project_name || "案件名なし"}</strong>
      <span className="order-field-hint">　{event.document_number}</span>
      {event.unavailable?.length ? <p>× 参加不可 {event.unavailable.length}人：{participantNames(event.unavailable)}</p> : null}
      <p>参加OK {event.ok.length}人：{event.ok.length ? participantNames(event.ok) : "なし"}</p>
      {event.pending?.length ? <p>運営確認待ち {event.pending.length}人：{participantNames(event.pending)}</p> : null}
      {event.changing.length > 0 ? <p>変更確認待ち {event.changing.length}人：{participantNames(event.changing)}</p> : null}
      {event.unanswered.length > 0 ? <p>未回答 {event.unanswered.length}人：{participantNames(event.unanswered)}</p> : null}
    </div>
  );
}

/** 依頼書の画面に出す、その依頼書（系列）の期間だけの小さい一覧。 */
export function VersionParticipationSummary({ versionId }: { versionId: string }) {
  const query = useQuery({
    queryKey: ["participation-calendar", "version", versionId],
    queryFn: () => getParticipationCalendar({ versionId }),
    refetchOnWindowFocus: true,
  });
  if (query.isLoading) return null;
  if (query.isError) return <p className="form-error">参加人数を読み込めませんでした。</p>;
  const days = query.data?.days ?? [];
  if (days.length === 0) return <p className="order-field-hint">日付の決まった稼働日がありません（日程を入力して確定した依頼書で表示されます）。</p>;
  return (
    <div className="order-draft-table participation-summary-table">
      <table className="data-table">
        <colgroup><col className="pc-summary-date-column" /><col /><col /><col /><col /><col /></colgroup>
        <thead>
          <tr><th scope="col">日付</th><th scope="col">参加OK</th><th scope="col">運営確認待ち</th><th scope="col">変更確認待ち</th><th scope="col">未回答</th><th scope="col">参加不可</th></tr>
        </thead>
        <tbody>
          {days.map((day) => {
            const event = day.events[0];
            return (
              <tr key={day.date}>
                <td className="pc-summary-date">{dayLabel(day.date)}</td>
                <td><ParticipationMembers label="参加OK" people={event.ok} /></td>
                <td><ParticipationMembers label="運営確認待ち" people={event.pending ?? []} /></td>
                <td><ParticipationMembers label="変更確認待ち" people={event.changing} /></td>
                <td><ParticipationMembers label="未回答" people={event.unanswered} /></td>
                <td><ParticipationMembers label="参加不可" people={event.unavailable ?? []} unavailable /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ParticipationMembers({ label, people, unavailable = false }: { label: string; people: ParticipationPerson[]; unavailable?: boolean }) {
  return <>
    <strong className="pc-summary-count">{unavailable ? "× " : ""}{people.length}人</strong>
    {people.length > 0 ? <ul className="pc-summary-names" aria-label={`${label}の稼働者`}>
      {people.map((person) => <li key={person.worker_id}><WorkerName name={person.name} isNewcomer={person.is_newcomer} isDirector={person.is_director} /></li>)}
    </ul> : null}
  </>;
}

function participantNames(list: ParticipationPerson[]) {
  return list.map((person, index) => <span key={person.worker_id}>{index ? "、" : ""}<WorkerName name={person.name} isNewcomer={person.is_newcomer} isDirector={person.is_director} /></span>);
}
