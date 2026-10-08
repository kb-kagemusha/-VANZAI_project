import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError, getActuals } from "../lib/api/client";
import { currentMonthInput, formatCurrency, formatDate, formatStatus, minutesToHours, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";

export function ActualsPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const periodKey = toPeriodKey(monthValue);
  const { from, to } = periodKeyToDateRange(periodKey);

  const actualsQuery = useQuery({
    queryKey: ["staff-actuals", periodKey],
    queryFn: () =>
      getActuals({
        work_date_from: from,
        work_date_to: to,
        sort_by: "work_date",
        sort_order: "desc",
        limit: 100,
      }),
  });

  if (actualsQuery.isLoading) {
    return <div className="panel-card">実績を読み込み中...</div>;
  }

  if (actualsQuery.isError) {
    return (
      <div className="panel-card">
        <h2>実績を取得できませんでした</h2>
        <p>{actualsQuery.error instanceof ApiError ? actualsQuery.error.message : "API 疎通を確認してください。"}</p>
      </div>
    );
  }

  const actuals = actualsQuery.data?.items ?? [];
  const totalMinutes = actuals.reduce((sum, row) => sum + row.calc_minutes_billable, 0);
  const totalOutsource = actuals.reduce((sum, row) => sum + Number(row.applied_price_outsource), 0);

  return (
    <div className="page-stack">
      <section className="hero-panel tide">
        <p className="panel-label">月次実績</p>
        <div className="month-toolbar">
          <h2>{monthValue}</h2>
          <input type="month" value={monthValue} onChange={(event) => setMonthValue(event.target.value)} />
        </div>
        <p>自分のスタッフ権限で実績を参照します。</p>
      </section>

      <section className="panel-grid three-up">
        <article className="panel-card accent-sand">
          <p className="panel-label">対象件数</p>
          <strong>{actuals.length} 件</strong>
        </article>
        <article className="panel-card accent-green">
          <p className="panel-label">稼働時間</p>
          <strong>{minutesToHours(totalMinutes)}</strong>
        </article>
        <article className="panel-card accent-blue">
          <p className="panel-label">支払見込</p>
          <strong>{formatCurrency(totalOutsource)}</strong>
        </article>
      </section>

      <section className="list-section">
        <div className="section-heading">
          <h2>実績明細</h2>
          <span>{actuals.length} 行</span>
        </div>

        {actuals.length === 0 ? (
          <div className="panel-card empty-card">対象月の実績はありません。</div>
        ) : (
          actuals.map((actual) => (
            <article key={actual.id} className="actual-card">
              <div className="assignment-header">
                <div>
                  <p className="panel-label">{actual.project_name}</p>
                  <h3>{formatDate(actual.work_date)}</h3>
                </div>
                <span className={`status-pill status-${actual.status}`}>{formatStatus(actual.status)}</span>
              </div>
              <dl className="detail-grid">
                <div>
                  <dt>役割</dt>
                  <dd>{actual.role_name}</dd>
                </div>
                <div>
                  <dt>計上時間</dt>
                  <dd>{minutesToHours(actual.calc_minutes_billable)}</dd>
                </div>
                <div>
                  <dt>外注単価</dt>
                  <dd>{formatCurrency(actual.applied_price_outsource)}</dd>
                </div>
                <div>
                  <dt>取込元</dt>
                  <dd>{actual.import_batch_file_name}</dd>
                </div>
              </dl>
              {actual.review_reason ? <p className="note-banner">確認理由: {actual.review_reason}</p> : null}
            </article>
          ))
        )}
      </section>
    </div>
  );
}