import { useState } from "react";

import {
  DEMO_CLIENT_SHARE,
  DEMO_EQUIPMENT,
  DEMO_FINANCE,
  DEMO_PROJECT_TREND,
  DEMO_STAFF_ORDERS,
  DEMO_TYPE_SHARE,
  DEMO_WORKER_TREND,
  FINANCE_LABELS,
  areaPath,
  demoMonthLabels,
  donutSegments,
  linePoints,
  type FinanceKey,
} from "./dashboardPreviewDemo";

function Sparkline({ values }: { values: number[] }) {
  const width = 128;
  const height = 40;
  return (
    <svg className="apex-preview__spark" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={linePoints(values, width, height, 4)} />
    </svg>
  );
}

function TrendCard({
  label,
  value,
  delta,
  values,
}: {
  label: string;
  value: string;
  delta: string;
  values: number[];
}) {
  const positive = !delta.startsWith("-");
  return (
    <article className="apex-preview__card apex-preview__trend-card">
      <p className="apex-preview__kpi-label">{label}</p>
      <p className="apex-preview__kpi-value">{value}</p>
      <p className={positive ? "apex-preview__delta is-up" : "apex-preview__delta is-down"}>{delta}</p>
      <Sparkline values={values} />
    </article>
  );
}

function DayCard({ title, workers, projects }: { title: string; workers: number; projects: number }) {
  return (
    <article className="apex-preview__card">
      <p className="apex-preview__kpi-label">{title}</p>
      <div className="apex-preview__day-grid">
        <div>
          <p className="apex-preview__day-value">{workers}</p>
          <p className="apex-preview__day-caption">稼働者数</p>
        </div>
        <div>
          <p className="apex-preview__day-value">{projects}</p>
          <p className="apex-preview__day-caption">遂行案件数</p>
        </div>
      </div>
    </article>
  );
}

function FinanceChart({ values }: { values: readonly number[] }) {
  const width = 640;
  const height = 220;
  const labels = demoMonthLabels();
  return (
    <svg className="apex-preview__area" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="月次推移">
      <path className="apex-preview__area-fill" d={areaPath([...values], width, height, 16)} />
      <polyline className="apex-preview__area-line" points={linePoints([...values], width, height, 16)} />
      {labels.map((label, index) => (
        <text key={label} x={16 + (index / (labels.length - 1)) * (width - 32)} y={height - 2} textAnchor="middle">
          {label.replace("月", "")}
        </text>
      ))}
    </svg>
  );
}

function Donut({ slices }: { slices: typeof DEMO_CLIENT_SHARE }) {
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const segments = donutSegments(slices, radius);
  return (
    <div className="apex-preview__donut-wrap">
      <svg className="apex-preview__donut" viewBox="0 0 120 120" role="img" aria-label="割合">
        <g transform="rotate(-90 60 60)">
          {segments.map((segment) => (
            <circle
              key={segment.label}
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth="14"
              strokeDasharray={`${segment.length} ${circumference - segment.length}`}
              strokeDashoffset={-segment.offset}
            />
          ))}
        </g>
      </svg>
      <ul className="apex-preview__legend">
        {segments.map((segment) => (
          <li key={segment.label}>
            <span className="apex-preview__swatch" style={{ background: segment.color }} />
            {segment.label}
            <strong>{segment.share}%</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GoalBar({ label, current, target, unit }: { label: string; current: number; target: number; unit: string }) {
  const percent = Math.min(100, Math.round((current / target) * 100));
  return (
    <div className="apex-preview__goal">
      <div className="apex-preview__goal-head">
        <span>{label}</span>
        <span>{percent}%</span>
      </div>
      <div className="apex-preview__bar" aria-hidden="true">
        <div className="apex-preview__bar-fill" style={{ width: `${percent}%` }} />
      </div>
      <p className="apex-preview__bar-meta">
        <span>{current.toLocaleString("ja-JP")} / 目標 {target.toLocaleString("ja-JP")}{unit}</span>
      </p>
    </div>
  );
}

export function PreviewDemoBoard() {
  const [finance, setFinance] = useState<FinanceKey>("sales");
  const [share, setShare] = useState<"client" | "type">("client");
  const financeValues = DEMO_FINANCE[finance];
  const latest = financeValues[financeValues.length - 1] ?? 0;

  return (
    <div className="apex-preview__demo">
      <p className="apex-preview__note">グラフとリストの数値はデモです。実データの接続はまだありません。</p>
      <section className="apex-preview__demo-top" aria-label="概況">
        <TrendCard label="月間の案件数" value="48" delta="+12.5%" values={DEMO_PROJECT_TREND} />
        <TrendCard label="稼働者数" value="186" delta="+8.2%" values={DEMO_WORKER_TREND} />
        <DayCard title="今日" workers={42} projects={11} />
        <DayCard title="明日" workers={38} projects={9} />
      </section>
      <section className="apex-preview__demo-mid">
        <article className="apex-preview__card">
          <div className="apex-preview__card-head">
            <div>
              <h2 className="apex-preview__section-title">売上・人件費・粗利益</h2>
              <p className="apex-preview__kpi-value">{latest.toLocaleString("ja-JP")}万円</p>
            </div>
            <div className="apex-preview__switch" role="group" aria-label="表示する金額">
              {(Object.keys(FINANCE_LABELS) as FinanceKey[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  className={finance === key ? "is-active" : ""}
                  aria-pressed={finance === key}
                  onClick={() => setFinance(key)}
                >
                  {FINANCE_LABELS[key]}
                </button>
              ))}
            </div>
          </div>
          <FinanceChart values={financeValues} />
        </article>
        <div className="apex-preview__demo-side">
          <article className="apex-preview__card">
            <div className="apex-preview__card-head">
              <h2 className="apex-preview__section-title">割合</h2>
              <div className="apex-preview__switch" role="group" aria-label="割合の種類">
                <button type="button" className={share === "client" ? "is-active" : ""} aria-pressed={share === "client"} onClick={() => setShare("client")}>
                  案件元
                </button>
                <button type="button" className={share === "type" ? "is-active" : ""} aria-pressed={share === "type"} onClick={() => setShare("type")}>
                  種別
                </button>
              </div>
            </div>
            <Donut slices={share === "client" ? DEMO_CLIENT_SHARE : DEMO_TYPE_SHARE} />
          </article>
          <article className="apex-preview__card">
            <h2 className="apex-preview__section-title">目標</h2>
            <GoalBar label="月間案件数" current={48} target={55} unit="件" />
            <GoalBar label="新規契約（稼働者）" current={12} target={20} unit="人" />
          </article>
        </div>
      </section>
      <section className="apex-preview__demo-bottom">
        <article className="apex-preview__card">
          <h2 className="apex-preview__section-title">スタッフの発注依頼書</h2>
          <p className="apex-preview__note">新規に作成した件数のデモです。</p>
          <div className="apex-preview__table-scroll">
            <table className="apex-preview__table apex-preview__table--fit">
              <thead>
                <tr>
                  <th>VANZAIスタッフ</th>
                  <th>作成数</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_STAFF_ORDERS.map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    <td>{row.count}件</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
        <article className="apex-preview__card">
          <h2 className="apex-preview__section-title">備品リスト</h2>
          <p className="apex-preview__note">備品マスタは未接続のため、見本の行です。</p>
          <div className="apex-preview__table-scroll">
            <table className="apex-preview__table apex-preview__table--fit">
              <thead>
                <tr>
                  <th>備品</th>
                  <th>数量</th>
                  <th>状態</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_EQUIPMENT.map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    <td>{row.stock}</td>
                    <td>
                      <span className={`apex-preview__pill ${row.status === "在庫" ? "is-positive" : "is-warning"}`}>{row.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
      </section>
    </div>
  );
}
