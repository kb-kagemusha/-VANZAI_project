/**
 * Web確認画面からの返事（統合計画 ③-C、D-09）：全日程で受諾する・理由を付けて辞退する。LIFF（?m=reply&d=送付行ID）。
 * トークの「受諾」「辞退」と同じ処理をサーバーで通す。送る前に確認画面を挟み、同じ送信の二重記録は冪等キーで防ぐ。
 */
import { useEffect, useState } from "react";

import { participationDateLines, participationPeriodLabel } from "../lib/participationDateFormat";
import { createPortalPdfLink, getPortalReplyView, submitPortalReply, type PortalReplyView } from "../lib/lineWorkerPortalApi";

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function messageOf(error: unknown): string {
  return error instanceof Error && error.message ? error.message : "通信に失敗しました。時間をおいて開き直してください。";
}

type LiffLike = { closeWindow?: () => void; isInClient?: () => boolean; openWindow?: (p: { url: string; external?: boolean }) => void };

function liff(): LiffLike | undefined {
  return (window as Window & { liff?: LiffLike }).liff;
}

function StateNotice({ view }: { view: PortalReplyView }) {
  switch (view.state) {
    case "open":
      return null;
    case "accepted":
      return <p className="lw-ok">{view.requires_operator_confirmation ? "参加可能の回答済みです。運営からの結果連絡をお待ちください。回答した日：" : "受諾済みです。参加する日："}{"\n"}{participationDateLines(view.accepted_dates)}</p>;
    case "declined":
      return <p className="lw-warn">この依頼は辞退済みです。</p>;
    case "superseded":
      return <p className="lw-warn">この依頼書には新しい版があります。予定の画面の「確認が必要な依頼」から、新しい依頼書に返事をしてください。</p>;
    default:
      return <p className="lw-warn">この依頼の返事は受け付けていません。運営へお問い合わせください。</p>;
  }
}

export function LineWorkerReply({ token, deliveryId }: { token: string; deliveryId: string }) {
  const [view, setView] = useState<PortalReplyView | null>(null);
  const [phase, setPhase] = useState<"ready" | "accept" | "decline" | "done">("ready");
  const [doneOutcome, setDoneOutcome] = useState<"acked" | "declined" | "">("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [pdfBusy, setPdfBusy] = useState(false);
  const [submitKey, setSubmitKey] = useState(newKey);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const loaded = await getPortalReplyView(token, deliveryId);
        if (active) setView(loaded);
      } catch (error) {
        if (active) setMessage(messageOf(error));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [token, deliveryId]);

  async function openPdf() {
    if (!view || pdfBusy) return;
    setPdfBusy(true);
    setMessage("");
    try {
      const link = await createPortalPdfLink(token, view.delivery_id);
      const client = liff();
      if (client?.openWindow && (client.isInClient?.() ?? false)) client.openWindow({ url: link.url, external: false });
      else window.location.href = link.url;
    } catch (error) {
      setMessage(messageOf(error));
    } finally {
      setPdfBusy(false);
    }
  }

  async function send(action: "accept" | "decline") {
    if (!view || sending) return;
    if (action === "decline" && !reason.trim()) {
      setMessage("辞退の理由を入力してください。");
      return;
    }
    setSending(true);
    setMessage("");
    try {
      const result = await submitPortalReply(token, view.delivery_id, action, action === "decline" ? reason.trim() : "", submitKey);
      if (result.outcome === "acked" || result.outcome === "declined") {
        setDoneOutcome(result.outcome);
        // 受付の通知はLINEのトークに届くので、LINEの中では画面を閉じる
        const client = liff();
        if (client?.closeWindow && (client.isInClient?.() ?? true)) client.closeWindow();
        setPhase("done");
      } else {
        setMessage(result.message || "返事を記録できませんでした。画面を開き直してください。");
        setSubmitKey(newKey());
        setPhase("ready");
      }
    } catch (error) {
      setMessage(messageOf(error));
    } finally {
      setSending(false);
    }
  }

  if (loading) return <p className="lw-status">読み込んでいます…</p>;
  if (!view) return <div className="lw-card lw-error"><p>{message || "この依頼書は開けません。"}</p></div>;

  if (phase === "done") {
    return (
      <div className="lw-card">
        <h1>{doneOutcome === "acked" ? view.requires_operator_confirmation ? "参加可能の回答を送りました" : "受諾を送りました" : "辞退を送りました"}</h1>
        <p className="lw-note">LINEのトークに受付の通知を送りました。</p>
        <a className="lw-secondary lwp-link-button lwp-back" href="?m=home">予定の画面へ戻る</a>
      </div>
    );
  }

  const offered = view.offered_dates;
  const summary = (
    <>
      {view.is_test ? <p className="lw-test">【テスト】正式な発注ではありません</p> : null}
      <p className="lw-eyebrow">発注依頼書 {view.document_number}（版{view.version_no}）</p>
      <h1>{(view.project_name || "案件").split("\n")[0]}</h1>
      {view.site_name ? <p className="lw-meta">稼働場所：{view.site_name.split("\n")[0]}</p> : null}
      {view.meeting_place ? <p className="lw-meta">集合場所：{view.meeting_place}</p> : null}
      <h2 className="lw-confirm-head">期間</h2>
      <p className="lw-off-dates">{participationPeriodLabel(view.period)}</p>
      <h2 className="lw-confirm-head">依頼された日（{offered.length}日）</h2>
      <p className="lw-dates">{participationDateLines(offered) || "なし"}</p>
    </>
  );

  if (phase === "accept") {
    return (
      <div className="lw-card">
        <h1>確認</h1>
        <p className="lw-confirm-lead">{view.requires_operator_confirmation ? "依頼された日すべてで参加可能と回答します。参加者は運営が決定し、改めて連絡します。" : "依頼された日すべてで受諾します。"}</p>
        {summary}
        {message ? <p className="lw-footer-error">{message}</p> : null}
        <div className="lw-confirm-actions">
          <button type="button" className="lw-primary" disabled={sending} onClick={() => void send("accept")}>{sending ? "送信しています…" : view.requires_operator_confirmation ? "参加可能と回答する" : "受諾を送る"}</button>
          <button type="button" className="lw-secondary" disabled={sending} onClick={() => { setMessage(""); setPhase("ready"); }}>戻る</button>
        </div>
      </div>
    );
  }

  if (phase === "decline") {
    return (
      <div className="lw-card">
        <h1>辞退する</h1>
        {summary}
        <label className="lwp-reason">
          <span className="lw-confirm-head">辞退の理由（必須）</span>
          <textarea rows={3} maxLength={500} value={reason} disabled={sending} placeholder="例：この日は別の予定があるため" onChange={(e) => { setReason(e.target.value); setMessage(""); }} />
        </label>
        {message ? <p className="lw-footer-error">{message}</p> : null}
        <div className="lw-confirm-actions">
          <button type="button" className="lw-primary lwp-decline" disabled={sending || !reason.trim()} onClick={() => void send("decline")}>{sending ? "送信しています…" : "辞退を送る"}</button>
          <button type="button" className="lw-secondary" disabled={sending} onClick={() => { setMessage(""); setPhase("ready"); }}>戻る</button>
        </div>
      </div>
    );
  }

  return (
    <div className="lw-card">
      {summary}
      <StateNotice view={view} />
      {view.decline_pending && view.state === "open" ? <p className="lw-note">トークで「辞退」を押したまま、理由がまだ届いていません。ここから受諾か、理由を付けて辞退できます。</p> : null}
      {message ? <p className="lw-footer-error">{message}</p> : null}
      <div className="lw-confirm-actions">
        {view.pdf_available ? (
          <button type="button" className="lw-secondary" disabled={pdfBusy} onClick={() => void openPdf()}>{pdfBusy ? "開いています…" : "依頼書（PDF）を開く"}</button>
        ) : null}
        {view.state === "open" ? (
          <>
            <button type="button" className="lw-primary" onClick={() => { setMessage(""); setPhase("accept"); window.scrollTo(0, 0); }}>{view.requires_operator_confirmation ? "全日程で参加可能" : "全日程で受諾する"}</button>
            {view.can_pick ? <a className="lw-secondary lwp-link-button" href={`?m=pick&d=${encodeURIComponent(view.delivery_id)}`}>{view.requires_operator_confirmation ? "参加可能な日を選ぶ" : "日付を選んで受諾する"}</a> : null}
            <button type="button" className="lw-secondary lwp-decline-entry" onClick={() => { setMessage(""); setPhase("decline"); window.scrollTo(0, 0); }}>辞退する</button>
          </>
        ) : null}
        <a className="lw-secondary lwp-link-button lwp-back" href="?m=home">予定の画面へ戻る</a>
      </div>
    </div>
  );
}
