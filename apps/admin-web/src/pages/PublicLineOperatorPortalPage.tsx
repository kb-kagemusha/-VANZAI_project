import { useEffect, useMemo, useState } from "react";
import { getOperatorLineEntry, operatorPortalRequest } from "../lib/api/client";
import { operatorMode } from "./PublicLineOperatorEntry";
import "../styles/lineOperator.css";

type Me = { name: string; phone: string | null; permissions: { wake: boolean; availability: boolean; orders: boolean } };
type Entry = { project_name: string; site_name: string; start_time: string | null; end_time: string | null; end_next_day: boolean; status: string };
type Wake = { date: string; total: number; reported: number; items: { worker_id: string; worker_name: string; first_start: string | null; wake_reported_at: string | null; entries: Entry[] }[] };
type Person = { worker_id: string; name: string };
type Event = { project_name: string; site_name: string; ok: Person[]; changing: Person[]; unanswered: Person[]; unavailable: Person[] };
type Calendar = { kind: string; days?: { date: string; events: Event[] }[]; workers?: { worker_id: string; name: string; days: Record<string, { status: string | null; assignments: { project_name: string; shift_label: string; status: string }[] }> }[] };
type Liff = { init: (options: { liffId: string }) => Promise<void>; isLoggedIn: () => boolean; login: () => void; getIDToken: () => string | null };
const today = () => new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Tokyo" }).format(new Date());
const labels: Record<string, string> = { available_all_day: "終日可", available_after_15: "15時以降可", unavailable: "不可", consult_required: "要相談", undecided: "未定" };
const buckets = [["ok", "参加予定"], ["changing", "変更確認待ち"], ["unanswered", "未回答"], ["unavailable", "参加不可"]] as const;
const time = (value: string) => new Date(value).toLocaleTimeString("ja-JP", { timeZone: "Asia/Tokyo", hour: "2-digit", minute: "2-digit" });

export function PublicLineOperatorPortalPage() {
  const [tab, setTab] = useState(operatorMode() || "wake");
  const [token, setToken] = useState("");
  const [me, setMe] = useState<Me | null>(null);
  const [day, setDay] = useState(today());
  const [month, setMonth] = useState(today().slice(0, 7));
  const [kind, setKind] = useState("orders");
  const [wake, setWake] = useState<Wake | null>(null);
  const [calendar, setCalendar] = useState<Calendar | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [updated, setUpdated] = useState("");

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
      if (active) { setMe(person); setToken(session.token); setKind(person.permissions.orders ? "orders" : "availability"); }
    };
    initialize().catch((cause) => { if (active) setError(cause.message); });
    return () => { active = false; policy.remove(); };
  }, []);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true); setError(""); setWake(null); setCalendar(null); setUpdated("");
    const read = async () => {
      const person = await operatorPortalRequest<Me>("/me", token);
      if (!active) return;
      setMe(person);
      if (tab === "wake") {
        if (!person.permissions.wake) throw new Error("起床状況を見る権限がありません。管理者へお問い合わせください。");
        const result = await operatorPortalRequest<Wake>(`/wake-status?date=${day}`, token);
        if (active) setWake(result);
      } else if (tab === "calendar") {
        if (!(kind === "orders" ? person.permissions.orders : person.permissions.availability)) throw new Error("このカレンダーを見る権限がありません。別の表示を選ぶか、管理者へお問い合わせください。");
        const [y, m] = month.split("-").map(Number);
        const last = new Date(y, m, 0).getDate();
        const result = await operatorPortalRequest<Calendar>(`/calendar?start=${month}-01&end=${month}-${last}&kind=${kind}`, token);
        if (active) setCalendar(result);
      }
      if (active) setUpdated(new Date().toLocaleTimeString("ja-JP", { timeZone: "Asia/Tokyo" }));
    };
    read().catch((cause) => { if (active) { setError(cause.message); setWake(null); setCalendar(null); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [token, tab, day, month, kind, refresh]);

  const days = useMemo(() => {
    const [y, m] = month.split("-").map(Number);
    return Array.from({ length: new Date(y, m, 0).getDate() }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`);
  }, [month]);
  const events = calendar?.days?.find((row) => row.date === day)?.events ?? [];
  const query = search.trim().toLocaleLowerCase();
  const selectedWorkers = calendar?.workers?.filter((row) => !query || row.name.toLocaleLowerCase().includes(query) || row.days[day]?.assignments.some((a) => a.project_name.toLocaleLowerCase().includes(query))) ?? [];
  return <main className="operator-line"><header><small>VANZAI 公式LINE</small><h1>運営スタッフ</h1>{me && <p>{me.name}さん</p>}</header>
    <nav aria-label="運営画面"><button className="operator-button" aria-pressed={tab === "wake"} onClick={() => setTab("wake")}>起床状況</button><button className="operator-button" aria-pressed={tab === "calendar"} onClick={() => setTab("calendar")}>カレンダー</button><button className="operator-button" aria-pressed={tab === "profile"} onClick={() => setTab("profile")}>自分の登録情報</button></nav>
    {token && <section className="operator-controls">{tab === "wake" && <label>確認する日<input aria-label="確認する日" type="date" value={day} onChange={(e) => { if (e.target.value) setDay(e.target.value); }} /></label>}
      {tab === "calendar" && <><label>表示する月<input type="month" value={month} onChange={(e) => { if (e.target.value) { setMonth(e.target.value); setDay(`${e.target.value}-01`); } }} /></label><div className="operator-switch">{me?.permissions.orders && <button className="operator-button" aria-pressed={kind === "orders"} onClick={() => setKind("orders")}>参加予定</button>}{me?.permissions.availability && <button className="operator-button" aria-pressed={kind === "availability"} onClick={() => setKind("availability")}>出勤可否・配置</button>}</div></>}
      <button className="operator-refresh" disabled={loading} onClick={() => setRefresh((v) => v + 1)}>最新の状況に更新</button>{updated && <small>最終取得 {updated}</small>}
    </section>}
    {error && <p className="operator-error" role="alert">{error}</p>}
    {(!token && !error) || loading ? <p role="status">確認しています…</p> : null}
    {tab === "profile" && me && !error && <section className="operator-card"><h2>自分の登録情報</h2><dl><dt>氏名</dt><dd>{me.name}</dd><dt>電話番号</dt><dd>{me.phone || "未登録"}</dd></dl><p>変更がある場合は管理者へご連絡ください。</p></section>}
    {wake && <><section className="operator-summary"><strong>{wake.total}名</strong> 対象 ／ 報告あり {wake.reported}名 ／ 未報告 {wake.total - wake.reported}名</section><label className="operator-search">氏名・案件で探す<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      {wake.items.filter((row) => !query || `${row.worker_name} ${row.entries.map((e) => e.project_name).join(" ")}`.toLocaleLowerCase().includes(query)).map((row) => <article className="operator-card" key={row.worker_id}><div className="operator-card-title"><h2>{row.worker_name}</h2><strong className={row.wake_reported_at ? "operator-reported" : "operator-missing"}>{row.wake_reported_at ? `報告あり ${time(row.wake_reported_at)}` : "未報告"}</strong></div>{row.entries.map((entry, index) => <p key={index}><strong>{entry.project_name}</strong><br />{entry.start_time || "時刻未設定"}〜{entry.end_next_day ? "翌" : ""}{entry.end_time || ""} {entry.site_name}{entry.status === "changing" ? "／変更確認待ち" : ""}</p>)}</article>)}{wake.total === 0 && <p>この日の対象予定はありません。</p>}<p className="operator-note">未報告は遅刻の確定ではありません。自動催促・運営への通知は別の機能です。</p></>}
    {calendar && <><div className="operator-days" aria-label="日付を選択">{days.map((value) => <button className="operator-button" key={value} aria-label={`${Number(value.slice(-2))}日`} aria-pressed={day === value} onClick={() => setDay(value)}>{Number(value.slice(-2))}<small>{calendar.days?.find((r) => r.date === value)?.events.length ? "●" : ""}</small></button>)}</div><h2>{day} の状況</h2><label className="operator-search">氏名・案件で探す<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      {calendar.kind === "orders" ? <>{events.filter((event) => !query || `${event.project_name} ${buckets.flatMap(([b]) => event[b].map((p) => p.name)).join(" ")}`.toLocaleLowerCase().includes(query)).map((event, index) => <article className="operator-card" key={index}><h3>{event.project_name}</h3><p>{event.site_name}</p>{buckets.map(([bucket, label]) => <div className="operator-bucket" key={bucket}><strong>{label} {event[bucket].length}名</strong><p>{event[bucket].map((p) => p.name).join("、") || "—"}</p></div>)}</article>)}{events.length === 0 && <p>この日の参加予定はありません。</p>}</> : <>{selectedWorkers.map((worker) => <article className="operator-card" key={worker.worker_id}><h3>{worker.name}</h3><p>{labels[worker.days[day]?.status ?? ""] || "可否未登録"}</p>{worker.days[day]?.assignments.map((assignment, index) => <p key={index}>{assignment.project_name} ／ {assignment.shift_label}</p>)}</article>)}{selectedWorkers.length === 0 && <p>該当する稼働者はいません。</p>}</>}
    </>}
  </main>;
}
