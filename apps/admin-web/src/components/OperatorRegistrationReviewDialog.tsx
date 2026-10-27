import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormDialog } from "./FormDialog";
import { approveOperatorRegistration, getOperatorRegistrationReview, rejectOperatorRegistration } from "../lib/api/client";

export function OperatorRegistrationReviewDialog({ requestId, onClose }: { requestId: string; onClose: () => void }) {
  const client = useQueryClient();
  const [target, setTarget] = useState("");
  const [userId, setUserId] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const review = useQuery({ queryKey: ["operator-registration-review", requestId], queryFn: () => getOperatorRegistrationReview(requestId), retry: false, refetchOnWindowFocus: false });
  const refresh = async () => {
    await Promise.all([client.invalidateQueries({ queryKey: ["registration-requests"] }), client.invalidateQueries({ queryKey: ["operator-staff"] }), client.invalidateQueries({ queryKey: ["vanzai-staff-page"] })]);
    onClose();
  };
  const approve = useMutation({ mutationFn: () => approveOperatorRegistration(requestId, target || undefined, review.data?.candidates.find((item) => item.id === target)?.profile_revision, userId), onSuccess: refresh, onError: (cause) => setError(cause.message) });
  const reject = useMutation({ mutationFn: () => rejectOperatorRegistration(requestId, reason.trim()), onSuccess: refresh, onError: (cause) => setError(cause.message) });
  const busy = approve.isPending || reject.isPending;
  const logins = (review.data?.login_candidates ?? []).filter((item) => !item.staff_id || item.staff_id === target);
  const selectedLogin = logins.some((item) => item.id === userId);
  return <FormDialog open title="運営スタッフ登録の内容確認" busy={busy} onClose={onClose} size="compact">
    <div className="operator-enrollment-form">
    {review.isLoading && <p>申請を読み込み中...</p>}
    {review.isError && <p className="form-error" role="alert">{review.error.message}</p>}
    {review.data && <>
      <p><span className="status-badge attention">運営スタッフ</span></p>
      <dl><dt>氏名</dt><dd>{review.data.name}</dd><dt>電話番号</dt><dd>{review.data.phone}</dd><dt>LINE表示名</dt><dd>{review.data.line_display_name}</dd></dl>
      {review.data.status === "pending" ? <>
        <fieldset disabled={busy}><legend>反映先</legend><label><input type="radio" name="operator-target" checked={!target} onChange={() => { setTarget(""); setUserId(""); }} />新規の運営スタッフとして登録</label>
          {review.data.candidates.map((candidate) => <label key={candidate.id} style={{ display: "block", marginTop: 8 }}><input type="radio" name="operator-target" checked={target === candidate.id} onChange={() => { setTarget(candidate.id); setUserId(""); }} />既存：{candidate.name}（{candidate.phone || "電話未設定"}）</label>)}
        </fieldset>
        <p>既存の運営スタッフを選ぶ場合、現在の氏名・電話番号・担当ロールを保持します。</p>
        <fieldset disabled={busy}><legend>本人の管理画面ID（必須）</legend>
          <label className="order-field">紐付けるログインID<select aria-label="紐付けるログインID" value={userId} onChange={(event) => setUserId(event.target.value)}><option value="">本人のIDを選んでください</option>{logins.map((item) => <option key={item.id} value={item.id}>{item.display_name || item.username}（{item.username}）{item.staff_id ? "・この運営に対応済み" : ""}</option>)}</select></label>
          {!logins.length && <p role="status">選べる未紐付けのIDがありません。先に本人のIDを作成してください。</p>}
          <p>IDが未作成の場合は、先に作成してから承認します。役割・閲覧権限は選んだIDの設定を使います。</p>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}><a className="btn btn-ghost" style={{ borderColor: "#8b5bb5", color: "#8b5bb5" }} href="/settings/access?create=1" target="_blank" rel="noopener noreferrer">IDを先に作成（別タブ）</a><button type="button" className="btn btn-ghost" disabled={review.isFetching} onClick={() => void review.refetch()}>ID一覧を更新</button></div>
        </fieldset>
        {error && <><p className="form-error" role="alert">{error}</p><button type="button" className="btn btn-ghost" disabled={busy || review.isFetching} onClick={() => { setTarget(""); setError(""); void review.refetch(); }}>最新の内容を読み込む</button></>}
        <button type="button" className="btn btn-primary create-button" disabled={busy || !selectedLogin || (!target && review.data.candidates.length > 0)} onClick={() => approve.mutate()}>{approve.isPending ? "承認中..." : "IDを紐付けて承認"}</button>
        <label>却下理由<input maxLength={1000} disabled={busy} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <button type="button" className="btn btn-ghost" disabled={busy || !reason.trim()} onClick={() => reject.mutate()}>却下</button>
      </> : <p>この申請の審査は終わっています。</p>}
    </>}
    </div>
  </FormDialog>;
}
