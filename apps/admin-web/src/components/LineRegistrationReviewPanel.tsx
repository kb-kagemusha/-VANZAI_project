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
  nearest_station: "最寄り駅",
  station_walk_minutes: "最寄り駅まで徒歩（分）",
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
  nearest_station: "最寄り駅",
  station_walk_minutes: "最寄り駅まで徒歩（分）",
};

function show(value: string) {
  return value || "（空）";
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

  return (
    <div style={{ display: "grid", gap: "0.75rem" }}>
      <h4 style={{ margin: 0 }}>LINE登録の審査</h4>
      <p style={{ margin: 0 }}>{targetSentence(shown)}</p>
      {shown.blocked_reason && shown.mode !== "choose" ? <p style={{ margin: 0 }}>{shown.blocked_reason}</p> : null}
      {shown.mode === "choose" || shown.mode === "create_new" || shown.mode === "existing" ? (
        <div style={{ display: "grid", gap: "0.75rem" }}>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="氏名・ふりがな・電話で探す"
              aria-label="既存の稼働者を検索"
            />
            <button type="button" className="btn btn-ghost" disabled={search.isPending} onClick={() => search.mutate()}>
              検索
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={choose.isPending || !pending}
              onClick={() => choose.mutate({ decision: "create_new" })}
            >
              新規の稼働者として比較する
            </button>
          </div>
          {candidates.length === 0 ? (
            <p style={{ margin: 0 }}>一致する稼働者はいません。新規として作る場合は、新規作成を選んでください。</p>
          ) : (
            <div style={{ display: "grid", gap: "0.5rem" }}>
              {candidates.map((candidate) => (
                <div
                  key={candidate.worker_id}
                  style={{
                    display: "flex",
                    gap: "0.75rem",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "0.75rem",
                    border: "1px solid var(--color-border-subtle, #d0d5dd)",
                    borderRadius: "0.5rem",
                  }}
                >
                  <span>
                    {candidate.name}
                    {candidate.phone ? ` / ${candidate.phone}` : ""}（{candidate.match_reasons.join("・")}）
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={choose.isPending || !pending}
                    onClick={() => choose.mutate({ decision: "existing", worker_id: candidate.worker_id })}
                  >
                    この稼働者で比較する
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
      {shown.mode !== "choose" ? (
        <div style={{ display: "grid", gap: "0.5rem" }}>
          {Object.keys(FIELD_LABELS).map((field) => (
            <div
              key={field}
              style={{
                display: "grid",
                gap: "0.2rem",
                padding: "0.75rem",
                border: "1px solid var(--color-border-subtle, #d0d5dd)",
                borderRadius: "0.5rem",
              }}
            >
              <strong>{FIELD_LABELS[field]}</strong>
              <span>変更前: {show(shown.before[field] || "")}</span>
              <span>変更後: {show(shown.after[field] || "")}</span>
            </div>
          ))}
        </div>
      ) : null}
      <div style={{ display: "grid", gap: "0.35rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        {Object.keys(COMPONENT_LABELS).map((field) => (
          <div key={field}>
            {COMPONENT_LABELS[field]}: {shown.components[field] || "（未入力）"}
          </div>
        ))}
      </div>
      {message ? <p style={{ margin: 0 }}>{message}</p> : null}
      {error ? <p style={{ margin: 0 }}>{error}</p> : null}
      <div>
        <button type="button" className="btn btn-ghost" onClick={onReload}>
          最新の内容を読み込む
        </button>
      </div>
      {pending ? (
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
          {shown.can_decide ? (
            <button
              type="button"
              className="btn btn-primary"
              disabled={!shown.comparison_ticket || approve.isPending}
              onClick={() => approve.mutate()}
            >
              承認
            </button>
          ) : (
            <p style={{ margin: 0 }}>承認できる反映先が決まっていません。</p>
          )}
          <div style={{ display: "grid", gap: "0.5rem" }}>
            <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="却下理由" />
            <button
              type="button"
              className="btn btn-danger"
              disabled={reason.trim().length === 0 || reject.isPending}
              onClick={() => reject.mutate()}
            >
              却下
            </button>
          </div>
        </div>
      ) : (
        <p style={{ margin: 0 }}>この申請の審査は終わっています。</p>
      )}
    </div>
  );
}
