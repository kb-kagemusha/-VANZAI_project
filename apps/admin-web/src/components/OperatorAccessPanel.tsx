import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api/client";

type Access = { user_ids: string[]; menu_status: string; users: { id: string; name: string; username: string; is_active: boolean; available: boolean }[] };
export function OperatorAccessPanel({ staffId }: { staffId: string }) {
  const [data, setData] = useState<Access | null>(null);
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const path = `/api/operator-access/${staffId}`;
  const load = (value: Access) => { setData(value); setSelected(value.user_ids.length === 1 ? value.user_ids[0] : ""); };
  useEffect(() => { let active = true; apiFetch<Access>(path).then((v) => { if (active) load(v); }).catch((e) => { if (active) setMessage(e.message); }); return () => { active = false; }; }, [path]);
  async function save() {
    setBusy(true); setMessage("");
    try { load(await apiFetch<Access>(path, { method: "PUT", body: JSON.stringify({ user_id: selected || null }) })); setMessage("ログインIDとの対応を保存しました。"); }
    catch (e) { setMessage(e instanceof Error ? e.message : "保存できませんでした。"); }
    finally { setBusy(false); }
  }
  async function sync() {
    setBusy(true); setMessage("");
    try { const result = await apiFetch<{ status: string }>(`${path}/sync`, { method: "POST" }); setMessage(result.status === "applied" ? "メニューの反映を確認しました。" : result.status === "not_eligible" ? "有効な管理画面IDとの対応を確認してください。" : result.status === "not_published" ? "メニューは準備中です。" : "LINEへの反映を再試行しています。しばらくしてから確認してください。"); load(await apiFetch<Access>(path)); }
    catch (e) { setMessage(e instanceof Error ? e.message : "確認できませんでした。"); }
    finally { setBusy(false); }
  }
  return <section className="order-draft-section operator-account-card"><h4>LINE運営画面のログインID</h4><p>本人の管理画面IDを選びます。LINEの運営画面も、このIDの閲覧権限を使います。</p>
    {data && <><label className="order-field">対応するログインID<select value={selected} onChange={(e) => setSelected(e.target.value)} disabled={busy}><option value="">未設定</option>{data.users.map((u) => <option key={u.id} value={u.id} disabled={!u.available || !u.is_active}>{u.name}（{u.username}）{!u.is_active ? "・無効" : !u.available ? "・別の本人に対応済み" : ""}</option>)}</select></label>
      {data.user_ids.length > 1 && <p role="alert">複数のIDが対応しています。本人のIDを1つ選び直してください。</p>}
      <div className="operator-form-actions"><button type="button" className="btn btn-ghost operator-access-save" disabled={busy} onClick={() => void save()}>IDの対応を保存</button><button type="button" className="btn btn-ghost operator-menu-sync" disabled={busy} onClick={() => void sync()}>LINEメニューを再確認</button></div>
      <p>メニュー反映：{({ applied: "反映済み", pending: "確認待ち", failed: "再試行待ち", not_linked: "LINE未連携" } as Record<string, string>)[data.menu_status] || data.menu_status}</p></>}
    {message && <p role="status">{message}</p>}
  </section>;
}
