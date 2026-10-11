import { useEffect, useState } from "react";

import {
  ApiError,
  createLineRegistrationSession,
  getLineRegistrationEntry,
  getLineRegistrationForm,
  submitLineRegistration,
} from "../lib/api/client";
import {
  emptyLineRegistrationInput,
  idempotencyKeyAfterAttempt,
  lineRegistrationPayload,
  registrationInputAfterSubjectChange,
  type LineRegistrationInput,
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
  const [linked, setLinked] = useState(false);
  const [notice, setNotice] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [input, setInput] = useState<LineRegistrationInput>(emptyLineRegistrationInput);
  const [sending, setSending] = useState(false);

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
        memoryToken = session.token;
        setInput((current) => registrationInputAfterSubjectChange(memorySubject, session.subject_tag, current));
        memorySubject = session.subject_tag;
        setLinked(session.linked);
        const form = await getLineRegistrationForm(session.token);
        if (!active) return;
        setLinked(form.linked);
        setNotice(form.message);
        setPhase("form");
      })
      .catch((loadError) => {
        if (!active) return;
        if (loadError instanceof ApiError && loadError.status === 403) {
          setPhase("closed");
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "登録画面を開けませんでした。");
      });
    return () => {
      active = false;
    };
  }, []);

  async function send() {
    if (!memoryToken || sending) return;
    const key = memoryKey || crypto.randomUUID();
    memoryKey = key;
    setSending(true);
    setError("");
    setMessage("");
    try {
      const result = await submitLineRegistration(memoryToken, key, lineRegistrationPayload(input, linked));
      memoryKey = idempotencyKeyAfterAttempt(key, 200);
      setMessage(result.message);
      setNotice("");
    } catch (submitError) {
      const status = submitError instanceof ApiError ? submitError.status : "network";
      memoryKey = idempotencyKeyAfterAttempt(key, status);
      setError(submitError instanceof ApiError ? submitError.message : "送信できませんでした。もう一度送信してください。");
    } finally {
      setSending(false);
    }
  }

  if (phase === "checking" && !error) {
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
          <p>{error || "LINEからの登録は受け付けていません"}</p>
        </section>
      </div>
    );
  }

  return (
    <div className="public-form-page">
      <section className="panel-card" style={{ display: "grid", gap: "0.75rem" }}>
        <h1>稼働者登録</h1>
        <p style={{ margin: 0 }}>
          {linked
            ? "変える項目だけ入力します。空欄は今の登録を消しません。"
            : "氏名、ふりがな、電話、生年月日、住所を入力します。"}
        </p>
        {notice ? <p style={{ margin: 0 }}>{notice}</p> : null}
        {fields.map((field) => (
          <label key={field.key} style={{ display: "grid", gap: "0.25rem" }}>
            {field.label}
            <input
              type={field.type ?? "text"}
              value={input[field.key]}
              onChange={(event) => setInput((current) => ({ ...current, [field.key]: event.target.value }))}
            />
          </label>
        ))}
        {message ? <p style={{ margin: 0 }}>{message}</p> : null}
        {error ? <p style={{ margin: 0 }}>{error}</p> : null}
        <button type="button" onClick={() => void send()} disabled={sending}>
          {sending ? "送信中..." : "申請を送る"}
        </button>
      </section>
    </div>
  );
}
