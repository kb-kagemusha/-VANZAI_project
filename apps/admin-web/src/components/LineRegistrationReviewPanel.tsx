import { showAdditionalStations } from "../lib/additionalStations";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  approveLineRegistrationReview,
  chooseLineRegistrationReview,
  getLineRegistrationReviewCandidates,
  rejectLineRegistrationReview,
} from "../lib/api/client";
import type { LineRegistrationReviewCandidate, LineRegistrationReviewResponse } from "../types/api";

const FIELD_LABELS: Record<string, string> = {
  name: "氏名",
  furigana: "ふりがな",
  phone: "電話",
  email: "メール",
  birth_date: "生年月日",
  postal_code: "郵便番号",
  address: "住所",
  additional_stations: "追加の最寄り駅",
  nearest_station: "最寄り駅",
  station_walk_minutes: "最寄り駅まで徒歩（分）",
  emergency_contact_phone: "緊急連絡先の電話番号",
  emergency_contact_name: "緊急連絡先のお名前",
  emergency_contact_relationship: "ご本人との関係",
};

const COMPONENT_LABELS: Record<string, string> = {
  last_name: "姓",
  first_name: "名",
  last_name_furigana: "せい",
  first_name_furigana: "めい",
  phone: "電話",
  email: "メール",
  birth_date: "生年月日",
  postal_code: "郵便番号",
  prefecture: "都道府県",
  address1: "市区町村・番地",
  address2: "建物名",
  additional_stations: "追加の最寄り駅",
  nearest_station: "最寄り駅",
  station_walk_minutes: "最寄り駅まで徒歩（分）",
  emergency_contact_phone: "緊急連絡先の電話番号",
  emergency_contact_name: "緊急連絡先のお名前",
  emergency_contact_relationship: "ご本人との関係",
};

const INPUT_GROUPS = [
  { title: "お名前・生年月日", fields: ["last_name", "first_name", "last_name_furigana", "first_name_furigana", "birth_date"] },
  { title: "連絡先", fields: ["phone", "email"] },
  { title: "住所", fields: ["postal_code", "prefecture", "address1", "address2"] },
  { title: "最寄り駅", fields: ["nearest_station", "station_walk_minutes", "additional_stations"] },
  { title: "緊急連絡先", fields: ["emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship"] },
];

const RESULT_GROUPS = [
  { title: "お名前・生年月日", fields: ["name", "furigana", "birth_date"] },
  { title: "連絡先", fields: ["phone", "email"] },
  { title: "住所", fields: ["postal_code", "address"] },
  { title: "最寄り駅", fields: ["nearest_station", "station_walk_minutes", "additional_stations"] },
  { title: "緊急連絡先", fields: ["emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship"] },
];

function show(value: string, field?: string) {
  return field === "additional_stations" ? showAdditionalStations(value) : value || "（空）";
}

function targetSentence(review: LineRegistrationReviewResponse) {
  if (review.mode === "fixed_update") {
    return `反映先は、申請時の「${review.worker_name || "稼働者"}」です。解除や差し替えのあとは、比較票を取り直しても承認できません。`;
  }
  if (review.mode === "create_new") {
    return "新規の稼働者として比較しています。承認すると、新しい稼働者とLINEの紐付けを同時に作ります。";
  }
  if (review.mode === "existing") {
    return `既存の「${review.worker_name || "稼働者"}」として比較しています。承認では紐付けを作りません。`;
  }
  return "新規の稼働者として作るか、既存の稼働者を選んでください。氏名や電話が一致しても、自動では統合しません。";
}

export function LineRegistrationReviewPanel({
  review,
  onReload,
}: {
  review: LineRegistrationReviewResponse;
  onReload: () => void;
}) {
  const [reason, setReason] = useState("");
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [shown, setShown] = useState(review);
  const [candidates, setCandidates] = useState<LineRegistrationReviewCandidate[]>(review.candidates);
  const queryClient = useQueryClient();
  const pending = shown.status === "pending";

  useEffect(() => {
    setShown(review);
    setCandidates(review.candidates);
    setQuery("");
    setMessage("");
    setError("");
  }, [review]);

  const choose = useMutation({
    mutationFn: (body: { decision: "create_new" | "existing"; worker_id?: string }) =>
      chooseLineRegistrationReview(shown.request_id, body),
    onSuccess: (next) => {
      setShown(next);
      setCandidates(next.candidates);
      setError("");
      setMessage("");
    },
    onError: (caught) => {
      setMessage("");
      setError(caught instanceof ApiError ? caught.message : "反映先を比較できませんでした。");
    },
  });

  const search = useMutation({
    mutationFn: () => getLineRegistrationReviewCandidates(shown.request_id, query),
    onSuccess: (result) => {
      setCandidates(result.candidates);
      setError("");
    },
    onError: (caught) => {
      setMessage("");
      setError(caught instanceof ApiError ? caught.message : "稼働者を検索できませんでした。");
    },
  });

  const approve = useMutation({
    mutationFn: () => approveLineRegistrationReview(shown.request_id, shown.comparison_ticket || ""),
    onSuccess: async () => {
      setError("");
      setMessage(
        shown.mode === "create_new"
          ? "新しい稼働者とLINEの紐付けを確定しました。"
          : shown.mode === "existing"
            ? "選択した稼働者へ反映しました。紐付けは新しく作っていません。"
            : "申請時の稼働者へ反映しました。",
      );
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["registration-request", shown.request_id] });
      await queryClient.invalidateQueries({ queryKey: ["line-registration-review", shown.request_id] });
      await queryClient.invalidateQueries({ queryKey: ["workers-list"] });
      await queryClient.invalidateQueries({ queryKey: ["line-links"] });
      await queryClient.invalidateQueries({ queryKey: ["line-link-workers"] });
    },
    onError: (caught) => {
      setMessage("");
      setError(caught instanceof ApiError ? caught.message : "承認できませんでした。");
    },
  });

  const reject = useMutation({
    mutationFn: () => rejectLineRegistrationReview(shown.request_id, reason.trim()),
    onSuccess: async () => {
      setError("");
      setMessage("LINEからの申請を却下し、受付を終えました。");
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["registration-request", shown.request_id] });
      await queryClient.invalidateQueries({ queryKey: ["line-registration-review", shown.request_id] });
    },
    onError: (caught) => {
      setMessage("");
      setError(caught instanceof ApiError ? caught.message : "却下できませんでした。");
    },
  });

  const busy = choose.isPending || approve.isPending || reject.isPending;
  const creating = shown.mode === "create_new";
  const selecting = shown.mode === "choose";
  const groups = selecting ? INPUT_GROUPS : RESULT_GROUPS;
  const labels = selecting ? COMPONENT_LABELS : FIELD_LABELS;
  const values = selecting ? shown.components : shown.after;

  return <div className="line-review">
    <section className="line-review-target" aria-labelledby="line-review-target-title">
      <h4 id="line-review-target-title">1. 登録方法・反映先</h4>
      <p>{targetSentence(shown)}</p>
      {shown.blocked_reason && !selecting ? <p className="line-review-warning">{shown.blocked_reason}</p> : null}
      {["choose", "create_new", "existing"].includes(shown.mode) && pending ? <div className="line-review-options">
        <div className={`line-review-option${creating ? " is-selected" : ""}`}>
          <strong>初めて登録する方</strong>
          <p>新しい稼働者として登録します。次に内容を確認して承認してください。</p>
          <button type="button" className="btn btn-primary create-button" disabled={busy} onClick={() => choose.mutate({ decision: "create_new" })}>
            {choose.isPending ? "内容を確認中..." : "新規登録へ進む"}
          </button>
          {creating ? <span className="line-review-selection">新規登録を選択中</span> : null}
        </div>
        <div className="line-review-option">
          <strong>すでに登録されている方</strong>
          <p>登録済みの稼働者を探し、更新先を選びます。</p>
          <div className="line-review-search">
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="氏名・ふりがな・電話で探す" aria-label="既存の稼働者を検索" />
            <button type="button" className="btn btn-ghost line-review-existing" disabled={search.isPending || busy} onClick={() => search.mutate()}>検索</button>
          </div>
          {candidates.length === 0 ? <p className="line-review-note">一致する稼働者はいません。初めての方は「新規登録へ進む」を選んでください。</p> : <div className="line-review-candidates">
            {candidates.map((candidate) => <div key={candidate.worker_id} className="line-review-candidate">
              <span><strong>{candidate.name}</strong>{candidate.phone ? `／${candidate.phone}` : ""}<small>{candidate.match_reasons.join("・")}</small></span>
              <button type="button" className="btn btn-ghost line-review-existing" disabled={busy} onClick={() => choose.mutate({ decision: "existing", worker_id: candidate.worker_id })}>この稼働者を選ぶ</button>
            </div>)}
          </div>}
        </div>
      </div> : null}
    </section>

    <section className="line-review-content" aria-labelledby="line-review-content-title">
      <h4 id="line-review-content-title">2. {selecting ? "届いた申請内容" : creating ? "新規登録する内容を確認" : "変更内容を確認"}</h4>
      {!selecting && !creating ? <p className="line-review-note">色の付いた行が変更される項目です。現在の登録と申請後の内容を確認してください。</p> : null}
      <div className="line-review-groups">
        {groups.map((group) => <section className="line-review-group" key={group.title}>
          <h5>{group.title}</h5>
          {selecting || creating ? <dl>{group.fields.map((field) => <div key={field}><dt>{labels[field]}</dt><dd>{show(values[field] || "", field)}</dd></div>)}</dl> : <table>
            <thead><tr><th>項目</th><th>現在の登録</th><th>申請後</th></tr></thead>
            <tbody>{group.fields.map((field) => <tr key={field} className={(shown.before[field] || "") !== (shown.after[field] || "") ? "is-changed" : undefined}>
              <th scope="row">{labels[field]}</th><td>{show(shown.before[field] || "", field)}</td><td>{show(shown.after[field] || "", field)}</td>
            </tr>)}</tbody>
          </table>}
        </section>)}
      </div>
    </section>
    {message ? <p className="line-review-success" role="status">{message}</p> : null}
    {error ? <p className="form-error" role="alert">{error}</p> : null}
    <div><button type="button" className="btn btn-ghost" disabled={busy} onClick={onReload}>最新の内容を読み込む</button></div>
    {pending ? <section className="line-review-actions">
      <div>{shown.can_decide ? <>
        <p>{creating ? "承認すると、新しい稼働者とLINEの紐付けを作成します。" : "承認すると、選択した稼働者へ内容を反映します。"}</p>
        <button type="button" className="btn btn-primary create-button" disabled={!shown.comparison_ticket || busy} onClick={() => approve.mutate()}>{approve.isPending ? "承認中..." : creating ? "承認して新規登録" : "承認して更新"}</button>
      </> : <p>新規登録または既存の稼働者を選ぶと、承認へ進めます。</p>}</div>
      <div className="line-review-reject"><label>却下する場合の理由<input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="却下理由" disabled={busy} /></label>
        <button type="button" className="btn btn-ghost line-review-reject-button" disabled={!reason.trim() || busy} onClick={() => reject.mutate()}>却下</button>
      </div>
    </section> : <p>この申請の審査は終わっています。</p>}
  </div>;
}
