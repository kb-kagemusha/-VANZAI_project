import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "../components/PageHeader";
import { DataTable } from "../components/DataTable";
import { ApiError, apiFetch } from "../lib/api/client";
import { formatRole } from "../lib/formatters";
import type { UserRole } from "../types/api";

type Account = { id: string; username: string; display_name: string | null; email: string; role: UserRole; is_active: boolean };
type RolePolicy = { role: UserRole; permissions: string[]; default_permissions: string[]; editable: boolean };
const ROLES: UserRole[] = ["admin", "ops", "accounting", "site_manager"];
const LABELS: Record<string, string> = {
  dashboard: "ダッシュボード", master: "マスタ", price: "単価", project: "案件", shift: "シフト枠",
  assignment: "配置", actual: "実績", availability: "出勤可能日", csv: "CSV", invoice: "請求",
  payout: "支払", soft_close: "Soft Close", hard_close: "Hard Close", expense: "経費",
  incentive: "インセンティブ", audit_log: "監査ログ", notice: "スタッフ通知", ocr: "OCR・在庫照合",
  order: "発注依頼書", registration: "登録申請",
};
const ACTIONS: Record<string, string> = { read: "閲覧", write: "編集", generate: "生成", issue: "発行", correct: "訂正",
  approve: "承認", submit: "提出", import: "取込", calculate: "計算", release: "解除", response: "回答", remind: "催促・要対応通知" };
function permissionLabel(value: string) {
  if (value === "soft_close" || value === "hard_close") return LABELS[value];
  const index = value.lastIndexOf("_");
  return `${LABELS[value.slice(0, index)] ?? value.slice(0, index)}：${ACTIONS[value.slice(index + 1)] ?? value.slice(index + 1)}`;
}

export function AccessManagementPage() {
  const client = useQueryClient();
  const [tab, setTab] = useState<"users" | "roles">("users");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [editRole, setEditRole] = useState<UserRole>("site_manager");
  const [active, setActive] = useState(true);
  const [reason, setReason] = useState("");
  const [role, setRole] = useState<UserRole>("site_manager");
  const [selected, setSelected] = useState<string[]>([]);
  const [policyReason, setPolicyReason] = useState("");
  const users = useQuery({ queryKey: ["access-users", search, page], queryFn: () => apiFetch<{items: Account[]; total: number}>(`/api/access/users?search=${encodeURIComponent(search)}&offset=${page * 50}&limit=50`) });
  const policies = useQuery({ queryKey: ["access-roles"], queryFn: () => apiFetch<{available_permissions: string[]; roles: RolePolicy[]}>("/api/access/roles") });
  const policy = policies.data?.roles.find(item => item.role === role);
  useEffect(() => { setSelected(policy?.permissions ?? []); setPolicyReason(""); }, [role, policy]);

  function togglePermission(permission: string, checked: boolean) {
    const read = permission.slice(0, permission.lastIndexOf("_")) + "_read";
    setSelected(current => {
      if (checked) return Array.from(new Set([...current, permission, ...(policies.data?.available_permissions.includes(read) ? [read] : [])]));
      if (permission.endsWith("_read")) {
        const prefix = permission.slice(0, -4);
        return current.filter(item => !item.startsWith(prefix));
      }
      return current.filter(item => item !== permission);
    });
  }

  async function save(path: string, method: string, body: unknown, done: () => void) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiFetch(path, { method, body: JSON.stringify(body) });
      await client.invalidateQueries({ queryKey: ["access-users"] });
      await client.invalidateQueries({ queryKey: ["access-roles"] });
      setMessage("保存しました"); done();
    } catch (err) { setError(err instanceof ApiError ? err.message : "保存に失敗しました"); }
    finally { setBusy(false); }
  }

  return <div className="page-stack">
    <PageHeader eyebrow="管理者設定" title="ID・権限管理" description="全体管理者がログインIDを作成し、役割と閲覧・操作権限を設定します。" />
    <div className="button-row" role="group" aria-label="管理対象">
      <button className={tab === "users" ? "primary-button" : "ghost-button"} onClick={() => setTab("users")}>ログインID</button>
      <button className={tab === "roles" ? "primary-button" : "ghost-button"} onClick={() => setTab("roles")}>役割ごとの権限</button>
    </div>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {(users.isError || policies.isError) && <p role="alert">管理情報を取得できませんでした。</p>}
    {tab === "users" ? <>
      <form className="card access-form" onSubmit={event => {
        event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
        void save("/api/access/users", "POST", Object.fromEntries(values.entries()), () => form.reset());
      }}>
        <h2>ログインIDを作成</h2>
        <div className="access-grid">
          <label>ログインID<input name="username" required maxLength={100} pattern="[A-Za-z0-9_.@\-]+" autoComplete="off" /></label>
          <label>表示名<input name="display_name" required maxLength={100} /></label>
          <label>メールアドレス<input name="email" type="email" required maxLength={255} /></label>
          <label>初期パスワード<input name="password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" /></label>
          <label>役割<select name="role" defaultValue="site_manager">{ROLES.map(item => <option key={item} value={item}>{formatRole(item)}</option>)}</select></label>
        </div>
        <p>8文字以上の初期パスワードを設定し、本人に安全な方法で伝えてください。本人はプロフィールから変更できます。</p>
        <div><button className="primary-button" disabled={busy}>IDを作成</button></div>
      </form>
      <label>IDを検索<input value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} placeholder="ID・表示名・メール" /></label>
      {users.isLoading ? <p>読み込み中…</p> : <DataTable<Account> columns={[
        {key: "id", header: "ログインID", render: row => row.username},
        {key: "name", header: "表示名", render: row => row.display_name ?? "—"},
        {key: "email", header: "メール", render: row => row.email},
        {key: "role", header: "役割", render: row => formatRole(row.role)},
        {key: "status", header: "状態", render: row => row.is_active ? "有効" : "無効"},
        {key: "edit", header: "操作", render: row => <button onClick={() => {setEditing(row); setEditRole(row.role); setActive(row.is_active); setReason("");}}>権限・状態を変更</button>},
      ]} rows={users.data?.items ?? []} getRowKey={row => row.id} emptyTitle="IDがありません" emptyDescription="検索条件を変更してください。" />}
      <div className="button-row"><button disabled={page === 0} onClick={() => setPage(page - 1)}>前へ</button><span>{page + 1}ページ / 全{users.data?.total ?? 0}件</span><button disabled={(page + 1) * 50 >= (users.data?.total ?? 0)} onClick={() => setPage(page + 1)}>次へ</button></div>
      {editing && <form className="card access-form" onSubmit={e => { e.preventDefault(); void save(`/api/access/users/${editing.id}`, "PUT", {role: editRole, is_active: active, reason}, () => setEditing(null)); }}>
        <h2>{editing.username} の権限・状態</h2>
        <label>役割<select value={editRole} onChange={e => setEditRole(e.target.value as UserRole)}>{[...ROLES, "worker" as UserRole].map(item => <option key={item} value={item}>{formatRole(item)}</option>)}</select></label>
        <div className="button-row" role="group" aria-label="IDの状態"><button type="button" className={active ? "primary-button" : "ghost-button"} onClick={() => setActive(true)}>有効</button><button type="button" className={!active ? "primary-button" : "ghost-button"} onClick={() => setActive(false)}>無効</button></div>
        <label>変更理由<input required maxLength={500} value={reason} onChange={e => setReason(e.target.value)} /></label>
        <div className="button-row"><button className="primary-button" disabled={busy || !reason.trim()}>変更を保存</button><button type="button" onClick={() => setEditing(null)}>閉じる</button></div>
      </form>}
    </> : <form className="card access-form" onSubmit={e => {e.preventDefault(); void save(`/api/access/roles/${role}`, "PUT", {permissions: selected, reason: policyReason}, () => {});}}>
      <h2>役割ごとの閲覧・操作権限</h2>
      <p>変更は同じ役割の全IDに適用されます。閲覧と編集は別の権限です。編集を許可すると閲覧も選択し、閲覧を外すと同じ機能の操作も外します。全体管理者は全権限を保持します。</p>
      <label>役割<select value={role} onChange={e => setRole(e.target.value as UserRole)}>{ROLES.map(item => <option key={item} value={item}>{formatRole(item)}</option>)}</select></label>
      <fieldset disabled={busy || !policy?.editable} className="access-permissions"><legend>許可する機能</legend>
        {policies.data?.available_permissions.map(permission => <label key={permission}><input type="checkbox" checked={selected.includes(permission)} onChange={e => togglePermission(permission, e.target.checked)} />{permissionLabel(permission)}</label>)}
      </fieldset>
      {policy?.editable && <><label>変更理由<input required maxLength={500} value={policyReason} onChange={e => setPolicyReason(e.target.value)} /></label><div className="button-row"><button className="primary-button" disabled={busy || !policyReason.trim()}>この役割の権限を保存</button><button type="button" disabled={busy} onClick={() => setSelected(policy.default_permissions)}>初期設定を選び直す</button></div></>}
    </form>}
  </div>;
}
