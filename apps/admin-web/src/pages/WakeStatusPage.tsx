import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { SummaryCard } from "../components/SummaryCard";
import { ApiError, getWakeStatus } from "../lib/api/client";
import type { WakeStatusEntry, WakeStatusItem } from "../types/orderRequest";

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

  return (
    <div className="page-stack">
      <PageHeader
        title="起床状況"
        description="その日に稼働予定がある人の、公式LINEでの起床報告を一覧にします。予定は受諾済みの発注依頼書から作られます。テスト用の依頼書の予定は含みません。1分ごとに更新します。"
        eyebrow="当日運用"
      />

      <section className="summary-grid">
        <SummaryCard label="稼働予定の人数" value={data?.total ?? 0} accent="#0f766e" />
        <SummaryCard label="起床報告あり" value={data?.reported ?? 0} accent="#1d4ed8" />
        <SummaryCard label="未報告" value={pending} accent="#9f1239" />
      </section>

      <FilterBar>
        <label>
          日付
          <input type="date" value={day} onChange={(event) => setSearchParams(event.target.value ? { date: event.target.value } : {})} />
        </label>
        <button type="button" className="btn btn-ghost" onClick={() => setSearchParams({})}>今日</button>
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
                header: "稼働者",
                render: (row) => (
                  <>
                    {row.worker_name}
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
