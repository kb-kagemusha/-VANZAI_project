import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ApiError, getAllClientStaff, updateClientCompany } from "../lib/api/client";
import { lookupPostalAddress, normalizePostalCode } from "../lib/postalAddress";
import type { ClientListItem, ClientStaffItem } from "../types/api";
import { ProfileDialog } from "./ProfileDialog";
import { ClientAddressFields } from "./ClientAddressFields";

const companyFields = ["name", "code", "phone", "postal_code", "address", "notes"] as const;
type CompanyForm = Record<typeof companyFields[number], string>;
type ContactForm = { key: string; id?: string; name: string; role: string; phone: string; email: string };
const contactFields = ["name", "role", "phone", "email"] as const;

function contactForm(contact: ClientStaffItem): ContactForm {
  return { key: contact.id, id: contact.id, name: contact.name, role: contact.role ?? "", phone: contact.phone ?? "", email: contact.email ?? "" };
}

function formFromClient(client: ClientListItem): CompanyForm {
  return Object.fromEntries(companyFields.map((field) => [field, client[field] ?? ""])) as CompanyForm;
}

export function ClientCompanyEditor({ client, readOnly = false, onClose, onSaved }: {
  client: ClientListItem;
  readOnly?: boolean;
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
  const [contacts, setContacts] = useState<ContactForm[]>([]);
  const contactBaseline = useRef<ContactForm[]>([]);
  const contactsLoaded = useRef(false);
  const staffQuery = useQuery({ queryKey: ["client-staff", client.id], queryFn: () => getAllClientStaff(client.id) });

  useEffect(() => {
    if (!staffQuery.data || contactsLoaded.current) return;
    const rows = staffQuery.data.items.map(contactForm);
    if (!rows.length && client.contact_name) rows.push({ key: "legacy", name: client.contact_name, role: "", phone: "", email: client.contact_email ?? "" });
    setContacts(rows);
    contactBaseline.current = rows;
    contactsLoaded.current = true;
  }, [staffQuery.data, client.contact_name, client.contact_email]);

  const save = useMutation({
    mutationFn: () => {
      const values = { ...form, name: form.name.trim(), postal_code: normalizePostalCode(form.postal_code) };
      const changes: Partial<Record<typeof companyFields[number], string | null>> = {};
      for (const field of companyFields) {
        if (values[field] !== baseline.current[field]) changes[field] = values[field] || null;
      }
      const contactChanges = contacts.filter((contact) => {
        const original = contactBaseline.current.find((item) => item.id === contact.id);
        return !contact.id || !original || contactFields.some((field) => contact[field] !== original[field]);
      }).map((contact) => ({ ...(contact.id ? { id: contact.id } : {}), name: contact.name.trim(), role: contact.role.trim() || null, phone: contact.phone.trim() || null, email: contact.email.trim() || null }));
      return updateClientCompany(client.id, { ...changes, ...(contactChanges.length ? { contacts: contactChanges } : {}) } as Parameters<typeof updateClientCompany>[1]);
    },
    onSuccess: async (updated) => {
      baseline.current = formFromClient(updated);
      setForm(baseline.current);
      const rows = updated.contacts.map(contactForm);
      setContacts(rows);
      contactBaseline.current = rows;
      setError("");
      setMessage("企業情報・担当者を保存しました");
      await onSaved(updated);
    },
    onError: (caught) => {
      setMessage("");
      setError(caught instanceof ApiError ? caught.message : "保存に失敗しました。入力内容を確認して再度保存してください。");
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
    if (readOnly || !contactsLoaded.current || staffQuery.isError || save.isPending) return;
    setError("");
    if (!form.name.trim()) { setError("企業名を入力してください"); return; }
    if (form.postal_code && !/^[0-9]{7}$/.test(normalizePostalCode(form.postal_code))) {
      setError("郵便番号は7桁で入力してください"); return;
    }
    if (contacts.some((contact) => !contact.name.trim())) { setError("担当者の氏名を入力するか、未保存の担当者行を外してください"); return; }
    save.mutate();
  }

  function changeContact(key: string, field: typeof contactFields[number], value: string) {
    setContacts((current) => current.map((contact) => contact.key === key ? { ...contact, [field]: value } : contact));
    setMessage("");
  }

  return <ProfileDialog title={`${client.name}の${readOnly ? "詳細" : "編集"}`} onClose={() => { if (!save.isPending) onClose(); }}>
    <form className="master-form" onSubmit={submit} style={{ display: "grid", gap: ".75rem" }}>
      <fieldset disabled={save.isPending || readOnly} style={{ margin: 0, padding: ".75rem", border: "1px solid #a8bace", borderRadius: 9, minWidth: 0 }}>
        <legend>企業情報</legend>
        <div className="master-form-grid">
          <label>企業名<input required maxLength={200} value={form.name} onChange={(e) => change("name", e.target.value)} /></label>
          <label>コード<input maxLength={50} value={form.code} onChange={(e) => change("code", e.target.value)} /></label>
          <label>会社電話番号<input type="tel" maxLength={20} value={form.phone} onChange={(e) => change("phone", e.target.value)} /></label>
        </div>
        <ClientAddressFields postalCode={form.postal_code} address={form.address} onPostalChange={(value) => { postalTouched.current = true; change("postal_code", value); }} onAddressChange={(value) => change("address", value)} message={postalMessage} choices={postalChoices} onChoose={(address) => { change("address", address); lastAutoAddress.current = address; setPostalChoices([]); }} />
        <label style={{ marginTop: ".75rem" }}>社内メモ<textarea aria-label="社内メモ" rows={3} value={form.notes} onChange={(e) => change("notes", e.target.value)} /></label>
      </fieldset>
      <fieldset disabled={save.isPending} className="master-client-contacts" style={{ margin: 0, padding: ".75rem", border: "1px solid #a8bace", borderRadius: 9, minWidth: 0 }}>
        <legend>担当者</legend>
        {staffQuery.isLoading && <p role="status">担当者を読み込み中...</p>}
        {staffQuery.isError && <p role="alert">担当者を読み込めませんでした。<button type="button" className="ghost-button" onClick={() => void staffQuery.refetch()}>再読み込み</button></p>}
        {contacts.map((contact, index) => <fieldset key={contact.key} disabled={readOnly}>
          <legend>担当者 {index + 1}</legend>
          <div className="master-form-grid">
            <label>氏名<input aria-label={`担当者${index + 1}の氏名`} required maxLength={100} value={contact.name} onChange={(e) => changeContact(contact.key, "name", e.target.value)} /></label>
            <label>役職<input aria-label={`担当者${index + 1}の役職`} maxLength={100} value={contact.role} onChange={(e) => changeContact(contact.key, "role", e.target.value)} /></label>
            <label>電話番号<input aria-label={`担当者${index + 1}の電話番号`} type="tel" maxLength={20} value={contact.phone} onChange={(e) => changeContact(contact.key, "phone", e.target.value)} /></label>
            <label>メール<input aria-label={`担当者${index + 1}のメール`} type="email" maxLength={255} value={contact.email} onChange={(e) => changeContact(contact.key, "email", e.target.value)} /></label>
          </div>
          {!readOnly && !contact.id && <button type="button" className="ghost-button" onClick={() => setContacts((current) => current.filter((item) => item.key !== contact.key))}>未保存の担当者{index + 1}を外す</button>}
        </fieldset>)}
        {!readOnly && <button type="button" className="ghost-button" disabled={!contactsLoaded.current || staffQuery.isError} onClick={() => { setContacts((current) => [...current, { key: crypto.randomUUID(), name: "", role: "", phone: "", email: "" }]); setMessage(""); }}>担当者を追加</button>}
        {!staffQuery.isLoading && !staffQuery.isError && !contacts.length && <p>担当者は未登録です</p>}
      </fieldset>
      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap" }}>
        {!readOnly && <button type="submit" className="primary-button master-add-button" disabled={save.isPending || !form.name.trim() || staffQuery.isLoading || staffQuery.isError || !contactsLoaded.current}>{save.isPending ? "保存中..." : "保存する"}</button>}
        <button type="button" className="ghost-button" disabled={save.isPending} onClick={onClose}>閉じる</button>
      </div>
    </form>
  </ProfileDialog>;
}
