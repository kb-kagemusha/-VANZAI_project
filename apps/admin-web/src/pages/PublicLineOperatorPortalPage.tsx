import { useCallback, useEffect, useMemo, useState } from "react";
import { getOperatorLineEntry, operatorPortalRequest } from "../lib/api/client";
import { operatorMode } from "./PublicLineOperatorEntry";
import "../styles/lineOperator.css";

type Me = { name: string; phone: string | null; permissions: { wake: boolean; availability: boolean; orders: boolean } };
type Entry = { project_name: string; site_name: string; start_time: string | null; end_time: string | null; end_next_day: boolean; status: string; is_test?: boolean };
type Handler = { actor_name: string; at: string; is_me: boolean } | null;
type WakeRow = {
  worker_id: string; worker_name: string; first_start: string | null; wake_reported_at: string | null; entries: Entry[];
  next_action: { step: string; label: string; priority: number }; handler: Handler;
  last_result: { label: string; actor_name: string; at: string } | null; is_test?: boolean;
};
type Wake = { date: string; is_today: boolean; total: number; reported: number; items: WakeRow[] };
type Person = { worker_id: string; name: string };
type Event = { project_name: string; site_name: string; version_id: string; document_number: string; is_test?: boolean; ok: Person[]; changing: Person[]; unanswered: Person[]; unavailable: Person[] };
type Calendar = { kind: string; days?: { date: string; events: Event[] }[]; workers?: { worker_id: string; name: string; days: Record<string, { status: string | null; assignments: { project_name: string; shift_label: string; status: string }[] }> }[] };
type Recipient = { worker_id: string; name: string; acked_at: string | null };
type OrderItem = {
  version_id: string; document_number: string; version_no: number; project_name: string; site_name: string; work_date_label: string;
  first_date: string | null; last_date: string | null; next_date: string | null; has_pdf: boolean; dispatch_stopped: boolean; is_test?: boolean;
  acked: Recipient[]; unacked: Recipient[]; decline_pending: Recipient[]; declined: Recipient[]; unsent: Recipient[];
};
type Orders = { start: string; end: string; items: OrderItem[] };
type Claim = { worker_id: string; worker_name: string; phone: string | null; handler_name: string };
type Liff = { init: (options: { liffId: string }) => Promise<void>; isLoggedIn: () => boolean; login: () => void; getIDToken: () => string | null; openWindow?: (p: { url: string; external?: boolean }) => void; isInClient?: () => boolean };
type Tab = "wake" | "today" | "calendar" | "orders" | "availability" | "profile";

const TABS: { key: Tab; label: string }[] = [
  { key: "wake", label: "起床状況" }, { key: "today", label: "今日の案件" }, { key: "calendar", label: "案件カレンダー" },
  { key: "orders", label: "発注依頼書" }, { key: "availability", label: "出勤可否・配置" },
];
const MODES: Record<string, Tab> = { wake: "wake", today: "today", calendar: "calendar", orders: "orders", availability: "availability", profile: "profile" };
const today = () => new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(new Date());
const addDays = (value: string, days: number) => { const d = new Date(`${value}T00:00:00+09:00`); d.setUTCDate(d.getUTCDate() + days); return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(d); };
const labels: Record<string, string> = { available_all_day: "終日可", available_after_15: "15時以降可", unavailable: "不可", consult_required: "要相談", undecided: "未定" };
const buckets = [["ok", "参加予定"], ["changing", "変更確認待ち"], ["unanswered", "未回答"], ["unavailable", "参加不可"]] as const;
const receipt = [["acked", "受領済み"], ["unacked", "未受領"], ["decline_pending", "辞退の確認待ち"], ["declined", "辞退"], ["unsent", "未送付"]] as const;
const RESULTS = [
  { value: "confirmed_awake", label: "起床を確認した" }, { value: "no_answer", label: "電話がつながらない" },
  { value: "site_notified", label: "現場へ連絡した" }, { value: "absent", label: "欠勤" },
] as const;
const time = (value: string) => new Date(value).toLocaleTimeString("ja-JP", { timeZone: "Asia/Tokyo", hour: "2-digit", minute: "2-digit" });
const dayLabel = (value: string) => { const d = new Date(`${value}T00:00:00+09:00`); return `${d.getMonth() + 1}/${d.getDate()}（${"日月火水木金土"[d.getDay()]}）`; };
const TEST_KEY = "vanzai.operator.showTest";
const readShowTest = () => { try { return window.localStorage.getItem(TEST_KEY) !== "0"; } catch { return true; } };
const TestMark = () => <span className="operator-test">テスト</span>;
const telHref = (phone: string) => `tel:${phone.replace(/[^0-9+]/g, "")}`;

function openUrl(url: string) {
  const liff = (window as Window & { liff?: Liff }).liff;
  if (liff?.openWindow && (liff.isInClient?.() ?? false)) { liff.openWindow({ url, external: false }); return; }
  window.location.href = url;
}

function OpenPdf({ versionId, token, busy, setBusy, setError }: { versionId: string; token: string; busy: string; setBusy: (v: string) => void; setError: (v: string) => void }) {
  return <button type="button" className="operator-pdf" disabled={!!busy} onClick={() => {
    setBusy(versionId); setError("");
    operatorPortalRequest<{ url: string }>(`/orders/${encodeURIComponent(versionId)}/pdf-link`, token, {})
      .then((link) => openUrl(link.url)).catch((cause) => setError(cause.message)).finally(() => setBusy(""));
  }}>{busy === versionId ? "開いています…" : "依頼書（PDF）を開く"}</button>;
}

export function PublicLineOperatorPortalPage() {
  const [tab, setTab] = useState<Tab>(MODES[operatorMode()] ?? "wake");
  const [token, setToken] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [day, setDay] = useState(today());
  const [month, setMonth] = useState(today().slice(0, 7));
  const [range, setRange] = useState<"next" | "past">("next");
  const [wake, setWake] = useState<Wake | null>(null);
  const [calendar, setCalendar] = useState<Calendar | null>(null);
  const [orders, setOrders] = useState<Orders | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [updated, setUpdated] = useState("");
  const [claim, setClaim] = useState<Claim | null>(null);
  const [busy, setBusy] = useState("");
  // テストの依頼書も表示する（動作確認用。0.53.9）。選んだ表示はこの端末に残す
  const [showTest, setShowTestState] = useState(readShowTest);
  const setShowTest = (value: boolean) => { setShowTestState(value); try { window.localStorage.setItem(TEST_KEY, value ? "1" : "0"); } catch { /* 保存できなくても表示は切り替わる */ } };

  useEffect(() => {
    let active = true;
    const policy = document.createElement("meta"); policy.name = "referrer"; policy.content = "no-referrer"; document.head.appendChild(policy);
    const initialize = async () => {
      const entry = await getOperatorLineEntry();
      if (!entry.enabled || !entry.liff_id) throw new Error("運営用のLINE画面は準備中です。");
      const host = window as Window & { liff?: Liff };
      if (!host.liff) await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script"); script.src = "https://static.line-scdn.net/liff/edge/2/sdk.js";
        script.onload = () => resolve(); script.onerror = () => reject(new Error("LINEを開き直してください。")); document.head.appendChild(script);
      });
      if (!host.liff) throw new Error("LINEを開き直してください。");
      await host.liff.init({ liffId: entry.liff_id });
      if (!active) return;
      if (!host.liff.isLoggedIn()) { host.liff.login(); return; }
      const proof = host.liff.getIDToken();
      if (!proof) throw new Error("LINEの本人確認ができませんでした。開き直してください。");
      const session = await operatorPortalRequest<{ token: string }>("/session", "", { id_token: proof });
      const person = await operatorPortalRequest<Me>("/me", session.token);
      if (active) { setMe(person); setToken(session.token); }
    };
    initialize().catch((cause) => { if (active) setError(cause.message); });
    return () => { active = false; policy.remove(); };
  }, []);

  const read = useCallback(async (isActive: () => boolean) => {
    const person = await operatorPortalRequest<Me>("/me", token);
    if (!isActive()) return;
    setMe(person);
    const deny = (allowed: boolean, label: string) => { if (!allowed) throw new Error(`${label}を見る権限がありません。管理者へお問い合わせください。`); };
    if (tab === "wake") {
      deny(person.permissions.wake, "起床状況");
      const result = await operatorPortalRequest<Wake>(`/wake-status?date=${day}&include_test=${showTest}`, token);
      if (isActive()) setWake(result);
    } else if (tab === "today" || tab === "calendar") {
      deny(person.permissions.orders, "案件の参加予定");
      const [y, m] = month.split("-").map(Number);
      const start = tab === "today" ? today() : `${month}-01`;
      const end = tab === "today" ? today() : `${month}-${new Date(y, m, 0).getDate()}`;
      const result = await operatorPortalRequest<Calendar>(`/calendar?start=${start}&end=${end}&kind=orders&include_test=${showTest}`, token);
      if (isActive()) setCalendar(result);
    } else if (tab === "availability") {
      deny(person.permissions.availability, "出勤可否・配置");
      const [y, m] = month.split("-").map(Number);
      const result = await operatorPortalRequest<Calendar>(`/calendar?start=${month}-01&end=${month}-${new Date(y, m, 0).getDate()}&kind=availability`, token);
      if (isActive()) setCalendar(result);
    } else if (tab === "orders") {
      deny(person.permissions.orders, "発注依頼書");
      const base = today();
      const [start, end] = range === "next" ? [base, addDays(base, 30)] : [addDays(base, -30), addDays(base, -1)];
      const result = await operatorPortalRequest<Orders>(`/orders?start=${start}&end=${end}&include_test=${showTest}`, token);
      if (isActive()) setOrders(result);
    }
    if (isActive()) setUpdated(new Date().toLocaleTimeString("ja-JP", { timeZone: "Asia/Tokyo", hour: "2-digit", minute: "2-digit" }));
  }, [token, tab, day, month, range, showTest]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true); setError(""); setActionError(""); setWake(null); setCalendar(null); setOrders(null); setUpdated("");
    read(() => active).catch((cause) => { if (active) setError(cause.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, read, refresh]);

  useEffect(() => { setClaim(null); setSearch(""); if (tab === "today") setDay(today()); }, [tab]);

  const startClaim = (row: WakeRow, takeover: boolean) => {
    setBusy(row.worker_id); setActionError("");
    operatorPortalRequest<Claim>("/wake-contacts/claim", token, { day, worker_id: row.worker_id, takeover })
      .then((result) => { setClaim(result); setRefresh((v) => v + 1); })
      .catch((cause) => { setActionError(cause.message); setRefresh((v) => v + 1); })
      .finally(() => setBusy(""));
  };
  const recordResult = (workerId: string, result: string) => {
    setBusy(workerId + result); setActionError("");
    operatorPortalRequest("/wake-contacts", token, { day, worker_id: workerId, result })
      .then(() => { if (result === "confirmed_awake" || result === "absent") setClaim(null); setRefresh((v) => v + 1); })
      .catch((cause) => setActionError(cause.message))
      .finally(() => setBusy(""));
  };

  const days = useMemo(() => {
    const [y, m] = month.split("-").map(Number);
    return Array.from({ length: new Date(y, m, 0).getDate() }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`);
  }, [month]);
  const query = search.trim().toLocaleLowerCase();
  const events = (calendar?.days?.find((row) => row.date === (tab === "today" ? today() : day))?.events ?? [])
    .filter((event) => !query || `${event.project_name} ${event.site_name} ${buckets.flatMap(([b]) => event[b].map((p) => p.name)).join(" ")}`.toLocaleLowerCase().includes(query));
  const selectedWorkers = calendar?.workers?.filter((row) => !query || row.name.toLocaleLowerCase().includes(query) || row.days[day]?.assignments.some((a) => a.project_name.toLocaleLowerCase().includes(query))) ?? [];
  const orderItems = (orders?.items ?? []).filter((item) => !query || `${item.project_name} ${item.site_name} ${item.document_number} ${receipt.flatMap(([k]) => item[k].map((p) => p.name)).join(" ")}`.toLocaleLowerCase().includes(query));
  const wakeItems = (wake?.items ?? []).filter((row) => !query || `${row.worker_name} ${row.entries.map((e) => e.project_name).join(" ")}`.toLocaleLowerCase().includes(query));
  const pdf = (versionId: string) => <OpenPdf versionId={versionId} token={token} busy={busy} setBusy={setBusy} setError={setActionError} />;

  const eventCards = <>{events.map((event) => <article className="operator-card" key={event.version_id + event.project_name}>
    <h3>{event.is_test && <TestMark />}{event.project_name || "案件"}</h3>{event.site_name && <p className="operator-sub">{event.site_name}</p>}
    {buckets.map(([bucket, label]) => <div className={`operator-bucket is-${bucket}`} key={bucket}><strong>{label} {event[bucket].length}名</strong><p>{event[bucket].map((p) => p.name).join("、") || "—"}</p></div>)}
    <div className="operator-actions">{pdf(event.version_id)}<small>発注依頼書 {event.document_number}</small></div>
  </article>)}{events.length === 0 && <p className="operator-empty">{tab === "today" ? "今日の案件はありません。" : "この日の案件はありません。"}</p>}</>;

  return <main className="operator-line"><header className="operator-head"><div><small>VANZAI 公式LINE</small><h1>運営メニュー</h1></div>{me && <p>{me.name}さん</p>}</header>
    <nav aria-label="運営画面" className="operator-tabs">{TABS.map((item) => <button key={item.key} className="operator-button" aria-pressed={tab === item.key} onClick={() => setTab(item.key)}>{item.label}</button>)}</nav>
    {token && <section className="operator-controls">
      {tab === "wake" && <label>確認する日<input aria-label="確認する日" type="date" value={day} onChange={(e) => { if (e.target.value) setDay(e.target.value); }} /></label>}
      {(tab === "calendar" || tab === "availability") && <label>表示する月<input type="month" value={month} onChange={(e) => { if (e.target.value) { setMonth(e.target.value); setDay(`${e.target.value}-01`); } }} /></label>}
      {tab === "today" && <p className="operator-today">{dayLabel(today())} の案件と参加予定者</p>}
      {tab === "orders" && <div className="operator-switch" role="group" aria-label="表示する期間"><button className="operator-button" aria-pressed={range === "next"} onClick={() => setRange("next")}>これから30日</button><button className="operator-button" aria-pressed={range === "past"} onClick={() => setRange("past")}>過去30日</button></div>}
      {tab !== "availability" && tab !== "profile" && <div className="operator-switch" role="group" aria-label="テストの依頼書"><button className="operator-button" aria-pressed={!showTest} onClick={() => setShowTest(false)}>正式のみ</button><button className="operator-button" aria-pressed={showTest} onClick={() => setShowTest(true)}>テストも表示</button></div>}
      <button className="operator-refresh" disabled={loading} onClick={() => setRefresh((v) => v + 1)}>最新の状況に更新</button>{updated && <small>最終取得 {updated}</small>}
    </section>}
    {error && <p className="operator-error" role="alert">{error}</p>}
    {actionError && <p className="operator-error" role="alert">{actionError}</p>}
    {(!token && !error) || loading ? <p role="status">確認しています…</p> : null}
    {tab !== "profile" && token && !error && !loading && <label className="operator-search">{tab === "orders" ? "案件・氏名・番号で探す" : "氏名・案件で探す"}<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} /></label>}

    {tab === "profile" && me && !error && <section className="operator-card"><h2>自分の登録情報</h2><dl><dt>氏名</dt><dd>{me.name}</dd><dt>電話番号</dt><dd>{me.phone || "未登録"}</dd></dl><p>変更がある場合は管理者へご連絡ください。</p></section>}

    {wake && <><section className="operator-summary"><strong>{wake.total}名</strong> 対象 ／ 報告あり {wake.reported}名 ／ 未報告 {wake.total - wake.reported}名</section>
      {wakeItems.map((row) => {
        const open = claim?.worker_id === row.worker_id;
        const needs = !row.wake_reported_at && wake.is_today && row.next_action.step !== "resolved";
        return <article className={`operator-card${needs && row.next_action.priority <= 3 ? " is-urgent" : ""}`} key={row.worker_id}>
          <div className="operator-card-title"><h2>{row.worker_name}{row.is_test && <TestMark />}</h2><strong className={row.wake_reported_at ? "operator-reported" : "operator-missing"}>{row.wake_reported_at ? `報告あり ${time(row.wake_reported_at)}` : row.next_action.step === "resolved" ? row.next_action.label : "未報告"}</strong></div>
          {row.entries.map((entry, index) => <p key={index}>{entry.is_test && <TestMark />}<strong>{entry.project_name}</strong><br />{entry.start_time || "時刻未設定"}〜{entry.end_next_day ? "翌" : ""}{entry.end_time || ""} {entry.site_name}{entry.status === "changing" ? "／変更確認待ち" : ""}</p>)}
          {needs && row.next_action.label && <p className="operator-next">今すること：{row.next_action.label}</p>}
          {row.last_result && <p className="operator-last">最後の記録：{row.last_result.label}（{row.last_result.actor_name} {time(row.last_result.at)}）</p>}
          {needs && <div className="operator-claim">
            {row.handler && !row.handler.is_me && !open && <p className="operator-handler">{row.handler.actor_name}さんが対応中です（{time(row.handler.at)}〜）</p>}
            {!open && (!row.handler ? <button type="button" className="operator-primary" disabled={!!busy} onClick={() => startClaim(row, false)}>{busy === row.worker_id ? "確認しています…" : "私が連絡します"}</button>
              : row.handler.is_me ? <button type="button" className="operator-primary" disabled={!!busy} onClick={() => startClaim(row, false)}>電話番号を表示</button>
              : <button type="button" className="operator-secondary" disabled={!!busy} onClick={() => startClaim(row, true)}>代わりに私が対応する</button>)}
            {open && claim && <div className="operator-call">
              {claim.phone ? <a className="operator-tel" href={telHref(claim.phone)}>電話をかける<span>{claim.phone}</span></a> : <p className="operator-error">電話番号が登録されていません。管理画面の稼働者登録で確認してください。</p>}
              <div className="operator-results">{RESULTS.map((item) => <button type="button" key={item.value} className={`operator-result is-${item.value}`} disabled={!!busy} onClick={() => recordResult(row.worker_id, item.value)}>{busy === row.worker_id + item.value ? "記録しています…" : item.label}</button>)}</div>
            </div>}
          </div>}
        </article>;
      })}{wake.total === 0 && <p className="operator-empty">この日の対象予定はありません。</p>}
      <p className="operator-note">未報告は遅刻の確定ではありません。「私が連絡します」を押すと、ほかの運営には対応中と表示されます。</p></>}

    {calendar && tab === "today" && eventCards}
    {calendar && tab === "calendar" && <><div className="operator-days" aria-label="日付を選択">{days.map((value) => <button className="operator-button" key={value} aria-label={`${Number(value.slice(-2))}日`} aria-pressed={day === value} onClick={() => setDay(value)}>{Number(value.slice(-2))}<small>{calendar.days?.find((r) => r.date === value)?.events.length ? "●" : ""}</small></button>)}</div><h2>{dayLabel(day)} の案件</h2>{eventCards}</>}
    {calendar && tab === "availability" && <><div className="operator-days" aria-label="日付を選択">{days.map((value) => <button className="operator-button" key={value} aria-label={`${Number(value.slice(-2))}日`} aria-pressed={day === value} onClick={() => setDay(value)}>{Number(value.slice(-2))}</button>)}</div><h2>{dayLabel(day)} の出勤可否・配置</h2>
      {selectedWorkers.map((worker) => <article className="operator-card" key={worker.worker_id}><h3>{worker.name}</h3><p>{labels[worker.days[day]?.status ?? ""] || "可否未登録"}</p>{worker.days[day]?.assignments.map((assignment, index) => <p key={index}>{assignment.project_name} ／ {assignment.shift_label}</p>)}</article>)}{selectedWorkers.length === 0 && <p className="operator-empty">該当する稼働者はいません。</p>}</>}

    {orders && <>{orderItems.map((item) => <article className="operator-card" key={item.version_id}>
      <h3>{item.is_test && <TestMark />}{item.project_name || "案件"}</h3>
      <p className="operator-sub">{item.site_name}{item.site_name ? "／" : ""}{item.first_date ? (item.first_date === item.last_date ? dayLabel(item.first_date) : `${dayLabel(item.first_date)}〜${dayLabel(item.last_date || item.first_date)}`) : item.work_date_label || "日程は依頼書を確認"}</p>
      {item.dispatch_stopped && <p className="operator-missing">送付を止めています</p>}
      <div className="operator-chips">{receipt.map(([key, label]) => item[key].length ? <span key={key} className={`operator-chip is-${key}`}>{label} {item[key].length}名</span> : null)}</div>
      <details className="operator-details"><summary>送付先ごとの状況を見る</summary>
        {receipt.map(([key, label]) => item[key].length ? <div className={`operator-bucket is-${key}`} key={key}><strong>{label}</strong><p>{item[key].map((p) => p.name).join("、")}</p></div> : null)}
        {receipt.every(([key]) => item[key].length === 0) && <p>送付先がありません。</p>}
      </details>
      <div className="operator-actions">{item.has_pdf ? pdf(item.version_id) : <small>PDFはまだありません</small>}<small>発注依頼書 {item.document_number}（版{item.version_no}）</small></div>
    </article>)}{orderItems.length === 0 && <p className="operator-empty">{range === "next" ? "これから30日の依頼書はありません。" : "過去30日の依頼書はありません。"}</p>}</>}
  </main>;
}
