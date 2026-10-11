import { useEffect, useState } from "react";

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

  if (phase === "checking" && !screen.error) {
    return (
      <div className="public-form-page">
        <section className="panel-card">
          <h1>稼働者登録</h1>
          <p>確認しています。</p>
        </section>
      </div>
    );
  }

  if (phase !== "form") {
    return (
      <div className="public-form-page">
        <section className="panel-card">
          <h1>稼働者登録</h1>
          <p>{screen.error || "LINEからの登録は受け付けていません"}</p>
        </section>
      </div>
    );
  }

  return (
    <div className="public-form-page">
      <section className="panel-card" style={{ display: "grid", gap: "0.75rem" }}>
        <h1>稼働者登録</h1>
        <p style={{ margin: 0 }}>
          {screen.linked
            ? "変える項目だけ入力します。空欄は今の登録を消しません。"
            : "氏名、ふりがな、電話、生年月日、住所を入力します。"}
        </p>
        {notice ? <p style={{ margin: 0 }}>{notice}</p> : null}
        {fields.map((field) => (
          <label key={field.key} style={{ display: "grid", gap: "0.25rem" }}>
            {field.label}
            <input
              type={field.type ?? "text"}
              value={screen.input[field.key]}
              readOnly={holdingSubmission}
              onChange={(event) =>
                setScreen((current) => ({
                  ...current,
                  input: { ...current.input, [field.key]: event.target.value },
                }))
              }
            />
          </label>
        ))}
        {screen.message ? <p style={{ margin: 0 }}>{screen.message}</p> : null}
        {screen.error ? <p style={{ margin: 0 }}>{screen.error}</p> : null}
        {holdingSubmission ? (
          <p style={{ margin: 0 }}>再送は、直前に送った内容です。内容を変えるときは、別の申請にしてください。</p>
        ) : null}
        {screen.needsReauth ? (
          lineLoginExpired(screen.error) ? (
            <button type="button" onClick={() => void reopenLine()} disabled={sending}>
              LINEを開き直す
            </button>
          ) : (
            <button type="button" onClick={() => void reauthenticate()} disabled={sending}>
              {sending ? "確認中..." : "本人確認をやり直す"}
            </button>
          )
        ) : (
          <button type="button" onClick={() => void send()} disabled={sending}>
            {sending ? "送信中..." : "申請を送る"}
          </button>
        )}
        {holdingSubmission ? (
          <button type="button" onClick={discardSubmission}>
            別の内容で申請する
          </button>
        ) : null}
      </section>
    </div>
  );
}
