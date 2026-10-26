import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormDialog } from "./FormDialog";
import { approveOperatorRegistration, getOperatorRegistrationReview, rejectOperatorRegistration } from "../lib/api/client";

export function OperatorRegistrationReviewDialog({ requestId, onClose }: { requestId: string; onClose: () => void }) {
  const client = useQueryClient();
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const review = useQuery({ queryKey: ["operator-registration-review", requestId], queryFn: () => getOperatorRegistrationReview(requestId), retry: false, refetchOnWindowFocus: false });
  const refresh = async () => {
    await Promise.all([client.invalidateQueries({ queryKey: ["registration-requests"] }), client.invalidateQueries({ queryKey: ["operator-staff"] }), client.invalidateQueries({ queryKey: ["vanzai-staff-page"] })]);
    onClose();
  };
  const approve = useMutation({ mutationFn: () => approveOperatorRegistration(requestId, target || undefined, review.data?.candidates.find((item) => item.id === target)?.profile_revision), onSuccess: refresh, onError: (cause) => setError(cause.message) });
  const reject = useMutation({ mutationFn: () => rejectOperatorRegistration(requestId, reason.trim()), onSuccess: refresh, onError: (cause) => setError(cause.message) });
  const busy = approve.isPending || reject.isPending;
  return <FormDialog open title="運営スタッフ登録の内容確認" busy={busy} onClose={onClose} size="compact">
    <div className="operator-enrollment-form">
    {review.isLoading && <p>申請を読み込み中...</p>}
    {review.isError && <p className="form-error" role="alert">{review.error.message}</p>}
    {review.data && <>
      <p><span className="status-badge attention">運営スタッフ</span></p>
      <dl><dt>氏名</dt><dd>{review.data.name}</dd><dt>電話番号</dt><dd>{review.data.phone}</dd><dt>LINE表示名</dt><dd>{review.data.line_display_name}</dd></dl>
      {review.data.status === "pending" ? <>
        <fieldset disabled={busy}><legend>反映先</legend><label><input type="radio" name="operator-target" checked={!target} onChange={() => setTarget("")} />新規の運営スタッフとして登録</label>
          {review.data.candidates.map((candidate) => <label key={candidate.id} style={{ display: "block", marginTop: 8 }}><input type="radio" name="operator-target" checked={target === candidate.id} onChange={() => setTarget(candidate.id)} />既存：{candidate.name}（{candidate.phone || "電話未設定"}）</label>)}
        </fieldset>
        <p>既存の運営スタッフを選ぶ場合、現在の氏名・電話番号・担当ロールを保持し、本人のLINEだけを紐付けます。管理画面のID・権限は付与しません。</p>
        {error && <><p className="form-error" role="alert">{error}</p><button type="button" className="btn btn-ghost" disabled={busy || review.isFetching} onClick={() => { setTarget(""); setError(""); void review.refetch(); }}>最新の内容を読み込む</button></>}
        <button type="button" className="btn btn-primary create-button" disabled={busy || (!target && review.data.candidates.length > 0)} onClick={() => approve.mutate()}>{approve.isPending ? "承認中..." : "承認"}</button>
        <label>却下理由<input maxLength={1000} disabled={busy} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <button type="button" className="btn btn-ghost" disabled={busy || !reason.trim()} onClick={() => reject.mutate()}>却下</button>
      </> : <p>この申請の審査は終わっています。</p>}
    </>}
    </div>
  </FormDialog>;
}
