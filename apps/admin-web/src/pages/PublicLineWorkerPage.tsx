/**
 * 稼働者向けLIFF画面（統合計画 ①）。LINEの中で開き、本人確認のあとで画面を出す。
 * いまは「日付を選んで受諾」（?m=pick&d=送付行ID）だけ。Web確認画面（②）もこのページに追加する。
 */
import { useEffect, useMemo, useState } from "react";

import registrationLogo from "../assets/registration-logo.png";
import { MonthCalendar, monthOf } from "../components/MonthCalendar";
import { participationDateLines, participationPeriodLabel } from "../lib/participationDateFormat";
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

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function PublicLineWorkerPage() {
  const [phase, setPhase] = useState<"checking" | "error" | "ready" | "confirm" | "done">("checking");
  const [message, setMessage] = useState("");
  const [token, setToken] = useState("");
  const [view, setView] = useState<LineWorkerPickView | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [month, setMonth] = useState("");
  const [sending, setSending] = useState(false);
  const [submitKey, setSubmitKey] = useState(newKey);
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
        setSelected(loaded.state === "accepted" ? loaded.accepted_dates : loaded.state === "open"
          ? [...new Set(loaded.offered_dates)].filter((day) => !loaded.holidays.includes(day)).sort() : []);
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
        // 受付の通知はLINEのトークに届くので、画面は閉じる（LINEの外で開いたときだけ完了を表示）
        const liff = liffClient();
        if (liff?.closeWindow && (liff.isInClient?.() ?? true)) {
          liff.closeWindow();
        }
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

        {phase === "done" ? (
          <div className="lw-card">
            <h1>送信しました</h1>
            <p className="lw-note">LINEのトークに受付の通知を送りました。</p>
          </div>
        ) : null}

        {phase === "confirm" && view ? (
          <div className="lw-card">
            <h1>確認</h1>
            <p className="lw-confirm-lead">以下の参加日で返信します。</p>
            <p className="lw-eyebrow">発注依頼書 {view.document_number}（版{view.version_no}）{view.project_name ? `　${view.project_name.split("\n")[0]}` : ""}</p>
            <PeriodSummary view={view} />
            <h2 className="lw-confirm-head">参加する日（{selected.length}日）</h2>
            <p className="lw-dates">{participationDateLines(selected)}</p>
            {(() => {
              const off = [...new Set(view.work_days.map((day) => day.date))].filter((d) => !selected.includes(d) && !holidays.has(d));
              return (
                <>
                  <h2 className="lw-confirm-head">参加しない日</h2>
                  <p className="lw-off-dates">{participationDateLines(off) || "なし"}</p>
                </>
              );
            })()}
            {message ? <p className="lw-footer-error">{message}</p> : null}
            <div className="lw-confirm-actions">
              <button type="button" className="lw-primary" disabled={sending} onClick={() => void submit()}>
                {sending ? "送信しています…" : "送信"}
              </button>
              <button type="button" className="lw-secondary" disabled={sending} onClick={() => { setMessage(""); setPhase("ready"); }}>
                日付を選び直す
              </button>
            </div>
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
              <PeriodSummary view={view} />
              <StateNotice view={view} />
            </div>

            <div className="lw-card">
              <h2>{editable ? "参加できない日をタップして外してください" : "稼働日"}</h2>
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
              <div className="lw-card">
                <h2>選んだ日（{selected.length}日）</h2>
                <p className="lw-dates">{participationDateLines(selected) || "まだ選んでいません"}</p>
              </div>
            ) : null}
            {editable ? (
              <div className="lw-footer">
                <p className="lw-footer-dates">{selected.length > 0 ? `${selected.length}日を選択しています` : "まだ選んでいません"}</p>
                {message ? <p className="lw-footer-error">{message}</p> : null}
                <button type="button" className="lw-primary" disabled={selected.length === 0} onClick={() => { setMessage(""); setPhase("confirm"); window.scrollTo(0, 0); }}>
                  確認する
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

function PeriodSummary({ view }: { view: LineWorkerPickView }) {
  return <>
    <h2 className="lw-confirm-head">期間</h2>
    <p className="lw-off-dates">{participationPeriodLabel(view.period)}</p>
    <h2 className="lw-confirm-head">期間中の休業日</h2>
    <p className="lw-off-dates">{participationDateLines(view.holidays) || "なし"}</p>
  </>;
}

function StateNotice({ view }: { view: LineWorkerPickView }) {
  switch (view.state) {
    case "open":
      return <p className="lw-note">初めは依頼された日をすべて選んでいます。参加できない日だけタップして外し、確認へ進んでください。</p>;
    case "accepted":
      return <p className="lw-ok">受諾済みです。参加する日：{"\n"}{participationDateLines(view.accepted_dates)}</p>;
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
