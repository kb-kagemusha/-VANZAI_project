/**
 * 稼働者向けのWeb確認画面（統合計画 ②、Web確認画面計画 v0.2、DEC-084）。LIFF（PublicLineWorkerPage）の中で表示する。
 * ホーム：確認が必要な依頼・その月の報酬見込みと稼働日数・月間／直近7日の予定。受託済みの依頼書の一覧。
 * 閲覧専用（受諾・辞退はトークのボタン、日付を選べる依頼書は日付を選ぶ画面で行う）。
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { MonthCalendar, shiftMonth } from "./MonthCalendar";
import {
  createPortalPdfLink,
  getPortalHome,
  getPortalOrders,
  type PortalChange,
  type PortalConfirmation,
  type PortalDay,
  type PortalEntry,
  type PortalEstimate,
  type PortalHome,
  type PortalOrders,
} from "../lib/lineWorkerPortalApi";
import "../styles/lineWorkerPortal.css";

const WEEKDAY = ["日", "月", "火", "水", "木", "金", "土"];

export function dayLabel(day: string): string {
  const [, m, d] = day.split("-").map(Number);
  const weekday = WEEKDAY[new Date(`${day}T00:00:00+09:00`).getDay()];
  return `${m}月${d}日（${weekday}）`;
}

function periodLabel(first: string | null, last: string | null): string {
  if (!first) return "";
  return !last || first === last ? dayLabel(first) : `${dayLabel(first)}〜${dayLabel(last)}`;
}

function yen(value: string): string {
  return `${Number(value).toLocaleString("ja-JP")}円`;
}

function timeLabel(entry: PortalEntry): string {
  if (!entry.start_time && !entry.end_time) return "時刻未定";
  return `${entry.start_time ?? ""}〜${entry.end_next_day ? "翌" : ""}${entry.end_time ?? ""}`;
}

function firstLine(value: string): string {
  return value.split("\n").map((line) => line.trim()).find(Boolean) ?? "";
}

function openUrl(url: string) {
  const liff = (window as Window & { liff?: { openWindow?: (p: { url: string; external?: boolean }) => void; isInClient?: () => boolean } }).liff;
  if (liff?.openWindow && (liff.isInClient?.() ?? false)) {
    liff.openWindow({ url, external: false });
    return;
  }
  window.location.href = url;
}

function messageOf(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "読み込めませんでした。";
}

type PdfAction = { onPdf: (deliveryId: string) => void; pdfBusy: string };

/** 「内容変更の確認待ち」で、何が起きていて本人が何をすればよいか（0.51.13） */
function ChangeNotice({ change, onPdf, pdfBusy }: { change: PortalChange | null | undefined } & PdfAction) {
  if (change?.state === "sent" && change.delivery_id) {
    const deliveryId = change.delivery_id;
    return (
      <div className="lwp-change">
        <p className="lwp-change-title">◆ 依頼の内容が変わりました</p>
        <p className="lwp-change-text">新しい依頼書を確認して、返事をしてください。返事をするまでは、ここに出ている前の内容のままです。</p>
        <div className="lwp-actions">
          {change.pdf_available ? (
            <button type="button" className="lw-secondary" disabled={pdfBusy === deliveryId} onClick={() => onPdf(deliveryId)}>
              {pdfBusy === deliveryId ? "開いています…" : "新しい依頼書（PDF）を開く"}
            </button>
          ) : null}
          {change.can_pick ? (
            <a className="lw-primary lwp-link-button" href={`?m=pick&d=${encodeURIComponent(deliveryId)}`}>日付を選んで返事する</a>
          ) : (
            <p className="lw-note">返事は、公式LINEのトークに届いた新しい依頼のメッセージの「受諾」「辞退」のボタンで行えます。</p>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="lwp-change">
      <p className="lwp-change-title">◆ 運営が依頼の内容を変更しています</p>
      <p className="lwp-change-text">新しい依頼書がLINEに届いたら、内容を確認して返事をしてください。それまでは、ここに出ている前の内容のままです。</p>
    </div>
  );
}

function EntryCard({ entry, onPdf, pdfBusy }: { entry: PortalEntry } & PdfAction) {
  return (
    <div className={`lwp-entry${entry.changing ? " is-changing" : ""}`}>
      {entry.is_test ? <p className="lw-test">【テスト】正式な発注ではありません</p> : null}
      <p className="lwp-entry-time">{timeLabel(entry)}</p>
      <p className="lwp-entry-title">{firstLine(entry.project_name) || "（案件名なし）"}</p>
      {entry.site_name ? <p className="lw-meta">稼働場所：{firstLine(entry.site_name)}</p> : null}
      {entry.meeting_place ? <p className="lw-meta">集合場所：{entry.meeting_place}</p> : null}
      {entry.changing ? <ChangeNotice change={entry.change} onPdf={onPdf} pdfBusy={pdfBusy} /> : null}
    </div>
  );
}

function DayBlock({ day, onPdf, pdfBusy }: { day: PortalDay } & PdfAction) {
  return (
    <div className="lwp-day-block">
      <h3>{dayLabel(day.date)}</h3>
      {day.entries.map((entry) => <EntryCard key={entry.id} entry={entry} onPdf={onPdf} pdfBusy={pdfBusy} />)}
    </div>
  );
}

function usePdfOpener(token: string) {
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const open = useCallback(async (deliveryId: string) => {
    if (busy) return;
    setBusy(deliveryId);
    setError("");
    try {
      const link = await createPortalPdfLink(token, deliveryId);
      openUrl(link.url);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setBusy("");
    }
  }, [busy, token]);
  return { open, busy, error };
}

function ConfirmationCard({ item, onPdf, pdfBusy }: { item: PortalConfirmation; onPdf: (id: string) => void; pdfBusy: string }) {
  return (
    <div className="lwp-confirm-item">
      {item.is_test ? <p className="lw-test">【テスト】正式な発注ではありません</p> : null}
      <p className={`lwp-badge ${item.kind === "changing" ? "is-changing" : "is-unanswered"}`}>
        {item.kind === "changing" ? "◆ 内容が変わりました（確認待ち）" : "● まだ返事をしていない依頼"}
      </p>
      <p className="lwp-entry-title">{firstLine(item.project_name) || "案件"}</p>
      <p className="lw-meta">発注依頼書 {item.document_number}（版{item.version_no}）</p>
      {item.first_date ? <p className="lw-meta">日程：{periodLabel(item.first_date, item.last_date)}（{item.offered_days}日）</p> : null}
      {item.follow_up_due_on ? <p className="lw-meta">返事の期限：{dayLabel(item.follow_up_due_on)}</p> : null}
      <div className="lwp-actions">
        {item.pdf_available ? (
          <button type="button" className="lw-secondary" disabled={pdfBusy === item.delivery_id} onClick={() => onPdf(item.delivery_id)}>
            {pdfBusy === item.delivery_id ? "開いています…" : "依頼書（PDF）を開く"}
          </button>
        ) : null}
        {item.can_pick ? (
          <a className="lw-primary lwp-link-button" href={`?m=pick&d=${encodeURIComponent(item.delivery_id)}`}>日付を選んで返事する</a>
        ) : (
          <p className="lw-note">返事は、公式LINEのトークに届いた依頼のメッセージの「受諾」「辞退」のボタンで行えます。</p>
        )}
      </div>
    </div>
  );
}

function amountLabel(estimate: Omit<PortalEstimate, "test">): string {
  return estimate.amount !== null ? `約${yen(estimate.amount)}` : estimate.work_days > 0 ? "算出できません" : "0円";
}

function EstimateCard({ home }: { home: PortalHome }) {
  const formal = home.estimate;
  const test = formal.test && formal.test.work_days > 0 ? formal.test : null;
  // 正式の予定がなくテストだけのときは、テストの分を大きく出す（【テスト】と明記。正式の合計には混ぜない）
  const testOnly = !!test && formal.work_days === 0;
  const estimate = testOnly && test ? test : formal;
  const [year, mon] = home.month.split("-").map(Number);
  const excluded = estimate.excluded_hourly + estimate.excluded_unknown;
  return (
    <div className="lwp-summary">
      {testOnly ? <p className="lw-test lwp-summary-test">【テスト】テストの依頼書の予定から出した見込みです（正式な発注ではありません）</p> : null}
      <div className="lwp-summary-item">
        <span className="lwp-summary-label">{year}年{mon}月の報酬見込み</span>
        <strong className="lwp-summary-value">{amountLabel(estimate)}</strong>
      </div>
      <div className="lwp-summary-item">
        <span className="lwp-summary-label">稼働日数</span>
        <strong className="lwp-summary-value">{estimate.work_days}日</strong>
      </div>
      {test && !testOnly ? (
        <p className="lwp-summary-testrow"><span className="lwp-test-chip">テスト</span>テストの依頼書の分：{amountLabel(test)}・{test.work_days}日（上の金額・日数には含みません）</p>
      ) : null}
      <p className="lw-note lwp-summary-note">
        受諾した予定と依頼書の日給から出した目安です。インセンティブは含みません。実際の支払額とは変わる場合があります。
        {estimate.separate_cost ? "交通費・昼食代を別に精算する日の分は含みません。" : ""}
        {excluded > 0 ? `時給の仕事など、${excluded}件は金額に入れていません。` : ""}
      </p>
    </div>
  );
}

function HomeView({ token, onOrders }: { token: string; onOrders: () => void }) {
  const [month, setMonth] = useState("");
  const [home, setHome] = useState<PortalHome | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"month" | "week">("month");
  const [selectedDay, setSelectedDay] = useState("");
  const pdf = usePdfOpener(token);

  const load = useCallback(async (target?: string) => {
    setLoading(true);
    setError("");
    try {
      const loaded = await getPortalHome(token, target);
      setHome(loaded);
      setMonth(loaded.month);
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    // LINEの画面に戻ってきたときに最新にする（古い値を最新として見せない）
    const onVisible = () => { if (document.visibilityState === "visible") void load(month || undefined); };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [load, month]);

  const byDate = useMemo(() => new Map((home?.month_days ?? []).map((day) => [day.date, day])), [home]);
  const selected = selectedDay ? byDate.get(selectedDay) : undefined;

  if (!home) {
    return loading ? <p className="lw-status">読み込んでいます…</p> : (
      <div className="lw-card lw-error">
        <p>{error || "読み込めませんでした。"}</p>
        <button type="button" className="lw-secondary lwp-retry" onClick={() => void load(month || undefined)}>もう一度読み込む</button>
      </div>
    );
  }

  return (
    <>
      <div className="lw-card">
        <p className="lw-eyebrow">{home.worker_name}さんの予定</p>
        {home.confirmations.length > 0 ? (
          <a className="lwp-alert" href="#lwp-confirmations">確認が必要な依頼が {home.confirmations.length}件 あります</a>
        ) : (
          <p className="lw-note lwp-no-confirm">確認が必要な依頼はありません。</p>
        )}
        <EstimateCard home={home} />
        {error ? <p className="lw-footer-error">{error}</p> : null}
      </div>

      <div className="lw-card">
        <div className="lwp-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === "month"} className={tab === "month" ? "is-active" : ""} onClick={() => setTab("month")}>月間</button>
          <button type="button" role="tab" aria-selected={tab === "week"} className={tab === "week" ? "is-active" : ""} onClick={() => setTab("week")}>直近7日</button>
        </div>
        {tab === "month" ? (
          <>
            <MonthCalendar
              month={month}
              onMonthChange={(next) => { setSelectedDay(""); setMonth(next); void load(next); }}
              minMonth={shiftMonth(home.today.slice(0, 7), -12)}
              maxMonth={shiftMonth(home.today.slice(0, 7), 12)}
              renderDay={(day) => {
                const info = byDate.get(day);
                const changing = info?.entries.some((e) => e.changing);
                const classes = ["lwp-cal-day", info ? "has-work" : "", changing ? "is-changing" : "", day === home.today ? "is-today" : "", day === selectedDay ? "is-selected" : ""].filter(Boolean).join(" ");
                return (
                  <button type="button" className={classes} disabled={!info} aria-pressed={day === selectedDay} aria-label={`${day === home.today ? "今日 " : ""}${dayLabel(day)}${info ? " 仕事あり" : ""}`} aria-current={day === home.today ? "date" : undefined} onClick={() => setSelectedDay(day === selectedDay ? "" : day)}>
                    <span className="lw-day-num">{Number(day.slice(8))}</span>
                    {info ? <span className="lwp-dot" aria-hidden="true">{changing ? "◆" : "●"}</span> : null}
                  </button>
                );
              }}
            />
            <p className="lw-legend"><span className="lwp-legend-mark">●</span>仕事がある日 <span className="lwp-legend-mark is-changing">◆</span>内容が変わった（確認待ち） <span className="lwp-legend-today" aria-hidden="true" />今日</p>
            {loading ? <p className="lw-note">読み込んでいます…</p> : null}
            {pdf.error ? <p className="lw-footer-error">{pdf.error}</p> : null}
            {home.month_days.some((d) => d.entries.some((e) => e.changing)) ? (
              <p className="lwp-change-hint">◆の日は、依頼の内容が変わり、あなたの確認を待っている日です。日付を押すと、することが表示されます。</p>
            ) : null}
            {selected ? <DayBlock day={selected} onPdf={(id) => void pdf.open(id)} pdfBusy={pdf.busy} /> : home.month_days.length > 0
              ? <p className="lw-note">●の日を押すと、その日の仕事を表示します。</p>
              : <p className="lw-note">この月の予定はありません（受諾した依頼だけが表示されます）。</p>}
          </>
        ) : (
          <>
            <p className="lwp-week-range">{dayLabel(home.week.from)}〜{dayLabel(home.week.to)}</p>
            {home.week.days.length > 0
              ? home.week.days.map((day) => <DayBlock key={day.date} day={day} onPdf={(id) => void pdf.open(id)} pdfBusy={pdf.busy} />)
              : <p className="lw-note">この7日間の予定はありません（受諾した依頼だけが表示されます）。</p>}
          </>
        )}
      </div>

      {home.confirmations.length > 0 ? (
        <div className="lw-card" id="lwp-confirmations">
          <h2>確認が必要な依頼（{home.confirmations.length}件）</h2>
          {pdf.error ? <p className="lw-footer-error">{pdf.error}</p> : null}
          {home.confirmations.map((item) => <ConfirmationCard key={item.delivery_id} item={item} onPdf={(id) => void pdf.open(id)} pdfBusy={pdf.busy} />)}
        </div>
      ) : null}

      {home.orders_enabled ? (
        <div className="lw-card">
          <button type="button" className="lw-secondary" onClick={onOrders}>受託済みの発注依頼書を見る</button>
        </div>
      ) : null}
      <p className="lw-note lwp-fetched">最終更新：{new Date(home.fetched_at).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
    </>
  );
}

function OrdersView({ token, onHome, homeEnabled }: { token: string; onHome: () => void; homeEnabled: boolean }) {
  const [data, setData] = useState<PortalOrders | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const pdf = usePdfOpener(token);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getPortalOrders(token));
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setLoading(false);
    }
  }, [token]);
  useEffect(() => { void load(); }, [load]);

  if (!data) {
    return loading ? <p className="lw-status">読み込んでいます…</p> : (
      <div className="lw-card lw-error">
        <p>{error || "読み込めませんでした。"}</p>
        <button type="button" className="lw-secondary lwp-retry" onClick={() => void load()}>もう一度読み込む</button>
      </div>
    );
  }
  return (
    <>
      <div className="lw-card">
        <h1>受託済みの発注依頼書</h1>
        <p className="lw-note">今月（{dayLabel(data.since)}）以降に予定がある依頼書です。</p>
        {pdf.error ? <p className="lw-footer-error">{pdf.error}</p> : null}
      </div>
      {data.items.length === 0 ? <div className="lw-card"><p className="lw-note">受託済みの依頼書はありません。</p></div> : null}
      {data.items.map((item) => (
        <div key={item.delivery_id} className="lw-card">
          {item.is_test ? <p className="lw-test">【テスト】正式な発注ではありません</p> : null}
          <p className="lw-eyebrow">発注依頼書 {item.document_number}（版{item.version_no}）</p>
          <p className="lwp-entry-title">{firstLine(item.project_name) || "案件"}</p>
          {item.site_name ? <p className="lw-meta">稼働場所：{firstLine(item.site_name)}</p> : null}
          <p className="lw-meta">日程：{periodLabel(item.first_date, item.last_date)}（{item.work_days}日{item.upcoming_days < item.work_days ? `、これから${item.upcoming_days}日` : ""}）</p>
          {item.changing ? <ChangeNotice change={item.change} onPdf={(id) => void pdf.open(id)} pdfBusy={pdf.busy} /> : null}
          <div className="lwp-actions">
            {item.pdf_available ? (
              <button type="button" className="lw-secondary" disabled={pdf.busy === item.delivery_id} onClick={() => void pdf.open(item.delivery_id)}>
                {pdf.busy === item.delivery_id ? "開いています…" : "依頼書（PDF）を開く"}
              </button>
            ) : <p className="lw-note">この依頼書は今は開けません。運営へご確認ください。</p>}
            {item.newer_delivery_id && !item.change ? (
              <button type="button" className="lw-secondary" disabled={pdf.busy === item.newer_delivery_id} onClick={() => void pdf.open(item.newer_delivery_id!)}>新しい依頼書（PDF）を開く</button>
            ) : null}
          </div>
        </div>
      ))}
      {homeEnabled ? <div className="lw-card"><button type="button" className="lw-secondary" onClick={onHome}>予定の画面へ</button></div> : null}
    </>
  );
}

export function LineWorkerPortal({ token, initial, features }: { token: string; initial: "home" | "orders"; features: string[] }) {
  const [view, setView] = useState<"home" | "orders">(initial);
  const homeEnabled = features.includes("web_home");
  useEffect(() => { window.scrollTo(0, 0); }, [view]);
  return view === "orders"
    ? <OrdersView token={token} homeEnabled={homeEnabled} onHome={() => setView("home")} />
    : <HomeView token={token} onOrders={() => setView("orders")} />;
}
