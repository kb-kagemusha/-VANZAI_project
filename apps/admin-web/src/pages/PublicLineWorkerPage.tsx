/**
 * 稼働者向けLIFF画面（統合計画 ①）。LINEの中で開き、本人確認のあとで画面を出す。
 * いまは「日付を選んで受諾」（?m=pick&d=送付行ID）だけ。Web確認画面（②）もこのページに追加する。
 */
import { useEffect, useMemo, useState } from "react";

import registrationLogo from "../assets/registration-logo.png";
import { MonthCalendar, monthOf } from "../components/MonthCalendar";
import {
  ApiError,
  createLineWorkerSession,
  getLineWorkerEntry,
  getLineWorkerPick,
  submitLineWorkerPick,
  type LineWorkerPickView,
} from "../lib/api/client";
import "../styles/lineRegistration.css";
import "../styles/monthCalendar.css";
import "../styles/lineWorker.css";

type LiffClient = {
  init: (config: { liffId: string }) => Promise<void>;
  isLoggedIn: () => boolean;
  login: (config?: { redirectUri?: string }) => void;
  getIDToken: () => string | null;
  isInClient?: () => boolean;
  closeWindow?: () => void;
};

function liffClient(): LiffClient | null {
  return (window as Window & { liff?: LiffClient }).liff ?? null;
}

function loadLiff(liffId: string): Promise<void> {
  const existing = liffClient();
  if (existing) return existing.init({ liffId });
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://static.line-scdn.net/liff/edge/2/sdk.js";
    script.onload = () => {
      const loaded = liffClient();
      if (!loaded) {
        reject(new Error("LINEの画面を開けませんでした。"));
        return;
      }
      loaded.init({ liffId }).then(resolve).catch(reject);
    };
    script.onerror = () => reject(new Error("LINEの画面を開けませんでした。"));
    document.head.appendChild(script);
  });
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const payload = error.detail as { detail?: { message?: string } | string } | undefined;
    const detail = payload?.detail;
    if (detail && typeof detail === "object" && detail.message) return detail.message;
    if (typeof detail === "string") return detail;
    return error.message;
  }
  return error instanceof Error ? error.message : "通信に失敗しました。時間をおいて開き直してください。";
}

/** 現在のURL、またはLIFFの liff.state に入った m・d を読む。 */
function readParams(): { mode: string; delivery: string } {
  const url = new URL(window.location.href);
  let params = url.searchParams;
  const state = params.get("liff.state");
  if (state) {
    const inner = state.startsWith("?") ? state.slice(1) : state.split("?")[1] ?? "";
    params = new URLSearchParams(inner);
  }
  return { mode: params.get("m") ?? "", delivery: params.get("d") ?? "" };
}

function dayLabel(day: string): string {
  const [, m, d] = day.split("-").map(Number);
  const weekday = "日月火水木金土"[new Date(`${day}T00:00:00+09:00`).getDay()];
  return `${m}/${d}（${weekday}）`;
}

function compactDates(days: string[]): string {
  return [...days].sort().map(dayLabel).join("、");
}

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function PublicLineWorkerPage() {
  const [phase, setPhase] = useState<"checking" | "error" | "ready" | "done">("checking");
  const [message, setMessage] = useState("");
  const [token, setToken] = useState("");
  const [view, setView] = useState<LineWorkerPickView | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [month, setMonth] = useState("");
  const [sending, setSending] = useState(false);
  const [submitKey, setSubmitKey] = useState(newKey);
  const [result, setResult] = useState<{ message: string; dates: string[] } | null>(null);
  const { mode, delivery } = useMemo(readParams, []);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const entry = await getLineWorkerEntry();
        if (!entry.liff_id) throw new Error("この画面は準備中です。運営へお問い合わせください。");
        await loadLiff(entry.liff_id);
        const liff = liffClient();
        if (!liff) throw new Error("LINEの画面を開けませんでした。");
        if (!liff.isLoggedIn()) {
          liff.login({ redirectUri: window.location.href });
          return;
        }
        const idToken = liff.getIDToken();
        if (!idToken) throw new Error("本人確認ができませんでした。LINEから開き直してください。");
        const session = await createLineWorkerSession(idToken);
        if (!active) return;
        setToken(session.token);
        if (mode !== "pick" || !delivery) throw new Error("開く画面が指定されていません。LINEのボタンから開き直してください。");
        const loaded = await getLineWorkerPick(session.token, delivery);
        if (!active) return;
        setView(loaded);
        setSelected(loaded.state === "accepted" ? loaded.accepted_dates : []);
        setMonth(monthOf(loaded.offered_dates[0] ?? loaded.period?.from ?? loaded.today));
        setPhase("ready");
      } catch (error) {
        if (!active) return;
        setMessage(errorMessage(error));
        setPhase("error");
      }
    })();
    return () => {
      active = false;
    };
  }, [mode, delivery]);

  const offered = useMemo(() => new Set(view?.offered_dates ?? []), [view]);
  const holidays = useMemo(() => new Set(view?.holidays ?? []), [view]);
  const workTimes = useMemo(() => {
    const map = new Map<string, string>();
    for (const day of view?.work_days ?? []) {
      if (day.start_time && !map.has(day.date)) map.set(day.date, `${day.start_time}〜${day.end_next_day ? "翌" : ""}${day.end_time}`);
    }
    return map;
  }, [view]);
  const editable = view?.state === "open";

  function toggle(day: string) {
    if (!editable || !offered.has(day) || holidays.has(day)) return;
    setSelected((current) => (current.includes(day) ? current.filter((d) => d !== day) : [...current, day].sort()));
  }

  async function submit() {
    if (!view || selected.length === 0 || sending) return;
    setSending(true);
    setMessage("");
    try {
      const response = await submitLineWorkerPick(token, view.delivery_id, selected, submitKey);
      if (response.outcome === "acked") {
        setResult({ message: response.message, dates: response.accepted_dates });
        setPhase("done");
      } else {
        setMessage(response.message || "受諾できませんでした。");
        // 状態が変わった可能性があるので、次の送信は新しいキーで行う
        setSubmitKey(newKey());
      }
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setSending(false);
    }
  }

  const minMonth = view?.period ? monthOf(view.period.from) : undefined;
  const maxMonth = view?.period ? monthOf(view.period.to) : undefined;

  return (
    <div className="line-registration-page line-worker-page">
      <div className="lr-container">
        <header className="lr-brand">
          <img src={registrationLogo} alt="" />
        </header>

        {phase === "checking" ? <p className="lw-status">読み込んでいます…</p> : null}
        {phase === "error" ? <div className="lw-card lw-error"><p>{message}</p></div> : null}

        {phase === "done" && result ? (
          <div className="lw-card">
            <h1>受け付けました</h1>
            <p className="lw-lead">受諾を受け付けました。あなたの稼働日（{result.dates.length}日）</p>
            <p className="lw-dates">{compactDates(result.dates)}</p>
            <p className="lw-note">同じ内容をLINEのトークにも送りました。予定はメニューの「スケジュール確認」でも確認できます。この画面は閉じて構いません。</p>
            {liffClient()?.closeWindow ? (
              <button type="button" className="lw-primary" onClick={() => liffClient()?.closeWindow?.()}>閉じる</button>
            ) : null}
          </div>
        ) : null}

        {phase === "ready" && view ? (
          <>
            <div className="lw-card">
              {view.is_test ? <p className="lw-test">【テスト】正式な発注ではありません</p> : null}
              <p className="lw-eyebrow">発注依頼書 {view.document_number}（版{view.version_no}）</p>
              <h1>{view.project_name || "案件"}</h1>
              {view.site_name ? <p className="lw-meta">稼働場所：{view.site_name}</p> : null}
              {view.meeting_place ? <p className="lw-meta">集合場所：{view.meeting_place}</p> : null}
              <StateNotice view={view} />
            </div>

            <div className="lw-card">
              <h2>{editable ? "参加する日をタップして選んでください" : "稼働日"}</h2>
              <MonthCalendar
                month={month}
                onMonthChange={setMonth}
                minMonth={minMonth}
                maxMonth={maxMonth}
                renderDay={(day) => {
                  const isOffered = offered.has(day) && !holidays.has(day);
                  const isSelected = selected.includes(day);
                  const isHoliday = holidays.has(day);
                  const classes = ["lw-day", isOffered ? "is-offered" : "is-off", isSelected ? "is-selected" : "", isHoliday ? "is-holiday" : "", day === view.today ? "is-today" : ""].filter(Boolean).join(" ");
                  return (
                    <button type="button" className={classes} disabled={!editable || !isOffered} aria-pressed={isSelected} onClick={() => toggle(day)}>
                      <span className="lw-day-num">{Number(day.slice(8))}</span>
                      {isSelected ? <span className="lw-day-check">✓</span> : isHoliday ? <span className="lw-day-sub">休</span> : isOffered ? <span className="lw-day-sub">{(workTimes.get(day) ?? "").slice(0, 5)}</span> : null}
                    </button>
                  );
                }}
              />
              <p className="lw-legend"><span className="lw-chip is-offered" />選べる日 <span className="lw-chip is-selected" />選んだ日 <span className="lw-chip is-off" />選べない日・休業日</p>
              {view.period && monthOf(view.period.from) !== monthOf(view.period.to) ? (
                <p className="lw-note">期間が月をまたいでいます。「‹」「›」で前後の月も確認してください。</p>
              ) : null}
            </div>

            {editable ? (
              <div className="lw-footer">
                <p className="lw-footer-dates">{selected.length > 0 ? `選んだ日：${compactDates(selected)}（${selected.length}日）` : "まだ選んでいません"}</p>
                {message ? <p className="lw-footer-error">{message}</p> : null}
                <button type="button" className="lw-primary" disabled={selected.length === 0 || sending} onClick={() => void submit()}>
                  {sending ? "送信しています…" : "この日で受諾する"}
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

function StateNotice({ view }: { view: LineWorkerPickView }) {
  switch (view.state) {
    case "open":
      return <p className="lw-note">全日程に参加できる場合は、LINEのメッセージの「全日程で受諾します」を押してください。</p>;
    case "accepted":
      return <p className="lw-ok">受諾済みです。あなたの稼働日：{compactDates(view.accepted_dates)}</p>;
    case "declined":
      return <p className="lw-warn">この依頼は辞退済みです。</p>;
    case "superseded":
      return <p className="lw-warn">この依頼書には新しい版があります。LINEに届いた新しい依頼書から返事をしてください。</p>;
    case "not_allowed":
      return <p className="lw-warn">この依頼書は日付を選んで受諾できません。LINEのメッセージから全日程で受諾するか、辞退してください。</p>;
    default:
      return <p className="lw-warn">この依頼の返事は受け付けていません。運営へお問い合わせください。</p>;
  }
}
