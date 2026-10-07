import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { Briefcase, CalendarDays, Sun, TrendingDown, TrendingUp, Users } from "lucide-react";

import {
  DEMO_CLIENT_SHARE,
  DEMO_EQUIPMENT,
  DEMO_FINANCE,
  DEMO_PROJECT_TREND,
  DEMO_STAFF_ORDERS,
  DEMO_TYPE_SHARE,
  DEMO_WORKER_TREND,
  FINANCE_COLORS,
  FINANCE_LABELS,
  axisTicks,
  demoMonthLabels,
  donutSegments,
  plotPoints,
  smoothLine,
  type DemoSlice,
  type FinanceKey,
} from "./dashboardPreviewDemo";

const CHART_WIDTH = 720;
const CHART_HEIGHT = 280;
const CHART_INSET = { left: 46, right: 12, top: 16, bottom: 28 };

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const gradientId = useId().replace(/:/g, "");
  const width = 240;
  const height = 72;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const points = plotPoints(values, width, height, { left: 0, right: 0, top: 8, bottom: 2 }, { min, max });
  const line = smoothLine(points);
  const last = points[points.length - 1];
  const first = points[0];
  const area = `${line} L ${last?.x ?? 0} ${height} L ${first?.x ?? 0} ${height} Z`;
  return (
    <svg className="apex-preview__spark" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
}

function TrendCard({
  label,
  value,
  delta,
  values,
  color,
  icon,
}: {
  label: string;
  value: string;
  delta: string;
  values: number[];
  color: string;
  icon: ReactNode;
}) {
  const positive = !delta.startsWith("-");
  return (
    <article className="apex-preview__card apex-preview__stat is-live">
      <div className="apex-preview__stat-top">
        <div>
          <p className="apex-preview__kpi-label">{label}</p>
          <p className="apex-preview__kpi-value">{value}</p>
          <p className={positive ? "apex-preview__delta is-up" : "apex-preview__delta is-down"}>
            {positive ? <TrendingUp size={14} aria-hidden="true" /> : <TrendingDown size={14} aria-hidden="true" />}
            {delta}
          </p>
        </div>
        <span className="apex-preview__stat-icon" style={{ color, background: `${color}1a` }}>{icon}</span>
      </div>
      <Sparkline values={values} color={color} />
    </article>
  );
}

function DayCard({
  title,
  workers,
  projects,
  icon,
  color,
}: {
  title: string;
  workers: number;
  projects: number;
  icon: ReactNode;
  color: string;
}) {
  return (
    <article className="apex-preview__card apex-preview__stat is-live">
      <div className="apex-preview__stat-top">
        <p className="apex-preview__kpi-label">{title}</p>
        <span className="apex-preview__stat-icon" style={{ color, background: `${color}1a` }}>{icon}</span>
      </div>
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

function FinanceChart({ values, color }: { values: readonly number[]; color: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const gradientId = useId().replace(/:/g, "");
  const labels = demoMonthLabels();
  const ticks = axisTicks(Math.max(...values));
  const scaleMax = ticks[ticks.length - 1] ?? 1;
  const points = plotPoints([...values], CHART_WIDTH, CHART_HEIGHT, CHART_INSET, { min: 0, max: scaleMax });
  const line = smoothLine(points);
  const first = points[0];
  const last = points[points.length - 1];
  const baseline = CHART_HEIGHT - CHART_INSET.bottom;
  const area = `${line} L ${last?.x ?? 0} ${baseline} L ${first?.x ?? 0} ${baseline} Z`;
  const active = hover == null ? null : points[hover];

  const move = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    const x = ((event.clientX - rect.left) / rect.width) * CHART_WIDTH;
    let nearest = 0;
    let distance = Number.POSITIVE_INFINITY;
    points.forEach((point, index) => {
      const gap = Math.abs(point.x - x);
      if (gap < distance) {
        distance = gap;
        nearest = index;
      }
    });
    setHover(nearest);
  };

  return (
    <div className="apex-preview__chart">
      <svg
        ref={svgRef}
        className="apex-preview__area"
        viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
        role="img"
        aria-label="月次推移。点を指すとその月の金額を表示します。"
        onMouseMove={move}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {ticks.map((tick) => {
          const y = CHART_INSET.top + (1 - tick / scaleMax) * (CHART_HEIGHT - CHART_INSET.top - CHART_INSET.bottom);
          return (
            <g key={tick}>
              <line className="apex-preview__grid" x1={CHART_INSET.left} x2={CHART_WIDTH - CHART_INSET.right} y1={y} y2={y} />
              <text className="apex-preview__axis" x={CHART_INSET.left - 8} y={y + 4} textAnchor="end">
                {tick.toLocaleString("ja-JP")}
              </text>
            </g>
          );
        })}
        <path className="apex-preview__area-fill" d={area} fill={`url(#${gradientId})`} />
        <path className="apex-preview__area-line apex-preview__draw" d={line} stroke={color} />
        {labels.map((label, index) => {
          const point = points[index];
          if (!point) return null;
          return (
            <text
              key={label}
              className={hover === index ? "apex-preview__axis is-active" : "apex-preview__axis"}
              x={point.x}
              y={CHART_HEIGHT - 8}
              textAnchor="middle"
            >
              {label.replace("月", "")}
            </text>
          );
        })}
        {active ? (
          <g>
            <line className="apex-preview__cursor" x1={active.x} x2={active.x} y1={CHART_INSET.top} y2={baseline} stroke={color} />
            <circle cx={active.x} cy={active.y} r="5" fill="#fff" stroke={color} strokeWidth="2.5" />
          </g>
        ) : null}
      </svg>
      {active ? (
        <div
          className={(active.y / CHART_HEIGHT) < 0.34 ? "apex-preview__tip is-below" : "apex-preview__tip"}
          style={{
            left: `${Math.min(Math.max(active.x / CHART_WIDTH, 0.12), 0.88) * 100}%`,
            top: `${(active.y / CHART_HEIGHT) * 100}%`,
          }}
        >
          <span>{labels[hover ?? 0]}</span>
          <strong>{active.value.toLocaleString("ja-JP")}万円</strong>
        </div>
      ) : null}
    </div>
  );
}

function Donut({ slices }: { slices: DemoSlice[] }) {
  const [active, setActive] = useState<number | null>(null);
  const radius = 46;
  const circumference = 2 * Math.PI * radius;
  const segments = donutSegments(slices, radius);
  const selected = active == null ? null : segments[active];
  return (
    <div className="apex-preview__donut-wrap">
      <div className="apex-preview__donut-stage">
        <svg className="apex-preview__donut" viewBox="0 0 140 140" role="img" aria-label="割合">
          <g transform="rotate(-90 70 70)">
            {segments.map((segment, index) => (
              <circle
                key={segment.label}
                cx="70"
                cy="70"
                r={radius}
                fill="none"
                stroke={segment.color}
                strokeWidth={active === index ? 18 : 14}
                strokeDasharray={`${Math.max(segment.length - 4, 0)} ${circumference}`}
                strokeDashoffset={-segment.offset}
                opacity={active == null || active === index ? 1 : 0.35}
                onMouseEnter={() => setActive(index)}
                onMouseLeave={() => setActive(null)}
              />
            ))}
          </g>
        </svg>
        <div className="apex-preview__donut-center">
          <strong>{selected ? `${selected.share}%` : "100%"}</strong>
          <span>{selected?.label ?? "合計"}</span>
        </div>
      </div>
      <ul className="apex-preview__legend">
        {segments.map((segment, index) => (
          <li key={segment.label}>
            <button
              type="button"
              className={active === index ? "is-active" : ""}
              onMouseEnter={() => setActive(index)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(index)}
              onBlur={() => setActive(null)}
            >
              <span className="apex-preview__swatch" style={{ background: segment.color }} />
              <span>{segment.label}</span>
              <strong>{segment.share}%</strong>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function GoalBar({
  label,
  current,
  target,
  unit,
  color,
}: {
  label: string;
  current: number;
  target: number;
  unit: string;
  color: string;
}) {
  const percent = Math.min(100, Math.round((current / target) * 100));
  const [grown, setGrown] = useState(0);
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setGrown(percent);
      return;
    }
    const frame = window.requestAnimationFrame(() => setGrown(percent));
    return () => window.cancelAnimationFrame(frame);
  }, [percent]);
  return (
    <div className="apex-preview__goal">
      <div className="apex-preview__goal-head">
        <span>{label}</span>
        <span>{percent}%</span>
      </div>
      <div className="apex-preview__bar" aria-hidden="true">
        <div className="apex-preview__bar-fill" style={{ width: `${grown}%`, background: color }} />
      </div>
      <p className="apex-preview__bar-meta">
        <span>{current.toLocaleString("ja-JP")}{unit}</span>
        <span>目標 {target.toLocaleString("ja-JP")}{unit}</span>
      </p>
    </div>
  );
}

function initials(name: string): string {
  return name.replace(/\s/g, "").slice(0, 1);
}


export function PreviewDemoBoard() {
  const [finance, setFinance] = useState<FinanceKey>("sales");
  const [share, setShare] = useState<"client" | "type">("client");
  const financeValues = DEMO_FINANCE[finance];
  const financeColor = FINANCE_COLORS[finance];

  return (
    <div className="apex-preview__demo">
      <p className="apex-preview__note">グラフとリストの数値はデモです。点や区分を指すと内訳が出ます。</p>
      <section className="apex-preview__demo-top" aria-label="概況">
        <TrendCard label="月間の案件数" value="48" delta="+12.5%" values={DEMO_PROJECT_TREND} color="#16a34a" icon={<Briefcase size={16} aria-hidden="true" />} />
        <TrendCard label="稼働者数" value="186" delta="+8.2%" values={DEMO_WORKER_TREND} color="#2563eb" icon={<Users size={16} aria-hidden="true" />} />
        <DayCard title="今日" workers={42} projects={11} color="#d97706" icon={<Sun size={16} aria-hidden="true" />} />
        <DayCard title="明日" workers={38} projects={9} color="#7c3aed" icon={<CalendarDays size={16} aria-hidden="true" />} />
      </section>
      <section className="apex-preview__demo-mid">
        <article className="apex-preview__card is-live">
          <div className="apex-preview__card-head">
            <div>
              <h2 className="apex-preview__section-title">売上・人件費・粗利益</h2>
              <p className="apex-preview__subtitle">今年の月次</p>
            </div>
            <div className="apex-preview__segment" role="tablist" aria-label="表示する金額">
              {(Object.keys(FINANCE_LABELS) as FinanceKey[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  className={finance === key ? "is-active" : ""}
                  aria-selected={finance === key}
                  onClick={() => setFinance(key)}
                >
                  {FINANCE_LABELS[key]}
                </button>
              ))}
            </div>
          </div>
          <FinanceChart key={finance} values={financeValues} color={financeColor} />
        </article>
        <div className="apex-preview__demo-side">
          <article className="apex-preview__card is-live">
            <div className="apex-preview__card-head">
              <div>
                <h2 className="apex-preview__section-title">割合</h2>
                <p className="apex-preview__subtitle">区分を指すと内訳を表示します</p>
              </div>
              <div className="apex-preview__segment" role="tablist" aria-label="割合の種類">
                <button type="button" role="tab" className={share === "client" ? "is-active" : ""} aria-selected={share === "client"} onClick={() => setShare("client")}>
                  案件元
                </button>
                <button type="button" role="tab" className={share === "type" ? "is-active" : ""} aria-selected={share === "type"} onClick={() => setShare("type")}>
                  種別
                </button>
              </div>
            </div>
            <Donut key={share} slices={share === "client" ? DEMO_CLIENT_SHARE : DEMO_TYPE_SHARE} />
          </article>
          <article className="apex-preview__card is-live">
            <h2 className="apex-preview__section-title">目標</h2>
            <p className="apex-preview__subtitle">月間の到達状況</p>
            <GoalBar label="月間案件数" current={48} target={55} unit="件" color="#16a34a" />
            <GoalBar label="新規契約（稼働者）" current={12} target={20} unit="人" color="#2563eb" />
          </article>
        </div>
      </section>
      <section className="apex-preview__demo-bottom">
        <article className="apex-preview__card is-live">
          <h2 className="apex-preview__section-title">スタッフの発注依頼書</h2>
          <p className="apex-preview__subtitle">新規に作成した件数のデモです</p>
          <div className="apex-preview__table-scroll">
            <table className="apex-preview__table apex-preview__table--fit">
              <thead>
                <tr>
                  <th>VANZAIスタッフ</th>
                  <th className="is-num">作成数</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_STAFF_ORDERS.map((row) => (
                  <tr key={row.name}>
                    <td>
                      <span className="apex-preview__person">
                        <span className="apex-preview__avatar" style={{ background: row.color }}>{initials(row.name)}</span>
                        {row.name}
                      </span>
                    </td>
                    <td className="is-num">{row.count}件</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>
        <article className="apex-preview__card is-live">
          <h2 className="apex-preview__section-title">備品リスト</h2>
          <p className="apex-preview__subtitle">備品マスタは未接続のため、見本の行です</p>
          <div className="apex-preview__table-scroll">
            <table className="apex-preview__table apex-preview__table--fit">
              <thead>
                <tr>
                  <th>備品</th>
                  <th className="is-num">数量</th>
                  <th>状態</th>
                </tr>
              </thead>
              <tbody>
                {DEMO_EQUIPMENT.map((row) => (
                  <tr key={row.name}>
                    <td>{row.name}</td>
                    <td className="is-num">{row.stock}</td>
                    <td>
                      <span className={`apex-preview__pill ${row.status === "在庫" ? "is-positive" : row.status === "貸出中" ? "is-warning" : "is-info"}`}>{row.status}</span>
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
