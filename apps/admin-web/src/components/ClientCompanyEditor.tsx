import { useEffect, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError, updateClientCompany } from "../lib/api/client";
import { lookupPostalAddress, normalizePostalCode } from "../lib/postalAddress";
import type { ClientListItem } from "../types/api";
import { ProfileDialog } from "./ProfileDialog";

const companyFields = ["name", "code", "phone", "postal_code", "address", "notes"] as const;
type CompanyForm = Record<typeof companyFields[number], string>;

function formFromClient(client: ClientListItem): CompanyForm {
  return Object.fromEntries(companyFields.map((field) => [field, client[field] ?? ""])) as CompanyForm;
}

export function ClientCompanyEditor({ client, onClose, onSaved }: {
  client: ClientListItem;
  onClose: () => void;
  onSaved: (client: ClientListItem) => Promise<void>;
}) {
  const [form, setForm] = useState(() => formFromClient(client));
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [postalMessage, setPostalMessage] = useState("");
  const [postalChoices, setPostalChoices] = useState<string[]>([]);
  const baseline = useRef(formFromClient(client));
  const postalTouched = useRef(false);
  const lastAutoAddress = useRef("");

  const save = useMutation({
    mutationFn: () => {
      const values = { ...form, name: form.name.trim(), postal_code: normalizePostalCode(form.postal_code) };
      const changes: Partial<Record<typeof companyFields[number], string | null>> = {};
      for (const field of companyFields) {
        if (values[field] !== baseline.current[field]) changes[field] = values[field] || null;
      }
      return updateClientCompany(client.id, changes as Parameters<typeof updateClientCompany>[1]);
    },
    onSuccess: async (updated) => {
      baseline.current = formFromClient(updated);
      setForm(baseline.current);
      setError("");
      setMessage("企業情報を更新しました");
      await onSaved(updated);
    },
    onError: (caught) => {
      setMessage("");
      setError(caught instanceof ApiError ? caught.message : "企業情報の更新に失敗しました");
    },
  });

  useEffect(() => {
    setPostalChoices([]);
    setPostalMessage("");
    if (!postalTouched.current || save.isPending) return;
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
          setForm((current) => !current.address || current.address === previous ? { ...current, address: addresses[0] } : current);
          lastAutoAddress.current = addresses[0];
          setPostalChoices(addresses);
          setPostalMessage("住所候補を取得しました。入力済み住所を変更する場合は候補を選択し、番地・建物名を確認してください。");
        } else if (addresses.length > 1) {
          setPostalChoices(addresses);
          setPostalMessage("住所候補を選択してください。");
        } else setPostalMessage("住所が見つかりませんでした。住所を直接入力してください。");
      } catch {
        if (!controller.signal.aborted) setPostalMessage("住所を取得できませんでした。住所を直接入力してください。");
      }
    }, 400);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [form.postal_code, save.isPending]);

  function change(field: keyof CompanyForm, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setMessage("");
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (!form.name.trim()) { setError("企業名を入力してください"); return; }
    if (form.postal_code && !/^[0-9]{7}$/.test(normalizePostalCode(form.postal_code))) {
      setError("郵便番号は7桁で入力してください"); return;
    }
    save.mutate();
  }

  return <ProfileDialog title={`${client.name}の企業情報を編集`} onClose={() => { if (!save.isPending) onClose(); }}>
    <form className="master-form" onSubmit={submit} style={{ display: "grid", gap: ".75rem" }}>
      <fieldset disabled={save.isPending} style={{ margin: 0, padding: ".75rem", border: "1px solid #a8bace", borderRadius: 9, minWidth: 0 }}>
        <legend>企業情報</legend>
        <div className="master-form-grid">
          <label>企業名<input required maxLength={200} value={form.name} onChange={(e) => change("name", e.target.value)} /></label>
          <label>コード<input maxLength={50} value={form.code} onChange={(e) => change("code", e.target.value)} /></label>
          <label>会社電話番号<input type="tel" maxLength={20} value={form.phone} onChange={(e) => change("phone", e.target.value)} /></label>
          <label>郵便番号<input inputMode="numeric" autoComplete="postal-code" value={form.postal_code} onChange={(e) => { postalTouched.current = true; change("postal_code", e.target.value); }} /></label>
        </div>
        {postalMessage && <p role="status">{postalMessage}</p>}
        {postalChoices.map((address) => <button key={address} type="button" className="ghost-button" onClick={() => { change("address", address); lastAutoAddress.current = address; setPostalChoices([]); }}>{address}</button>)}
        <label style={{ marginTop: ".75rem" }}>住所<textarea aria-label="住所" rows={3} value={form.address} onChange={(e) => change("address", e.target.value)} /></label>
        <label style={{ marginTop: ".75rem" }}>社内メモ<textarea aria-label="社内メモ" rows={3} value={form.notes} onChange={(e) => change("notes", e.target.value)} /></label>
      </fieldset>
      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap" }}>
        <button type="submit" className="primary-button master-add-button" disabled={save.isPending || !form.name.trim()}>{save.isPending ? "更新中..." : "企業情報を更新"}</button>
        <button type="button" className="ghost-button" disabled={save.isPending} onClick={onClose}>閉じる</button>
      </div>
    </form>
  </ProfileDialog>;
}
