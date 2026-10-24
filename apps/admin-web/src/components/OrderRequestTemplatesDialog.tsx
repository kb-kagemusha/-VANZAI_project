import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FormDialog } from "./FormDialog";
import { ApiError, archiveOrderRequestTemplate, listOrderRequestTemplates } from "../lib/api/client";
import { confirmApp } from "../lib/appDialog";

export function OrderRequestTemplatesDialog({ onClose, onUse, canWrite }: {
  onClose: () => void; onUse: (id: string) => Promise<boolean>; canWrite: boolean;
}) {
  const client = useQueryClient();
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const query = useQuery({ queryKey: ["order-request-templates", search, offset], queryFn: () => listOrderRequestTemplates({ q: search, offset, limit: 20 }) });

  async function useTemplate(id: string) {
    setBusy(true); setError("");
    try { if (await onUse(id)) onClose(); }
    catch (err) { setError(err instanceof Error ? err.message : "テンプレートを呼び出せませんでした。"); }
    finally { setBusy(false); }
  }
  async function archive(id: string, name: string) {
    if (!(await confirmApp({ title: "テンプレートを一覧から外す", message: `「${name}」を保存済み一覧から外します。作成済みの依頼書はそのまま残ります。`, confirmLabel: "一覧から外す" }))) return;
    setBusy(true); setError("");
    try {
      await archiveOrderRequestTemplate(id);
      setOffset(0);
      await client.invalidateQueries({ queryKey: ["order-request-templates"] });
    } catch (err) { setError(err instanceof ApiError ? err.message : "テンプレートを一覧から外せませんでした。"); }
    finally { setBusy(false); }
  }

  return <FormDialog open title="保存済みテンプレート" onClose={onClose} busy={busy}>
    <p>名前で探して、新規の依頼書へ内容を呼び出せます。日付・休業日・期限・送付先は毎回設定します。</p>
    <label className="order-field"><span className="order-field-label">テンプレート名で検索</span>
      <input value={search} maxLength={100} disabled={busy} onChange={(event) => { setSearch(event.target.value); setOffset(0); }} />
    </label>
    {query.isLoading ? <p>読み込んでいます…</p> : null}
    {query.isError ? <p className="form-error">テンプレートを読み込めませんでした。<button type="button" className="btn btn-ghost btn-sm" onClick={() => void query.refetch()}>再読み込み</button></p> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    {query.data ? <>
      {query.data.items.length ? <div className="order-list-table"><table className="data-table"><thead><tr><th>テンプレート名</th><th>案件名</th><th>操作</th></tr></thead><tbody>
        {query.data.items.map((row) => <tr key={row.id}>
          <td><strong>{row.name}</strong><span className="order-change-note">{row.source_document_number ? `保存元：${row.source_document_number}` : "直接作成"}</span></td>
          <td className="order-cell-multiline">{row.project_name || "—"}</td>
          <td><div className="order-row-actions">
            {canWrite ? <button type="button" className="btn create-button btn-sm" disabled={busy} onClick={() => void useTemplate(row.id)}>このテンプレートで新規作成</button> : null}
            {canWrite ? <button type="button" className="btn btn-ghost btn-sm" disabled={busy} onClick={() => void archive(row.id, row.name)}>一覧から外す</button> : null}
          </div></td>
        </tr>)}
      </tbody></table></div> : <p>{search ? "一致するテンプレートはありません。" : "保存済みのテンプレートはありません。「テンプレートの作成」または作成済み依頼書の「テンプレートとして保存」から登録できます。"}</p>}
      <div className="order-template-pagination">
        <button type="button" className="btn btn-ghost btn-sm" disabled={busy || offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>前へ</button>
        <span>{query.data.total}件{query.data.total ? `中 ${offset + 1}〜${Math.min(offset + 20, query.data.total)}件` : ""}</span>
        <button type="button" className="btn btn-ghost btn-sm" disabled={busy || offset + 20 >= query.data.total} onClick={() => setOffset(offset + 20)}>次へ</button>
      </div>
    </> : null}
  </FormDialog>;
}
