import { useEffect, useState } from "react";
import { getOperatorLineEntry, submitOperatorLineRegistration } from "../lib/api/client";
import registrationLogo from "../assets/registration-logo.png";
import "../styles/lineRegistration.css";

type Liff = { init: (options: { liffId: string }) => Promise<void>; isLoggedIn: () => boolean; login: () => void; getIDToken: () => string | null };
const liff = () => (window as Window & { liff?: Liff }).liff;

export function PublicLineOperatorRegistrationPage() {
  const [ready, setReady] = useState(false);
  const [closed, setClosed] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  // LIFF may initially deliver the invitation in liff.state before its redirect.
  const parameters = new URLSearchParams(window.location.search);
  const state = parameters.get("liff.state") ?? "";
  const invite = parameters.get("invite") ?? new URLSearchParams(state.includes("?") ? state.slice(state.indexOf("?") + 1) : state).get("invite") ?? "";

  useEffect(() => {
    let active = true;
    const policy = document.createElement("meta"); policy.name = "referrer"; policy.content = "no-referrer"; document.head.appendChild(policy);
    const previousTitle = document.title; document.title = "運営スタッフ登録｜VANZAI";
    getOperatorLineEntry().then(async (entry) => {
      if (!active) return;
      if (!entry.enabled || !entry.liff_id) { setClosed(true); return; }
      if (!invite) throw new Error("管理者から届いた運営スタッフ用の招待リンクを開いてください。");
      if (!liff()) await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script"); script.src = "https://static.line-scdn.net/liff/edge/2/sdk.js";
        script.onload = () => resolve(); script.onerror = () => reject(new Error("LINEを開き直してください。")); document.head.appendChild(script);
      });
      const client = liff(); if (!client) throw new Error("LINEを開き直してください。");
      await client.init({ liffId: entry.liff_id });
      if (!active) return;
      if (!client.isLoggedIn()) { client.login(); return; }
      setReady(true);
    }).catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : "登録画面を開けませんでした。"); });
    return () => { active = false; policy.remove(); document.title = previousTitle; };
  }, [invite]);

  function check() {
    const normalized = phone.normalize("NFKC").replace(/[\s()（）－ー-]/g, "");
    if (!name.trim() || !/^0[0-9]{9,10}$/.test(normalized)) { setError("氏名と電話番号（0から始まる10〜11桁）を確認してください。"); return; }
    setName(name.trim()); setPhone(normalized); setError(""); setConfirm(true);
  }
  async function send() {
    const token = liff()?.getIDToken();
    if (!token) { setError("LINEの本人確認が切れました。招待リンクから開き直してください。"); return; }
    setBusy(true); setError("");
    try { const result = await submitOperatorLineRegistration({ invite, id_token: token, name, phone }); setStatus(result.status); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "送信できませんでした。同じ内容で再試行できます。"); }
    finally { setBusy(false); }
  }
  return <main className="line-registration-page"><div className="lr-container">
    <header className="lr-brand"><img src={registrationLogo} alt="VANZAI ロゴ" /><small>運営スタッフ登録</small></header>
    <section className="lr-intro"><h1>運営スタッフ登録</h1><p>氏名と電話番号を登録し、管理者の承認を受けます。</p></section>
    {closed ? <section className="lr-card"><h2>ただいま準備中です</h2><p>管理者からの案内をお待ちください。</p></section> : status ? <section className="lr-card" role="status"><h2>{status === "approved" ? "登録は承認済みです" : status === "rejected" ? "この申請の確認は終了しています" : "申請を受け付けました"}</h2><p>{status === "pending" ? "管理者の確認・承認をお待ちください。申請の段階では運営スタッフへの登録は完了していません。" : "詳しくは管理者へお問い合わせください。"}</p></section> : <>
      <aside className="lr-privacy"><p>氏名・電話番号・LINEの本人情報は、運営スタッフの登録確認と業務連絡のために使用します。稼働者としての登録や管理画面のID発行は行いません。</p></aside>
      {ready && <section className="lr-card">
        {confirm ? <div className="lr-confirm-card"><h2>申請内容の確認</h2><dl><div><dt>区分</dt><dd>運営スタッフ</dd></div><div><dt>氏名</dt><dd>{name}</dd></div><div><dt>電話番号</dt><dd>{phone}</dd></div></dl><div className="lr-action-bar"><button type="button" className="lr-button lr-primary" disabled={busy} onClick={() => void send()}>{busy ? "送信中…" : "この内容で申請する"}</button><button type="button" className="lr-button lr-secondary" disabled={busy} onClick={() => setConfirm(false)}>入力内容を修正する</button></div></div> : <form className="lr-fields" onSubmit={(event) => { event.preventDefault(); check(); }}>
          <div className="lr-field"><label htmlFor="operator-name">氏名<span className="lr-badge lr-badge-required">必須</span></label><input id="operator-name" autoComplete="name" maxLength={100} required value={name} onChange={(event) => setName(event.target.value)} /></div>
          <div className="lr-field"><label htmlFor="operator-phone">電話番号<span className="lr-badge lr-badge-required">必須</span></label><input id="operator-phone" type="tel" inputMode="tel" autoComplete="tel" maxLength={30} required value={phone} onChange={(event) => setPhone(event.target.value)} /></div>
          <button className="lr-button lr-primary" type="submit">入力内容を確認する</button>
        </form>}
      </section>}
      {!ready && !error ? <p role="status">LINEの本人確認をしています…</p> : null}
    </>}
    {error && <p role="alert" className="lr-error">{error}</p>}
  </div></main>;
}
