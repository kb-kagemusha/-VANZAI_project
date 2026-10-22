import { useQuery } from "@tanstack/react-query";
import { getClients, getAllClientStaff } from "../lib/api/client";
import type { ClientListItem } from "../types/api";
import type { InternalOrderSource } from "../types/orderRequest";

async function allClients() {
  const result: ClientListItem[] = [];
  for (let offset = 0; ; offset += 200) {
    const page = await getClients({ offset, limit: 200, sort_by: "name", sort_order: "asc" });
    result.push(...page.items);
    if (!page.items.length || result.length >= page.total) return result;
  }
}

async function allContacts(clientId: string) {
  return (await getAllClientStaff(clientId, true)).items;
}

export function OrderInternalSourceEditor({ value, disabled, onChange }: { value: InternalOrderSource | null; disabled: boolean; onChange: (source: InternalOrderSource | null) => void }) {
  const clients = useQuery({ queryKey: ["order-source-clients"], queryFn: allClients, enabled: !disabled });
  const contacts = useQuery({ queryKey: ["order-source-contacts", value?.client_id], queryFn: () => allContacts(value!.client_id), enabled: !disabled && Boolean(value?.client_id) });
  const clientRows = clients.data ?? [];
  const staffRows = contacts.data ?? [];
  const selectedClient = clientRows.find((row) => row.id === value?.client_id);
  const selectedStaff = staffRows.find((row) => row.id === value?.client_staff_id);
  return <section className="order-draft-section order-internal-source">
    <h4>発注元・担当者（内部管理）</h4>
    <p className="order-field-hint">稼働者へ送る本文・LINE・PDFには含めません。会社を変更すると担当者の選択を解除します。</p>
    <div className="order-draft-grid">
      <label className="order-field order-span-6">発注元
        <select value={value?.client_id ?? ""} disabled={disabled || clients.isLoading || clients.isError} onChange={(event) => {
          const row = clientRows.find((item) => item.id === event.target.value);
          onChange(row ? { client_id: row.id, client_staff_id: null, client_name: row.name, client_phone: row.phone } : null);
        }}>
          <option value="">未設定</option>
          {value && !selectedClient && <option value={value.client_id}>{value.client_name ?? "保存済みの発注元"}（保存済み）</option>}
          {clientRows.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
      <label className="order-field order-span-6">担当者（発注元）
        <select value={value?.client_staff_id ?? ""} disabled={disabled || !value?.client_id || contacts.isLoading || contacts.isError} onChange={(event) => {
          const row = staffRows.find((item) => item.id === event.target.value);
          onChange(value ? { ...value, client_staff_id: row?.id ?? null, staff_name: row?.name ?? null, staff_phone: row?.phone ?? null } : null);
        }}>
          <option value="">なし</option>
          {value?.client_staff_id && !selectedStaff && <option value={value.client_staff_id}>{value.staff_name ?? "保存済みの担当者"}（保存済み）</option>}
          {staffRows.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
        </select>
      </label>
    </div>
    {value && <p className="order-field-hint">会社電話：{selectedClient?.phone ?? value.client_phone ?? "未登録"}　担当者電話：{selectedStaff?.phone ?? value.staff_phone ?? "未登録"}</p>}
    {(clients.isError || contacts.isError) && <p className="form-error">クライアント・担当者を取得できませんでした。画面を開き直してください。</p>}
    {!disabled && value?.client_id && contacts.isSuccess && !staffRows.length && <p className="order-field-hint">担当者が未登録です。マスタ一覧のクライアント「担当者管理」から追加してください。</p>}
  </section>;
}
