import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { PageHeader } from "../components/PageHeader";
import { ClientAddressFields } from "../components/ClientAddressFields";
import { ApiError } from "../lib/api/client";
import { getCompanyProfile, saveCompanyProfile, type CompanyProfile } from "../lib/orderBillingApi";
import { lookupPostalAddress, normalizePostalCode } from "../lib/postalAddress";

/** 会社情報（0.49.8、DEC-082）。請求書の発行元・振込先・支払期限に使う。 */
export function CompanyProfilePage() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["company-profile"], queryFn: getCompanyProfile });
  const [form, setForm] = useState<CompanyProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [postalMessage, setPostalMessage] = useState("");
  const [postalChoices, setPostalChoices] = useState<string[]>([]);
  const postalTouched = useRef(false);
  const lastAutoAddress = useRef("");

  useEffect(() => { if (query.data && !form) setForm(query.data); }, [query.data, form]);

  useEffect(() => {
    setPostalChoices([]);
    setPostalMessage("");
    if (!form || !postalTouched.current || busy) return;
    const postal = normalizePostalCode(form.postal_code);
    if (!/^[0-9]{7}$/.test(postal)) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const choices = await lookupPostalAddress(postal, controller.signal);
        if (controller.signal.aborted) return;
        const addresses = choices.map((choice) => choice.prefecture + choice.address);
        if (addresses.length === 1) {
          const previous = lastAutoAddress.current;
          setForm((current) => current && (!current.address || current.address === previous) ? { ...current, address: addresses[0] } : current);
          lastAutoAddress.current = addresses[0];
          setPostalChoices(addresses);
          setPostalMessage("住所候補を取得しました。番地・建物名を確認して入力してください。");
        } else if (addresses.length > 1) {
          setPostalChoices(addresses);
          setPostalMessage("住所候補を選択してください。");
        } else setPostalMessage("住所が見つかりませんでした。住所を直接入力してください。");
      } catch {
        if (!controller.signal.aborted) setPostalMessage("住所を取得できませんでした。住所を直接入力してください。");
      }
    }, 400);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [form?.postal_code, busy]); // eslint-disable-line react-hooks/exhaustive-deps

  function change<K extends keyof CompanyProfile>(key: K, value: CompanyProfile[K]) {
    setForm((current) => current ? { ...current, [key]: value } : current);
    setMessage("");
  }

  const changed = !!form && !!query.data && (Object.keys(form) as (keyof CompanyProfile)[]).some((key) => form[key] !== query.data![key]);

  async function save() {
    if (!form || busy || !form.name.trim()) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await saveCompanyProfile(form);
      queryClient.setQueryData(["company-profile"], saved);
      await queryClient.invalidateQueries({ queryKey: ["order-billing"] });
      setForm(saved);
      postalTouched.current = false;
      setMessage("保存しました。これから作成・発行する請求書に反映します。");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "保存できませんでした。時間をおいて再度お試しください。");
    } finally {
      setBusy(false);
    }
  }

  return <div className="page-stack company-profile-page">
    <PageHeader title="会社情報" eyebrow="その他" description="請求書の発行元として、会社名・住所・電話番号などを記載します。発行済みの請求書は、発行した時点の内容のまま変わりません。" />
    {query.isError ? <p className="form-error" role="alert">会社情報を取得できませんでした。</p> : null}
    {form ? <section className="card company-profile-card">
      <div className="order-billing-settings-grid">
        <label className="order-field">会社の正式名称（必須）<input maxLength={200} disabled={busy} value={form.name} onChange={(e) => change("name", e.target.value)} /></label>
        <label className="order-field">代表者名<input maxLength={100} disabled={busy} placeholder="例：代表取締役 山田太郎" value={form.representative} onChange={(e) => change("representative", e.target.value)} /></label>
        <div style={{ gridColumn: "1 / -1" }}>
          <ClientAddressFields
            postalCode={form.postal_code}
            address={form.address}
            onPostalChange={(value) => { postalTouched.current = true; change("postal_code", value); }}
            onAddressChange={(value) => change("address", value)}
            message={postalMessage}
            choices={postalChoices}
            onChoose={(address) => { change("address", address); lastAutoAddress.current = address; setPostalChoices([]); }}
          />
        </div>
        <label className="order-field">電話番号<input maxLength={30} inputMode="tel" autoComplete="tel" disabled={busy} placeholder="例：03-1234-5678" value={form.phone} onChange={(e) => change("phone", e.target.value)} /></label>
        <label className="order-field">メールアドレス<input maxLength={200} type="email" autoComplete="email" disabled={busy} value={form.email} onChange={(e) => change("email", e.target.value)} /></label>
        <label className="order-field">登録番号（インボイス）<input maxLength={50} disabled={busy} placeholder="例：T1234567890123" value={form.registration_number} onChange={(e) => change("registration_number", e.target.value)} /></label>
        <label className="order-field">支払期限・条件<textarea rows={2} maxLength={1000} placeholder="例：請求月の翌月末まで" disabled={busy} value={form.payment_terms} onChange={(e) => change("payment_terms", e.target.value)} /></label>
        <label className="order-field" style={{ gridColumn: "1 / -1" }}>振込先<textarea rows={3} maxLength={2000} placeholder="銀行名・支店名・口座種別・口座番号・口座名義など" disabled={busy} value={form.bank_details} onChange={(e) => change("bank_details", e.target.value)} /></label>
      </div>
      <p className="order-field-hint">請求書への載り方：会社名・代表者名・住所・電話番号・メールアドレス・登録番号は発行元の欄に、支払期限・条件と振込先は依頼元別の月次請求書の下に載ります。空の項目は載りません。</p>
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      {message ? <p role="status">{message}</p> : null}
      <div className="company-profile-actions">
        <button type="button" className="btn create-button" disabled={busy || !changed || !form.name.trim()} onClick={() => void save()}>保存する</button>
      </div>
    </section> : null}
  </div>;
}
