import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Clock3, MapPin, Phone, ShieldCheck, UserRound } from "lucide-react";
import registrationLogo from "../assets/registration-logo.png";
import "../styles/lineRegistration.css";
import { PREFECTURES, REGISTRATION_PRIVACY_NOTICE, todayInJapan, validateRegistrationInput, type RegistrationFieldErrors } from "../lib/lineRegistrationUi";

import {
  ApiError,
  createLineRegistrationSession,
  getLineRegistrationEntry,
  getLineRegistrationForm,
  submitLineRegistration,
} from "../lib/api/client";
import { confirmApp } from "../lib/appDialog";
import {
  emptyLineRegistrationInput,
  lineLoginExpired,
  lineRegistrationPayload,
  screenAfterReauthentication,
  screenAfterUnauthorized,
  submissionRetentionAfterAttempt,
  submissionRetentionAfterNewApplication,
  submissionRetentionAfterReauthentication,
  type LineRegistrationInput,
  type LineRegistrationScreen,
} from "../lib/lineRegistrationForm";

type LiffClient = {
  init: (config: { liffId: string }) => Promise<void>;
  isLoggedIn: () => boolean;
  login: () => void;
  getIDToken: () => string | null;
};

const fields: Array<{ key: keyof LineRegistrationInput; label: string; type?: string }> = [
  { key: "last_name", label: "姓" },
  { key: "first_name", label: "名" },
  { key: "last_name_furigana", label: "姓ふりがな" },
  { key: "first_name_furigana", label: "名ふりがな" },
  { key: "phone", label: "電話" },
  { key: "email", label: "メール" },
  { key: "birth_date", label: "生年月日", type: "date" },
  { key: "postal_code", label: "郵便番号" },
  { key: "prefecture", label: "都道府県" },
  { key: "address1", label: "市区町村・番地" },
  { key: "address2", label: "建物名" },
  { key: "nearest_station", label: "最寄り駅" },
  { key: "station_walk_minutes", label: "最寄り駅までの徒歩時間" },
];

let memoryToken = "";
let memorySubject = "";
let memoryKey = "";
let memoryPayload: Record<string, string> | null = null;

function remember(screen: LineRegistrationScreen) {
  memoryToken = screen.token;
  memorySubject = screen.subject;
}

function liffClient(): LiffClient | null {
  const candidate = (window as Window & { liff?: LiffClient }).liff;
  return candidate ?? null;
}

function loadLiff(liffId: string): Promise<void> {
  const existing = liffClient();
  if (existing) {
    return existing.init({ liffId });
  }
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

export function PublicLineRegistrationPage() {
  const [phase, setPhase] = useState<"checking" | "closed" | "form">("checking");
  const [notice, setNotice] = useState("");
  const [screen, setScreen] = useState<LineRegistrationScreen>({
    input: emptyLineRegistrationInput(),
    token: "",
    subject: "",
    linked: false,
    needsReauth: false,
    error: "",
    message: "",
  });
  const [sending, setSending] = useState(false);
  const [holdingSubmission, setHoldingSubmission] = useState(false);
  const [view, setView] = useState<"input" | "confirm" | "receipt">("input");
  const [fieldErrors, setFieldErrors] = useState<RegistrationFieldErrors>({});
  const [receiptSaved, setReceiptSaved] = useState(false);

  useEffect(() => {
    const previous = document.title;
    document.title = "稼働者登録｜VANZAI";
    return () => { document.title = previous; };
  }, []);

  function replaceScreen(next: LineRegistrationScreen) {
    remember(next);
    setScreen(next);
  }

  useEffect(() => {
    let active = true;
    getLineRegistrationEntry()
      .then(async (entry) => {
        if (!active) return;
        if (!entry.enabled || !entry.liff_id) {
          setPhase("closed");
          return;
        }
        await loadLiff(entry.liff_id);
        const liff = liffClient();
        if (!liff) {
          throw new Error("LINEの画面を開けませんでした。");
        }
        if (!liff.isLoggedIn()) {
          liff.login();
          return;
        }
        const idToken = liff.getIDToken();
        if (!idToken) {
          throw new Error("本人確認ができません。LINEでもう一度開き直してください。");
        }
        const session = await createLineRegistrationSession(idToken);
        if (!active) return;
        const next: LineRegistrationScreen = {
          input: emptyLineRegistrationInput(),
          token: session.token,
          subject: session.subject_tag,
          linked: session.linked,
          needsReauth: false,
          error: "",
          message: "",
        };
        remember(next);
        setScreen(next);
        const form = await getLineRegistrationForm(session.token);
        if (!active) return;
        setScreen((current) => ({ ...current, linked: form.linked }));
        setNotice(form.message);
        setPhase("form");
      })
      .catch((loadError) => {
        if (!active) return;
        if (loadError instanceof ApiError && loadError.status === 403) {
          setPhase("closed");
          return;
        }
        setScreen((current) => ({
          ...current,
          error: loadError instanceof Error ? loadError.message : "登録画面を開けませんでした。",
        }));
      });
    return () => {
      active = false;
    };
  }, []);

  async function reauthenticate() {
    setSending(true);
    try {
      const entry = await getLineRegistrationEntry();
      if (!entry.enabled || !entry.liff_id) {
        setPhase("closed");
        return;
      }
      await loadLiff(entry.liff_id);
      const liff = liffClient();
      if (!liff?.isLoggedIn()) {
        replaceScreen({
          ...screen,
          needsReauth: true,
          error: "LINEのログインが確認できません。入力は残しています。",
          message: "",
        });
        return;
      }
      const idToken = liff.getIDToken();
      if (!idToken) {
        replaceScreen({
          ...screen,
          needsReauth: true,
          error: "本人確認ができません。入力は残しています。",
          message: "",
        });
        return;
      }
      const session = await createLineRegistrationSession(idToken);
      const next = screenAfterReauthentication(screen, {
        token: session.token,
        subject: session.subject_tag,
        linked: session.linked,
      });
      const retained = submissionRetentionAfterReauthentication(
        { key: memoryKey, payload: memoryPayload },
        next.subject === screen.subject,
      );
      memoryKey = retained.key;
      memoryPayload = retained.payload;
      setHoldingSubmission(Boolean(retained.payload));
      replaceScreen(next);
      if (next.subject === screen.subject) {
        const form = await getLineRegistrationForm(session.token);
        setNotice(form.message);
        setScreen((current) => ({ ...current, linked: form.linked }));
      } else {
        setNotice("");
        setView("input");
        setFieldErrors({});
      }
    } catch (loadError) {
      replaceScreen({
        ...screen,
        needsReauth: true,
        error: loadError instanceof ApiError ? loadError.message : "本人確認をやり直せませんでした。入力は残しています。",
        message: "",
      });
    } finally {
      setSending(false);
    }
  }

  function discardSubmission() {
    const cleared = submissionRetentionAfterNewApplication();
    memoryKey = cleared.key;
    memoryPayload = cleared.payload;
    setHoldingSubmission(false);
    setView("input");
    setFieldErrors({});
    setScreen((current) => ({ ...current, error: "", message: "" }));
  }

  async function reopenLine() {
    const confirmed = await confirmApp({
      title: "LINEを開き直す",
      message: "LINEのログイン期限が切れています。開き直すと、この画面の入力は残しません。",
      confirmLabel: "開き直す",
    });
    if (!confirmed) return;
    const liff = liffClient();
    liff?.login();
  }

  async function send() {
    if (!memoryToken || sending || screen.needsReauth) return;
    const payload = memoryPayload ?? lineRegistrationPayload(screen.input, screen.linked);
    const key = memoryKey || crypto.randomUUID();
    memoryKey = key;
    memoryPayload = payload;
    setHoldingSubmission(true);
    setSending(true);
    replaceScreen({ ...screen, error: "", message: "" });
    try {
      const result = await submitLineRegistration(memoryToken, key, payload);
      const retained = submissionRetentionAfterAttempt(key, payload, 200);
      memoryKey = retained.key;
      memoryPayload = retained.payload;
      setHoldingSubmission(false);
      setNotice("");
      replaceScreen({ ...screen, error: "", message: result.message });
      setReceiptSaved(result.saved);
      setView("receipt");
    } catch (submitError) {
      const status = submitError instanceof ApiError ? submitError.status : "network";
      const retained = submissionRetentionAfterAttempt(key, payload, status);
      memoryKey = retained.key;
      memoryPayload = retained.payload;
      setHoldingSubmission(Boolean(retained.payload));
      const error = submitError instanceof ApiError ? submitError.message : "送信できませんでした。もう一度送信してください。";
      replaceScreen(status === 401 ? screenAfterUnauthorized(screen, error) : { ...screen, error, message: "" });
    } finally {
      setSending(false);
    }
  }

  const jumpToTop = () => window.scrollTo({ top: 0, behavior: "smooth" });
  function confirmInput() {
    const errors = validateRegistrationInput(screen.input, screen.linked);
    if (screen.linked && !Object.values(screen.input).some((value) => value.trim())) {
      setScreen((current) => ({ ...current, error: "変更する項目を1つ以上入力してください。" }));
      return;
    }
    setFieldErrors(errors);
    const first = Object.keys(errors)[0];
    if (first) {
      document.getElementById(`lr-${first}`)?.focus();
      return;
    }
    setView("confirm");
    setScreen((current) => ({ ...current, error: "", message: "" }));
    jumpToTop();
  }

  const placeholders: Partial<Record<keyof LineRegistrationInput, string>> = {
    last_name: "山田", first_name: "太郎", last_name_furigana: "やまだ", first_name_furigana: "たろう",
    phone: "09012345678", email: "example@mail.com", postal_code: "1234567",
    address1: "〇〇市〇〇町1-2-3", address2: "〇〇マンション101号室", nearest_station: "新宿駅", station_walk_minutes: "10",
  };
  const autocomplete: Partial<Record<keyof LineRegistrationInput, string>> = {
    last_name: "family-name", first_name: "given-name", phone: "tel", email: "email",
    birth_date: "bday", postal_code: "postal-code", prefecture: "address-level1", address1: "address-line1", address2: "address-line2",
  };
  function renderField(key: keyof LineRegistrationInput) {
    const field = fields.find((item) => item.key === key)!;
    const required = !screen.linked && !["email", "address2", "nearest_station", "station_walk_minutes"].includes(key);
    const error = fieldErrors[key];
    const change = (value: string) => {
      setScreen((current) => ({ ...current, input: { ...current.input, [key]: value }, error: "" }));
      setFieldErrors((current) => ({ ...current, [key]: undefined }));
    };
    const properties = {
      id: `lr-${key}`, name: key, value: screen.input[key], autoComplete: autocomplete[key] ?? "off",
      "aria-invalid": Boolean(error), "aria-describedby": error ? `lr-error-${key}` : undefined,
    };
    return <div className="lr-field" key={key}>
      <label htmlFor={`lr-${key}`}><span>{field.label}</span><span className={`lr-badge ${required ? "lr-badge-required" : ""}`}>{required ? "必須" : "任意"}</span></label>
      {key === "prefecture" ? <select {...properties} disabled={holdingSubmission} onChange={(event) => change(event.target.value)}>
        <option value="">選択してください</option>{PREFECTURES.map((prefecture) => <option key={prefecture}>{prefecture}</option>)}
      </select> : <div className={key === "station_walk_minutes" ? "lr-walk-input" : "lr-input-wrap"}>
        {key === "station_walk_minutes" ? <span aria-hidden="true">徒歩</span> : null}
        <input {...properties} readOnly={holdingSubmission}
          type={key === "phone" ? "tel" : key === "email" ? "email" : field.type ?? "text"}
          inputMode={["phone", "postal_code", "station_walk_minutes"].includes(key) ? "numeric" : key === "email" ? "email" : "text"}
          max={key === "birth_date" ? todayInJapan() : undefined}
          maxLength={key === "postal_code" ? 7 : key === "station_walk_minutes" ? 3 : key === "nearest_station" ? 100 : undefined}
          placeholder={placeholders[key]} onChange={(event) => change(event.target.value)} />
        {key === "station_walk_minutes" ? <span aria-hidden="true">分</span> : null}
      </div>}
      {key === "postal_code" ? <span className="lr-hint">ハイフンなし・半角数字7桁</span> : null}
      {error ? <span id={`lr-error-${key}`} className="lr-field-error" role="alert">{error}</span> : null}
    </div>;
  }

  const progress = view === "receipt" ? 2 : view === "confirm" ? 1 : 0;
  return <main className="line-registration-page">
    <div className="lr-container">
      <header className="lr-brand"><img src={registrationLogo} alt="VANZAI ロゴ" /><span><small>稼働者登録</small></span></header>
      {phase === "checking" && !screen.error ? <section className="lr-card lr-status"><span className="lr-spinner" /><h1>登録画面を準備しています</h1><p>そのまま少しお待ちください。</p></section>
      : phase !== "form" ? <section className="lr-card lr-status"><ShieldCheck size={36} /><h1>稼働者登録</h1><p role="alert">{screen.error || "LINEからの登録は受け付けていません"}</p></section>
      : <>
        <ol className="lr-progress" aria-label="申請の流れ">{["入力", "内容確認", "受付"].map((label, index) => <li key={label} className={index <= progress ? "is-active" : ""} aria-current={index === progress ? "step" : undefined}><span>{index < progress ? <Check size={13} /> : index + 1}</span>{label}</li>)}</ol>
        {view === "receipt" ? <section className="lr-card lr-status lr-receipt" aria-live="polite">
          <div className={`lr-status-icon ${receiptSaved ? "is-success" : ""}`}>{receiptSaved ? <CheckCircle2 size={36} /> : <Clock3 size={36} />}</div>
          <h1>{receiptSaved ? "申請を受け付けました" : "前回の申請を確認中です"}</h1>
          <p>{screen.message}</p>
          {receiptSaved ? <p className="lr-hint">登録情報は、管理者の確認・承認後に反映されます。<br />この画面を閉じてお待ちください。</p> : <p className="lr-hint">今回入力した内容は保存していません。<br />この画面を閉じてお待ちください。</p>}
        </section> : <>
          <div className="lr-intro"><span className="lr-eyebrow">{view === "confirm" ? "送信前の最終確認" : "LINEから登録・更新"}</span><h1>{view === "confirm" ? "入力内容をご確認ください" : screen.linked ? "登録情報を更新" : "稼働者情報の登録"}</h1><p>{view === "confirm" ? "内容を確認して、申請を送信してください。" : screen.linked ? "変更したい項目だけ入力してください。空欄の項目は現在の登録内容を変更しません。" : "お名前・連絡先・住所をご入力ください。管理者が確認してから登録します。"}</p></div>
          <aside className="lr-privacy"><ShieldCheck size={18} aria-hidden="true" /><div><strong>個人情報の取り扱い</strong><p>{REGISTRATION_PRIVACY_NOTICE}</p></div></aside>
          {notice ? <div className="lr-notice" role="status"><Clock3 size={18} /><p>{notice}</p></div> : null}
          {view === "input" ? <form noValidate onSubmit={(event) => { event.preventDefault(); confirmInput(); }}>
            <section className="lr-card"><div className="lr-section-heading"><span><UserRound size={19} /></span><div><h2>お名前・生年月日</h2><p>ご本人の情報を入力してください</p></div></div><div className="lr-fields"><div className="lr-pair">{renderField("last_name")}{renderField("first_name")}</div><div className="lr-pair">{renderField("last_name_furigana")}{renderField("first_name_furigana")}</div>{renderField("birth_date")}</div></section>
            <section className="lr-card"><div className="lr-section-heading"><span><Phone size={19} /></span><div><h2>連絡先</h2><p>お仕事のご案内や業務連絡に使用します</p></div></div><div className="lr-fields">{renderField("phone")}{renderField("email")}</div></section>
            <section className="lr-card"><div className="lr-section-heading"><span><MapPin size={19} /></span><div><h2>住所・アクセス</h2><p>住所を変更する場合は、郵便番号から番地まで入力してください</p></div></div><div className="lr-fields">{renderField("postal_code")}{renderField("prefecture")}{renderField("address1")}{renderField("address2")}<div className="lr-divider" />{renderField("nearest_station")}{renderField("station_walk_minutes")}</div></section>
            {screen.error ? <div className="lr-error" role="alert">{screen.error}</div> : null}
            {screen.message ? <div className="lr-notice" role="status">{screen.message}</div> : null}
            {holdingSubmission ? <p className="lr-hint">直前の送信内容を保持しています。内容を変える場合は「別の内容で申請する」を選んでください。</p> : null}
            <div className="lr-action-bar"><button className="lr-button lr-primary" type="submit" disabled={sending}>入力内容を確認する<ArrowRight size={18} /></button><p>確認画面で内容を確認してから送信できます</p></div>
          </form> : <>
            <section className="lr-card lr-confirm-card"><h2>申請する内容</h2><dl>{fields.filter((field) => screen.input[field.key].trim()).map((field) => <div key={field.key}><dt>{field.label}</dt><dd>{field.key === "station_walk_minutes" ? `徒歩${screen.input[field.key]}分` : screen.input[field.key]}</dd></div>)}</dl>{screen.linked ? <p className="lr-hint">表示のない項目は、現在の登録内容を変更しません。</p> : null}</section>
            {screen.error ? <div className="lr-error" role="alert">{screen.error}</div> : null}
            {screen.message ? <div className="lr-notice" role="status">{screen.message}</div> : null}
            {holdingSubmission ? <p className="lr-hint">再送は直前に送った内容で行います。入力は保持しています。</p> : null}
            <div className="lr-action-bar">{screen.needsReauth ? <button type="button" className="lr-button lr-primary" onClick={() => void (lineLoginExpired(screen.error) ? reopenLine() : reauthenticate())} disabled={sending}>{sending ? "確認中…" : lineLoginExpired(screen.error) ? "LINEを開き直す" : "本人確認をやり直す"}</button> : <button type="button" className="lr-button lr-primary" onClick={() => void send()} disabled={sending}>{sending ? "送信しています…" : "この内容で申請する"}<ArrowRight size={18} /></button>}
              <button type="button" className="lr-button lr-secondary" disabled={sending || holdingSubmission} onClick={() => { setView("input"); jumpToTop(); }}><ArrowLeft size={16} />入力内容を修正する</button>
              <p>管理者の確認・承認後に登録情報へ反映します</p>
            </div>
          </>}
          {holdingSubmission ? <button type="button" className="lr-text-button" disabled={sending} onClick={discardSubmission}>別の内容で申請する</button> : null}
        </>}
        <footer className="lr-footer">VANZAI · 稼働者登録</footer>
      </>}
    </div>
  </main>;
}
