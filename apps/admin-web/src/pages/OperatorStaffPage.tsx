import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { ProfileDialog } from "../components/ProfileDialog";
import { OperatorInvitationDialog } from "../components/OperatorInvitationDialog";
import { OperatorAccessPanel } from "../components/OperatorAccessPanel";
import { ApiError, getOperatorStaff, issueOperatorLineCode, revokeOperatorLine, saveOperatorStaff } from "../lib/api/client";
import { alertApp, confirmApp, promptApp } from "../lib/appDialog";
import { MANAGEMENT_ROLES, type OperatorStaffItem, type OperatorStaffWrite } from "../types/operatorStaff";

const EMPTY: OperatorStaffWrite = { name: "", phone: null, email: null, can_drive: null, smoking_area_ok: null, emergency_contact_name: null, emergency_contact_phone: null, emergency_contact_relationship: null, management_roles: [], is_active: true, notes: null };
const message = (error: unknown) => error instanceof ApiError ? error.message : "処理に失敗しました";
function toForm(item: OperatorStaffItem): OperatorStaffWrite {
  const { id: _id, line_linked: _line, line_display_name: _name, line_linked_at: _at, ...profile } = item;
  return profile;
}

export function OperatorStaffPage() {
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<OperatorStaffItem | null>(null);
  const [open, setOpen] = useState(false);
  const [invitationOpen, setInvitationOpen] = useState(false);
  const [form, setForm] = useState<OperatorStaffWrite>(EMPTY);
  const [baseline, setBaseline] = useState(JSON.stringify(EMPTY));
  const [error, setError] = useState("");
  const [code, setCode] = useState<{ code: string; expires_at: string; instruction: string } | null>(null);
  const list = useQuery({ queryKey: ["operator-staff", search, page], queryFn: () => getOperatorStaff({ search, offset: page * 30, limit: 30 }), refetchInterval: 30000 });
  const invalidate = () => Promise.all([client.invalidateQueries({ queryKey: ["operator-staff"] }), client.invalidateQueries({ queryKey: ["vanzai-staff-page"] })]);
  const save = useMutation({ mutationFn: () => saveOperatorStaff(form, selected?.id), onSuccess: async (item) => {
    const next = toForm(item);
    setSelected(item); setForm(next); setBaseline(JSON.stringify(next)); setError("");
    await invalidate(); await alertApp({ title: "保存完了", message: selected ? "情報を更新しました" : "運営スタッフを登録しました" });
  }, onError: (e) => setError(message(e)) });
  const issue = useMutation({ mutationFn: () => issueOperatorLineCode(selected!.id), onSuccess: (value) => { setCode(value); setError(""); }, onError: (e) => setError(message(e)) });
  const unlink = useMutation({ mutationFn: (reason: string) => revokeOperatorLine(selected!.id, reason), onSuccess: async () => { setCode(null); setError(""); await invalidate(); }, onError: (e) => setError(message(e)) });
  const current = (list.data?.items ?? []).find((item) => item.id === selected?.id) ?? selected;
  function edit(item: OperatorStaffItem | null) {
    const next = item ? toForm(item) : { ...EMPTY, management_roles: [] };
    setForm(next); setBaseline(JSON.stringify(next)); setSelected(item); setError(""); setCode(null); setOpen(true);
  }
  async function close() {
    if (save.isPending || issue.isPending || unlink.isPending) return;
    if (JSON.stringify(form) !== baseline && !await confirmApp({ title: "未保存の情報", message: "保存していない変更があります。閉じますか？", confirmLabel: "閉じる" })) return;
    setOpen(false); setCode(null);
  }
  function field(key: "name" | "phone" | "email" | "emergency_contact_name" | "emergency_contact_phone" | "emergency_contact_relationship", label: string, type = "text") {
    return <label className="order-field">{label}<input type={type} value={form[key] ?? ""} required={key === "name"} maxLength={key.includes("phone") ? 20 : key === "email" ? 255 : key === "emergency_contact_name" ? 200 : key === "emergency_contact_relationship" ? 50 : 100} onChange={(e) => setForm({ ...form, [key]: e.target.value || (key === "name" ? "" : null) })} /></label>;
  }
  return <div className="page-stack">
    <PageHeader title="運営スタッフ登録・一覧" description="運営スタッフの連絡先、担当ロール、公式LINEの本人紐付けを管理します。" />
    <section className="surface"><div className="filter-bar"><label>氏名で検索<input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} /></label><button className="btn btn-primary create-button" type="button" onClick={() => edit(null)}>運営スタッフを登録</button><button className="btn btn-ghost" style={{ borderColor: "#8b5bb5", color: "#8b5bb5" }} type="button" onClick={() => setInvitationOpen(true)}>LINE登録の招待リンク</button></div></section>
    {invitationOpen && <OperatorInvitationDialog onClose={() => setInvitationOpen(false)} />}
    {list.isError && <ErrorState title="運営スタッフを取得できませんでした" description={message(list.error)} />}
    {list.isLoading && <p>読み込み中...</p>}
    {list.data && <><DataTable rows={list.data.items} getRowKey={(row) => row.id} emptyTitle="運営スタッフが登録されていません" emptyDescription="運営スタッフを登録してください。" columns={[
      { key: "name", header: "氏名", render: (row) => row.name },
      { key: "contact", header: "連絡先", render: (row) => <>{row.phone ?? "—"}<br />{row.email}</> },
      { key: "roles", header: "付与ロール", render: (row) => row.management_roles.join("、") || "未設定" },
      { key: "line", header: "LINE", render: (row) => row.line_linked ? row.line_display_name || "紐付け済み（表示名未取得）" : "未紐付け" },
      { key: "active", header: "状態", render: (row) => row.is_active ? "有効" : "無効" },
      { key: "edit", header: "操作", render: (row) => <button type="button" className="btn btn-ghost" onClick={() => edit(row)}>内容確認・更新</button> },
    ]} /><PaginationBar page={page} total={list.data.total} limit={30} onPrevious={() => setPage(page - 1)} onNext={() => setPage(page + 1)} /></>}
    {open && <ProfileDialog title={selected ? "運営スタッフの内容確認・更新" : "運営スタッフ登録"} className="operator-profile-dialog" onClose={() => void close()}>
      <form onSubmit={(e) => { e.preventDefault(); setError(""); save.mutate(); }}>
        <fieldset className="operator-profile-fields" disabled={save.isPending}>
          <legend>登録情報</legend><div className="operator-profile-grid">{field("name", "氏名")}{field("phone", "電話番号", "tel")}{field("email", "メールアドレス", "email")}
          <label className="order-field">運転可否<select value={form.can_drive == null ? "" : String(form.can_drive)} onChange={(e) => setForm({ ...form, can_drive: e.target.value === "" ? null : e.target.value === "true" })}><option value="">未確認</option><option value="true">運転可</option><option value="false">運転不可</option></select></label>
          <label className="order-field">喫煙可否<select value={form.smoking_area_ok == null ? "" : String(form.smoking_area_ok)} onChange={(e) => setForm({ ...form, smoking_area_ok: e.target.value === "" ? null : e.target.value === "true" })}><option value="">未確認</option><option value="true">可</option><option value="false">不可</option></select></label>
          {field("emergency_contact_name", "緊急連絡先の氏名")}{field("emergency_contact_phone", "緊急連絡先の電話番号", "tel")}{field("emergency_contact_relationship", "緊急連絡先の続柄")}</div>
          <fieldset><legend>付与ロール</legend><div className="operator-role-options">{MANAGEMENT_ROLES.map((role) => <label key={role}><input type="checkbox" checked={form.management_roles.includes(role)} onChange={(e) => setForm({ ...form, management_roles: e.target.checked ? [...form.management_roles, role] : form.management_roles.filter((r) => r !== role) })} />{role}</label>)}</div><p className="order-field-hint">ロールを付与・保存します。画面の表示項目や操作権限への反映は、今後対応します。</p></fieldset>
          <label className="order-field">備考<textarea rows={2} value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value || null })} /></label>
          <label className="operator-active-check"><input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />有効</label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="operator-form-actions"><button type="submit" className={`btn btn-primary operator-save-button${selected ? "" : " create-button"}`}>{save.isPending ? "保存中..." : selected ? "更新" : "登録"}</button>
          {selected && form.profile_revision !== current?.profile_revision && <button type="button" className="btn btn-ghost" onClick={() => current && edit(current)}>最新の内容を読み込む</button>}
          </div>
        </fieldset>
      </form>
      {selected && <div className="operator-account-panels"><section className="order-draft-section operator-account-card"><h4>公式LINEの本人紐付け</h4><p>運営に関する連絡の送付先です。本人が公式LINEへコードを送ると紐付けが完了します。</p>
        {current?.line_linked ? <><p>LINE表示名：{current.line_display_name || "未取得"}</p><button type="button" className="btn btn-ghost operator-unlink-button" disabled={unlink.isPending} onClick={async () => { const reason = await promptApp({ title: "LINE紐付け解除", message: "解除すると運営の連絡を受け取れなくなります。解除理由を入力してください。", confirmLabel: "解除" }); if (reason?.trim()) unlink.mutate(reason.trim()); }}>紐付けを解除</button></> : <button type="button" className="btn btn-ghost operator-code-button" disabled={issue.isPending || !current?.is_active} onClick={() => issue.mutate()}>LINE紐付けコードを発行</button>}
        {code && !current?.line_linked && <div className="surface"><strong>{code.code}</strong><p>{code.instruction}</p><p>期限：{new Date(code.expires_at).toLocaleString("ja-JP")}</p></div>}
      </section><OperatorAccessPanel staffId={selected.id} /></div>}
    </ProfileDialog>}
  </div>;
}
