import { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Check, CheckCircle2, Clock3, MapPin, Phone, ShieldCheck, UserRound } from "lucide-react";
import { AdditionalStationFields } from "../components/AdditionalStationFields";
import { BirthDateFields } from "../components/BirthDateFields";
import { showAdditionalStations } from "../lib/additionalStations";
import registrationLogo from "../assets/registration-logo.png";
import "../styles/lineRegistration.css";
import { PREFECTURES, REGISTRATION_PRIVACY_NOTICE, todayInJapan, validateRegistrationInput, type RegistrationFieldErrors } from "../lib/lineRegistrationUi";
import { lookupPostalAddress, normalizePostalCode, type PostalAddress } from "../lib/postalAddress";

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
  screenAfterRegisteredForm,
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
  { key: "birth_date", label: "生年月日" },
  { key: "postal_code", label: "郵便番号" },
  { key: "prefecture", label: "都道府県" },
  { key: "address1", label: "市区町村・番地" },
  { key: "address2", label: "建物名" },
  { key: "nearest_station", label: "最寄り駅" },
  { key: "station_walk_minutes", label: "最寄り駅までの徒歩時間" },
  { key: "additional_stations", label: "追加の最寄り駅" },
  { key: "emergency_contact_phone", label: "緊急連絡先の電話番号" },
  { key: "emergency_contact_name", label: "緊急連絡先のお名前" },
  { key: "emergency_contact_relationship", label: "ご本人との関係" },
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
  const [postalMessage, setPostalMessage] = useState("");
  const [postalLoading, setPostalLoading] = useState(false);
  const [postalChoices, setPostalChoices] = useState<{ postal: string; addresses: PostalAddress[] }>({ postal: "", addresses: [] });
  const addressEditVersion = useRef(0);

  useEffect(() => {
    const postal = screen.input.postal_code;
    setPostalChoices({ postal: "", addresses: [] });
    setPostalMessage("");
    setPostalLoading(false);
    if (phase !== "form" || view !== "input" || holdingSubmission || (screen.baseline && postal === screen.baseline.postal_code && screen.baseline.prefecture && screen.baseline.address1) || !/^[0-9]{7}$/.test(postal)) return;
    setPostalLoading(true);
    const controller = new AbortController();
    let active = true;
    const beforeEdit = addressEditVersion.current;
    let deadline: ReturnType<typeof setTimeout> | undefined;
    const timer = setTimeout(() => {
      setPostalMessage("住所を検索しています…");
      deadline = setTimeout(() => {
        controller.abort();
        if (active) setPostalLoading(false);
        if (active) setPostalMessage("住所を取得できませんでした。手入力で続けられます。");
      }, 10000);
      lookupPostalAddress(postal, controller.signal).then((addresses) => {
        if (!active) return;
        if (addresses.length === 0) {
          setPostalMessage("該当する住所が見つかりません。郵便番号を確認するか、手入力してください。");
        } else if (addresses.length === 1 && beforeEdit === addressEditVersion.current) {
          setScreen((current) => current.input.postal_code === postal ? { ...current, input: { ...current.input, prefecture: addresses[0].prefecture, address1: addresses[0].address } } : current);
          setFieldErrors((current) => ({ ...current, prefecture: undefined, address1: undefined }));
          setPostalMessage("住所を入力しました。続けて番地を入力してください。");
        } else {
          setPostalChoices({ postal, addresses });
          setPostalMessage(addresses.length > 1 ? "候補が複数あります。住所を選択してください。" : "手入力した住所を残しました。必要なら検索結果を選択してください。");
        }
      }).catch(() => {
        if (active && !controller.signal.aborted) setPostalMessage("住所を取得できませんでした。手入力で続けられます。");
      }).finally(() => { clearTimeout(deadline); if (active) setPostalLoading(false); });
    }, 300);
    return () => { active = false; clearTimeout(timer); clearTimeout(deadline); controller.abort(); };
  }, [screen.input.postal_code, phase, view, holdingSubmission]);

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
        replaceScreen(screenAfterRegisteredForm(next, form));
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
      const form = await getLineRegistrationForm(session.token);
      setNotice(form.message);
      const samePerson = next.subject === screen.subject;
      replaceScreen(samePerson && retained.payload ? { ...next, linked: form.linked } : screenAfterRegisteredForm(next, form, samePerson));
      if (!samePerson) {
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
    const payload = memoryPayload ?? lineRegistrationPayload(screen.input, screen.linked, screen.baseline);
    const key = memoryKey || crypto.randomUUID();
    memoryKey = key;
    memoryPayload = payload;
    setHoldingSubmission(true);
    setSending(true);
    replaceScreen({ ...screen, error: "", message: "" });
    try {
      const result = await submitLineRegistration(memoryToken, key, payload, screen.formTicket);
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
    if (postalLoading) return;
    const errors = validateRegistrationInput(screen.input, screen.baseline ? false : screen.linked);
    if (!Object.keys(errors).length && screen.linked && !Object.keys(lineRegistrationPayload(screen.input, true, screen.baseline)).length) {
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
    emergency_contact_phone: "09012345678", emergency_contact_name: "山田 花子", emergency_contact_relationship: "実父・実兄・配偶者など",
  };
  const autocomplete: Partial<Record<keyof LineRegistrationInput, string>> = {
    last_name: "family-name", first_name: "given-name", phone: "tel", email: "email",
    birth_date: "bday", postal_code: "postal-code", prefecture: "address-level1", address1: "address-line1", address2: "address-line2",
  };
  function renderField(key: keyof LineRegistrationInput) {
    const field = fields.find((item) => item.key === key)!;
    const required = key !== "address2" && (!screen.linked || (screen.baseline !== undefined && !screen.baseline[key].trim()));
    const error = fieldErrors[key];
    const change = (value: string) => {
      if (key === "prefecture" || key === "address1") addressEditVersion.current += 1;
      if (key === "postal_code") value = normalizePostalCode(value);
      setScreen((current) => ({ ...current, input: { ...current.input, [key]: value }, error: "" }));
      setFieldErrors((current) => ({ ...current, [key]: undefined }));
    };
    const properties = {
      id: `lr-${key}`, name: key, value: screen.input[key], autoComplete: autocomplete[key] ?? "off",
      "aria-invalid": Boolean(error), "aria-describedby": error ? `lr-error-${key}` : undefined,
      "aria-required": required, required,
    };
    return <div className="lr-field" key={key}>
      <label htmlFor={`lr-${key}`}><span>{field.label}</span><span className={`lr-badge ${required ? "lr-badge-required" : ""}`}>{required ? "必須" : screen.baseline?.[key].trim() ? "登録済み" : "任意"}</span></label>
      {key === "birth_date" ? <BirthDateFields value={screen.input.birth_date} onChange={change} required={required} disabled={holdingSubmission} error={error} today={todayInJapan()} /> : key === "prefecture" ? <select {...properties} disabled={holdingSubmission} onChange={(event) => change(event.target.value)}>
        <option value="">選択してください</option>{PREFECTURES.map((prefecture) => <option key={prefecture}>{prefecture}</option>)}
      </select> : <div className={key === "station_walk_minutes" ? "lr-walk-input" : "lr-input-wrap"}>
        {key === "station_walk_minutes" ? <span aria-hidden="true">徒歩</span> : null}
        <input {...properties} readOnly={holdingSubmission}
          type={["phone", "emergency_contact_phone"].includes(key) ? "tel" : key === "email" ? "email" : field.type ?? "text"}
          inputMode={["phone", "postal_code", "station_walk_minutes", "emergency_contact_phone"].includes(key) ? "numeric" : key === "email" ? "email" : "text"}
          maxLength={key === "postal_code" ? 8 : key === "station_walk_minutes" ? 3 : key === "nearest_station" ? 100 : key === "emergency_contact_name" ? 200 : key === "emergency_contact_relationship" ? 50 : key === "emergency_contact_phone" ? 20 : undefined}
          placeholder={placeholders[key]} onChange={(event) => change(event.target.value)} />
        {key === "station_walk_minutes" ? <span aria-hidden="true">分</span> : null}
      </div>}
      {key === "postal_code" ? <span className="lr-hint">ハイフンなし・半角数字7桁</span> : null}
      {key === "postal_code" && postalMessage ? <span className="lr-hint" role="status">{postalMessage}</span> : null}
      {key === "postal_code" && postalChoices.addresses.length ? <select aria-label="郵便番号の住所候補" defaultValue="" disabled={holdingSubmission} onChange={(event) => {
        const address = postalChoices.addresses[Number(event.target.value)];
        if (!event.target.value || !address) return;
        addressEditVersion.current += 1;
        setScreen((current) => current.input.postal_code === postalChoices.postal ? { ...current, input: { ...current.input, prefecture: address.prefecture, address1: address.address } } : current);
        setPostalMessage("住所を入力しました。続けて番地を入力してください。");
        setPostalChoices({ postal: "", addresses: [] });
      }}><option value="">検索結果から住所を選択</option>{postalChoices.addresses.map((item, index) => <option key={index} value={index}>{item.prefecture}{item.address}</option>)}</select> : null}
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
          <div className="lr-intro"><span className="lr-eyebrow">{view === "confirm" ? "送信前の最終確認" : "LINEから登録・更新"}</span><h1>{view === "confirm" ? "入力内容をご確認ください" : screen.linked ? "登録情報を更新" : "稼働者情報の登録"}</h1><p>{view === "confirm" ? "内容を確認して、申請を送信してください。" : screen.linked ? "登録済みの情報を表示しています。変更する項目と、未登録の必須項目を入力してください。" : "お名前・連絡先・住所をご入力ください。管理者が確認してから登録します。"}</p></div>
          <aside className="lr-privacy"><ShieldCheck size={18} aria-hidden="true" /><div><strong>個人情報の取り扱い</strong><p>{REGISTRATION_PRIVACY_NOTICE}</p></div></aside>
          {notice ? <div className="lr-notice" role="status"><Clock3 size={18} /><p>{notice}</p></div> : null}
          {view === "input" ? <form noValidate onSubmit={(event) => { event.preventDefault(); confirmInput(); }}>
            <section className="lr-card"><div className="lr-section-heading"><span><UserRound size={19} /></span><div><h2>お名前・生年月日</h2><p>ご本人の情報を入力してください</p></div></div><div className="lr-fields"><div className="lr-pair">{renderField("last_name")}{renderField("first_name")}</div><div className="lr-pair">{renderField("last_name_furigana")}{renderField("first_name_furigana")}</div>{renderField("birth_date")}</div></section>
            {screen.baseline && (!screen.baseline.first_name || !screen.baseline.first_name_furigana) ? <p className="lr-notice">保存されている氏名に区切りがない場合は姓の欄に表示しています。姓・名とふりがなを分けて入力してください。</p> : null}
            <section className="lr-card"><div className="lr-section-heading"><span><Phone size={19} /></span><div><h2>連絡先</h2><p>お仕事のご案内や業務連絡に使用します</p></div></div><div className="lr-fields">{renderField("phone")}{renderField("email")}</div></section>
            <section className="lr-card"><div className="lr-section-heading"><span><MapPin size={19} /></span><div><h2>住所・アクセス</h2><p>住所を変更する場合は、郵便番号から番地まで入力してください</p></div></div><div className="lr-fields">{renderField("postal_code")}{renderField("prefecture")}{renderField("address1")}{renderField("address2")}<div className="lr-divider" />{renderField("nearest_station")}{renderField("station_walk_minutes")}<AdditionalStationFields value={screen.input.additional_stations} disabled={holdingSubmission} error={fieldErrors.additional_stations} onChange={(additional_stations) => {
              setScreen((current) => ({ ...current, input: { ...current.input, additional_stations }, error: "" }));
              setFieldErrors((current) => ({ ...current, additional_stations: undefined }));
            }} /></div></section>
            <section className="lr-card"><div className="lr-section-heading"><span><Phone size={19} /></span><div><h2>緊急連絡先</h2><p>緊急時に連絡できる方をご入力ください</p></div></div><div className="lr-fields">{renderField("emergency_contact_phone")}{renderField("emergency_contact_name")}{renderField("emergency_contact_relationship")}{screen.linked ? <p className="lr-hint">変更する場合は、電話番号・お名前・関係をまとめて入力してください。</p> : null}</div></section>
            {screen.error ? <div className="lr-error" role="alert">{screen.error}</div> : null}
            {screen.message ? <div className="lr-notice" role="status">{screen.message}</div> : null}
            {holdingSubmission ? <p className="lr-hint">直前の送信内容を保持しています。内容を変える場合は「別の内容で申請する」を選んでください。</p> : null}
            <div className="lr-action-bar"><button className="lr-button lr-primary" type="submit" disabled={sending || postalLoading}>{postalLoading ? "住所を検索しています…" : "入力内容を確認する"}<ArrowRight size={18} /></button><p>確認画面で内容を確認してから送信できます</p></div>
          </form> : <>
            <section className="lr-card lr-confirm-card"><h2>申請する内容</h2><dl>{fields.filter((field) => (screen.baseline ? Object.prototype.hasOwnProperty.call(lineRegistrationPayload(screen.input, screen.linked, screen.baseline), field.key) : screen.input[field.key].trim())).map((field) => <div key={field.key}><dt>{field.label}</dt><dd>{field.key === "additional_stations" ? showAdditionalStations(screen.input[field.key]) : field.key === "station_walk_minutes" ? `徒歩${screen.input[field.key]}分` : screen.input[field.key]}</dd></div>)}</dl>{screen.linked ? <p className="lr-hint">表示のない項目は、現在の登録内容を変更しません。</p> : null}</section>
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
