import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormDialog } from "./FormDialog";
import { getOperatorInvitations, getOperatorRegistrationSettings, issueOperatorInvitation, revokeOperatorInvitation } from "../lib/api/client";
import { formatDateTime } from "../lib/formatters";

export function OperatorInvitationDialog({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const settings = useQuery({ queryKey: ["operator-registration-settings"], queryFn: getOperatorRegistrationSettings });
  const invitations = useQuery({ queryKey: ["operator-invitations"], queryFn: getOperatorInvitations });
  const issue = useMutation({ mutationFn: issueOperatorInvitation, onSuccess: async () => { setError(""); setCopied(false); await client.invalidateQueries({ queryKey: ["operator-invitations"] }); }, onError: (cause) => setError(cause.message) });
  const revoke = useMutation({ mutationFn: revokeOperatorInvitation, onSuccess: async (_result, id) => { if (issue.data?.request_id === id) issue.reset(); setError(""); await client.invalidateQueries({ queryKey: ["operator-invitations"] }); }, onError: (cause) => setError(cause.message) });
  return <FormDialog open title="運営スタッフのLINE招待" onClose={onClose} busy={issue.isPending || revoke.isPending} size="compact">
    <div className="operator-enrollment-form">
    <p>本人が氏名・電話番号を入力して申請し、管理者が「登録確認待ち」で承認します。リンクは24時間・1申請限りです。</p>
    {settings.isError ? <p className="form-error">登録設定を確認できませんでした。</p> : settings.data && !settings.data.enabled ? <p>運営用のLINE登録は準備中です。運営用LIFFの設定後に招待リンクを発行できます。</p> : null}
    <button type="button" className="btn btn-primary create-button" disabled={!settings.data?.enabled || issue.isPending} onClick={() => issue.mutate()}>{issue.isPending ? "発行中..." : "招待リンクを発行"}</button>
    {issue.data && <section className="order-draft-section"><p>発行したURLはこの画面でのみ確認できます。本人へ個別に渡してください。</p><p style={{ overflowWrap: "anywhere" }}>{issue.data.url}</p><p>期限：{formatDateTime(issue.data.expires_at)}</p><button type="button" className="btn btn-ghost" onClick={async () => { try { await navigator.clipboard.writeText(issue.data!.url); setCopied(true); } catch { setError("コピーできませんでした。表示されたURLを選択してコピーしてください。"); } }}>{copied ? "コピーしました" : "URLをコピー"}</button></section>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <h3>未申請の招待</h3>
    {invitations.isError ? <p className="form-error">招待一覧を取得できませんでした。</p> : invitations.data?.items.length === 0 ? <p>未申請の招待はありません。</p> : invitations.data?.items.map((item) => <div key={item.request_id}><span>発行 {formatDateTime(item.created_at)}／期限 {formatDateTime(item.expires_at)}</span><button type="button" className="btn btn-ghost" disabled={revoke.isPending} onClick={() => revoke.mutate(item.request_id)}>失効</button></div>)}
    </div>
  </FormDialog>;
}
