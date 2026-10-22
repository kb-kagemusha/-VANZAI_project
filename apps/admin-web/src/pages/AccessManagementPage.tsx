import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "../components/PageHeader";
import { DataTable } from "../components/DataTable";
import { FormDialog } from "../components/FormDialog";
import { RolePermissionPicker } from "../components/RolePermissionPicker";
import { ApiError, apiFetch } from "../lib/api/client";
import { formatRole } from "../lib/formatters";

type Account = { id: string; username: string; display_name: string | null; email: string; role: string; role_name?: string; is_active: boolean };
type RolePolicy = { role: string; display_name?: string; permissions: string[]; default_permissions: string[]; editable: boolean; builtin?: boolean };

export function AccessManagementPage() {
  const client = useQueryClient();
  const [tab, setTab] = useState<"users" | "roles">("users");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [editRole, setEditRole] = useState("site_manager");
  const [active, setActive] = useState(true);
  const [roleCreateOpen, setRoleCreateOpen] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<RolePolicy | null>(null);
  const [renamingRole, setRenamingRole] = useState<RolePolicy | null>(null);
  const [renameName, setRenameName] = useState("");
  const [roleName, setRoleName] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const users = useQuery({ queryKey: ["access-users", search, page], queryFn: () => apiFetch<{items: Account[]; total: number}>("/api/access/users?search=" + encodeURIComponent(search) + "&offset=" + page * 50 + "&limit=50") });
  const policies = useQuery({ queryKey: ["access-roles"], queryFn: () => apiFetch<{available_permissions: string[]; roles: RolePolicy[]}>("/api/access/roles") });
  const roles = policies.data?.roles ?? [];
  const hasDialog = createOpen || !!editing || roleCreateOpen || !!editingPolicy || !!renamingRole;
  const roleLabel = (role: RolePolicy) => role.display_name || formatRole(role.role);

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
    <PageHeader eyebrow="管理者設定" title="ID・権限管理" description="ログインIDと役割を管理し、役割ごとの閲覧・操作権限を設定します。" />
    <div className="record-list-actions" role="group" aria-label="管理対象">
      <button className={tab === "users" ? "primary-button" : "ghost-button"} onClick={() => setTab("users")}>ログインID</button>
      <button className={tab === "roles" ? "primary-button" : "ghost-button"} onClick={() => setTab("roles")}>役割ごとの権限</button>
    </div>
    {error && !hasDialog && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {(users.isError || policies.isError) && <p role="alert">管理情報を取得できませんでした。</p>}
    {tab === "users" ? <>
      <div className="record-list-actions"><button className="primary-button create-button" disabled={!roles.length} onClick={() => { setError(""); setCreateOpen(true); }}>新しいIDを作成</button></div>
      <label>IDを検索<input value={search} onChange={e => { setSearch(e.target.value); setPage(0); }} placeholder="ID・表示名・メール" /></label>
      {users.isLoading ? <p>読み込み中…</p> : <DataTable<Account> columns={[
        {key: "id", header: "ログインID", render: row => row.username},
        {key: "name", header: "表示名", render: row => row.display_name ?? "—"},
        {key: "email", header: "メール", render: row => row.email},
        {key: "role", header: "役割", render: row => row.role_name || formatRole(row.role)},
        {key: "status", header: "状態", render: row => row.is_active ? "有効" : "無効"},
        {key: "edit", header: "操作", render: row => <button onClick={() => {setError(""); setEditing(row); setEditRole(row.role); setActive(row.is_active);}}>権限・状態を変更</button>},
      ]} rows={users.data?.items ?? []} getRowKey={row => row.id} emptyTitle="IDがありません" emptyDescription="新しいIDを作成するか、検索条件を変更してください。" />}
      <div className="record-list-actions"><button disabled={page === 0} onClick={() => setPage(page - 1)}>前へ</button><span>{page + 1}ページ / 全{users.data?.total ?? 0}件</span><button disabled={(page + 1) * 50 >= (users.data?.total ?? 0)} onClick={() => setPage(page + 1)}>次へ</button></div>
    </> : <>
      <div className="record-list-actions"><button className="primary-button create-button" onClick={() => { setError(""); setRoleName(""); setSelected([]); setRoleCreateOpen(true); }}>新しい役割を作成</button></div>
      <p>権限の変更は同じ役割の全IDに適用されます。全体管理者の権限は固定です。</p>
      <DataTable<RolePolicy> columns={[
        {key: "name", header: "役割", render: row => roleLabel(row)},
        {key: "type", header: "種類", render: row => row.builtin === false ? "独自の役割" : "標準の役割"},
        {key: "permissions", header: "許可する権限", render: row => row.permissions.length + "項目"},
        {key: "edit", header: "操作", render: row => <div className="record-list-actions"><button onClick={() => { setError(""); setRenamingRole(row); setRenameName(roleLabel(row)); }}>名称を変更</button><button onClick={() => { setError(""); setEditingPolicy(row); setSelected([...row.permissions]); }}>{row.editable ? "権限を編集" : "権限を確認"}</button></div>},
      ]} rows={roles} getRowKey={row => row.role} emptyTitle="役割を読み込み中です" emptyDescription="しばらくお待ちください。" />
    </>}

    <FormDialog open={!!renamingRole} title="役割の名称を変更" size="compact" busy={busy} onClose={() => setRenamingRole(null)}>
      <form className="card access-form" onSubmit={e => { e.preventDefault(); if (renamingRole) void save("/api/access/roles/" + renamingRole.role + "/name", "PATCH", {display_name: renameName}, () => setRenamingRole(null)); }}>
        <p>名称はすべてのIDに反映されます。権限は変わりません。</p>
        <label>役割名<input required maxLength={100} value={renameName} onChange={e => setRenameName(e.target.value)} disabled={busy} /></label>
        {error && <p role="alert">{error}</p>}
        <div className="record-list-actions"><button className="primary-button" disabled={busy || !renameName.trim()}>名称を保存</button><button type="button" disabled={busy} onClick={() => setRenamingRole(null)}>キャンセル</button></div>
      </form>
    </FormDialog>

    <FormDialog open={createOpen} title="ログインIDを作成" busy={busy} onClose={() => setCreateOpen(false)}>
      <form className="card access-form" onSubmit={event => { event.preventDefault(); const values = new FormData(event.currentTarget); void save("/api/access/users", "POST", Object.fromEntries(values.entries()), () => setCreateOpen(false)); }}>
        <div className="access-grid">
          <label>ログインID<input name="username" required maxLength={100} pattern="[A-Za-z0-9_.@\-]+" autoComplete="off" /></label>
          <label>表示名<input name="display_name" required maxLength={100} /></label>
          <label>メールアドレス<input name="email" type="email" required maxLength={255} /></label>
          <label>初期パスワード<input name="password" type="password" required minLength={8} maxLength={72} autoComplete="new-password" /></label>
          <label>役割<select aria-label="役割" name="role" defaultValue="site_manager">{roles.map(item => <option key={item.role} value={item.role}>{roleLabel(item)}</option>)}</select></label>
        </div>
        <p>初期パスワードは8文字以上に設定し、本人に安全な方法で伝えてください。</p>
        {error && <p role="alert">{error}</p>}
        <div className="record-list-actions"><button className="primary-button create-button" disabled={busy}>IDを作成</button><button type="button" disabled={busy} onClick={() => setCreateOpen(false)}>キャンセル</button></div>
      </form>
    </FormDialog>

    <FormDialog open={!!editing} title={(editing?.username ?? "") + " の権限・状態"} size="compact" busy={busy} onClose={() => setEditing(null)}>
      {editing && <form className="card access-form" onSubmit={e => { e.preventDefault(); void save("/api/access/users/" + editing.id, "PUT", {role: editRole, is_active: active}, () => setEditing(null)); }}>
        <label>役割<select aria-label="役割" value={editRole} onChange={e => setEditRole(e.target.value)}>{roles.map(item => <option key={item.role} value={item.role}>{roleLabel(item)}</option>)}{editing.role === "worker" && <option value="worker">稼働者</option>}</select></label>
        <div className="record-list-actions" role="group" aria-label="IDの状態"><button type="button" className={active ? "primary-button" : "ghost-button"} onClick={() => setActive(true)}>有効</button><button type="button" className={!active ? "primary-button" : "ghost-button"} onClick={() => setActive(false)}>無効</button></div>
        {error && <p role="alert">{error}</p>}
        <div className="access-apply-row"><button className="access-apply-button" disabled={busy || (editRole === editing.role && active === editing.is_active)}>変更を適用して閉じる</button></div>
      </form>}
    </FormDialog>

    <FormDialog open={roleCreateOpen || !!editingPolicy} title={roleCreateOpen ? "新しい役割を作成" : (editingPolicy ? roleLabel(editingPolicy) : "") + " の権限"} busy={busy} onClose={() => { setRoleCreateOpen(false); setEditingPolicy(null); }}>
      <form className="card access-form" onSubmit={e => { e.preventDefault(); void save(roleCreateOpen ? "/api/access/roles" : "/api/access/roles/" + editingPolicy?.role, roleCreateOpen ? "POST" : "PUT", {permissions: selected, ...(roleCreateOpen ? {display_name: roleName} : {})}, () => { setRoleCreateOpen(false); setEditingPolicy(null); }); }}>
        {roleCreateOpen && <label>役割名<input required maxLength={100} value={roleName} onChange={e => setRoleName(e.target.value)} placeholder="例：案件閲覧担当" /></label>}
        <p>新しい役割は権限なしから設定します。編集・承認を選ぶと閲覧も許可し、閲覧を外すと関連操作も外します。ID・役割管理は全体管理者だけが行えます。</p>
        <RolePermissionPicker available={policies.data?.available_permissions ?? []} selected={selected} setSelected={setSelected} disabled={busy || (!roleCreateOpen && !editingPolicy?.editable)} />
        {(roleCreateOpen || editingPolicy?.editable) && <>
          {error && <p role="alert">{error}</p>}
          <div className="record-list-actions"><button className={roleCreateOpen ? "primary-button create-button" : "primary-button"} disabled={busy || (roleCreateOpen && !roleName.trim())}>{roleCreateOpen ? "役割を作成" : "この役割の権限を保存"}</button>{editingPolicy && <button type="button" disabled={busy} onClick={() => setSelected(editingPolicy.default_permissions)}>初期設定を選び直す</button>}</div></>}
      </form>
    </FormDialog>
  </div>;
}
