import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { SummaryCard } from "../components/SummaryCard";
import { ApiError, getWakeStatus, recordWakeContact } from "../lib/api/client";
import type { WakeContactResult, WakeNextAction, WakeStatusEntry, WakeStatusItem } from "../types/orderRequest";

function todayInTokyo(): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(new Date());
}

function timeInTokyo(value: string): string {
  return new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function entryLabel(entry: WakeStatusEntry): string {
  const time = entry.start_time || entry.end_time
    ? `${entry.start_time ?? ""}〜${entry.end_next_day ? "翌" : ""}${entry.end_time ?? ""} `
    : "";
  const place = entry.meeting_place ? `（集合：${entry.meeting_place}）` : entry.site_name ? `（${entry.site_name}）` : "";
  const changing = entry.status === "changing" ? " ※内容変更中" : "";
  return `${time}${entry.project_name || "案件名なし"}${place}${changing}`;
}

const CONTACT_OPTIONS: { value: WakeContactResult; label: string }[] = [
  { value: "line_sent", label: "LINEで連絡した" },
  { value: "confirmed_awake", label: "電話で起床を確認" },
  { value: "no_answer", label: "電話がつながらない" },
  { value: "site_notified", label: "現場へ連絡した" },
  { value: "absent", label: "欠勤" },
];

/** 今の段階で記録することが多い結果を初めに選んでおく（選び直せる） */
function suggestedResult(action: WakeNextAction): WakeContactResult | "" {
  if (action.step === "line") return "line_sent";
  if (action.step === "call") return "confirmed_awake";
  if (action.step === "site" || action.step === "started") return "site_notified";
  return "";
}

/** 今すぐ対応が必要な段階か（返事待ち・時刻前・報告あり・対応済みは含めない） */
function needsActionNow(action: WakeNextAction): boolean {
  return action.priority <= 3;
}

function actionTone(action: WakeNextAction): string {
  if (action.step === "started" || action.step === "site") return "wake-action is-urgent";
  if (action.step === "call") return "wake-action is-call";
  if (action.step === "line") return "wake-action is-line";
  if (action.step === "resolved") return "wake-action is-done";
  return "wake-action is-wait";
}

function ContactRecorder({ day, row }: { day: string; row: WakeStatusItem }) {
  const queryClient = useQueryClient();
  const [result, setResult] = useState<WakeContactResult | "">(suggestedResult(row.next_action));
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const save = useMutation({
    mutationFn: () => recordWakeContact({ day, worker_id: row.worker_id, result: result as WakeContactResult, note }),
    onSuccess: async () => {
      setNote("");
      setError("");
      setResult("");
      await queryClient.invalidateQueries({ queryKey: ["wake-status", day] });
    },
    onError: (caught) => setError(caught instanceof ApiError ? caught.message : "記録できませんでした。もう一度押してください。"),
  });
  return (
    <div className="wake-contact-recorder">
      <select aria-label={`${row.worker_name}さんへの連絡の結果`} value={result} disabled={save.isPending} onChange={(event) => setResult(event.target.value as WakeContactResult | "")}>
        <option value="">連絡の結果を選ぶ</option>
        {CONTACT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>
      <input aria-label={`${row.worker_name}さんへの連絡のメモ`} maxLength={500} placeholder="メモ（任意）" value={note} disabled={save.isPending} onChange={(event) => setNote(event.target.value)} />
      <button type="button" className="btn btn-line-blue btn-sm" disabled={!result || save.isPending} onClick={() => save.mutate()}>記録</button>
      {error ? <div className="form-error" role="alert">{error}</div> : null}
    </div>
  );
}

export function WakeStatusPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const day = searchParams.get("date") || todayInTokyo();

  const query = useQuery({
    queryKey: ["wake-status", day],
    queryFn: () => getWakeStatus(day),
    placeholderData: keepPreviousData,
    refetchInterval: 60_000,
  });

  const data = query.data;
  const pending = data ? data.total - data.reported : 0;
  const actionNow = data ? data.items.filter((item) => needsActionNow(item.next_action)).length : 0;

  return (
    <div className="page-stack">
      <PageHeader
        title="起床状況"
        description="その日に稼働予定がある人の、公式LINEでの起床報告を一覧にします。今連絡が必要な人ほど上に並びます（最初の開始の2時間前からLINE、1時間30分前から電話、1時間前から現場へ連絡）。予定は受諾済みの発注依頼書から作られ、テスト用の依頼書の予定は含みません。1分ごとに更新します。"
        eyebrow="当日運用"
      />

      <section className="summary-grid">
        <SummaryCard label="稼働予定の人数" value={data?.total ?? 0} accent="#0f766e" />
        <SummaryCard label="起床報告あり" value={data?.reported ?? 0} accent="#1d4ed8" />
        <SummaryCard label="未報告" value={pending} accent="#9f1239" />
        <SummaryCard label="今連絡が必要" value={actionNow} accent="#b45309" />
      </section>

      <FilterBar>
        <label>
          日付
          <input type="date" value={day} onChange={(event) => setSearchParams(event.target.value ? { date: event.target.value } : {})} />
        </label>
      </FilterBar>

      {query.isError ? (
        <ErrorState
          title="起床状況を読み込めませんでした"
          description={query.error instanceof ApiError ? query.error.message : "時間をおいて再度お試しください。"}
        />
      ) : (
        <div style={{ position: "relative" }}>
          {query.isFetching && !data ? <LoadingOverlay /> : null}
          <DataTable<WakeStatusItem>
            columns={[
              {
                key: "action",
                header: "今すること",
                render: (row) => row.next_action.label
                  ? <span className={actionTone(row.next_action)}>{row.next_action.label}</span>
                  : <span className="order-field-hint">—</span>,
              },
              {
                key: "status",
                header: "起床報告",
                render: (row) => row.wake_reported_at ? (
                  <span className="status-badge positive">
                    {timeInTokyo(row.wake_reported_at)} 報告{row.wake_late_received ? "（受信遅れ）" : ""}
                  </span>
                ) : (
                  <span className="status-badge attention">未報告</span>
                ),
              },
              {
                key: "worker",
                header: "稼働者・電話番号",
                render: (row) => (
                  <>
                    {row.worker_name}
                    <div>{row.phone ? <a className="wake-phone" href={`tel:${row.phone.replace(/[^0-9+]/g, "")}`}>{row.phone}</a> : <span className="order-field-hint">電話番号の登録なし</span>}</div>
                    {!row.line_linked ? <div className="order-field-hint">公式LINE未連携</div> : null}
                  </>
                ),
              },
              { key: "start", header: "最初の開始", render: (row) => row.first_start ?? "-" },
              {
                key: "entries",
                header: "予定",
                render: (row) => (
                  <>
                    {row.entries.map((entry) => <div key={entry.id}>{entryLabel(entry)}</div>)}
                    {row.overlap_warning ? <div className="form-error">時間が重なる予定があります。依頼書を確認してください。</div> : null}
                  </>
                ),
              },
              {
                key: "contacts",
                header: "連絡の記録",
                render: (row) => (
                  <div className="wake-contact-cell">
                    {row.contacts.map((contact) => (
                      <div key={contact.id} className="wake-contact-log">
                        {timeInTokyo(contact.created_at)} {contact.result_label}（{contact.actor_name}）{contact.note ? `：${contact.note}` : ""}
                      </div>
                    ))}
                    {!row.wake_reported_at ? <ContactRecorder key={`${row.worker_id}-${row.next_action.step}`} day={day} row={row} /> : null}
                  </div>
                ),
              },
            ]}
            rows={data?.items ?? []}
            getRowKey={(row) => row.worker_id}
            emptyTitle="この日の稼働予定はありません"
            emptyDescription="受諾済みの発注依頼書（日程入り）がある人だけが表示されます。"
          />
        </div>
      )}
    </div>
  );
}
