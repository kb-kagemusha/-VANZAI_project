import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError, approveLineRegistrationReview, rejectLineRegistrationReview } from "../lib/api/client";
import type { LineRegistrationReviewResponse } from "../types/api";

const FIELD_LABELS: Record<string, string> = {
  name: "氏名",
  furigana: "ふりがな",
  phone: "電話",
  email: "メール",
  birth_date: "生年月日",
  postal_code: "郵便番号",
  address: "住所",
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
};

function show(value: string) {
  return value || "（空）";
}

export function LineRegistrationReviewPanel({
  review,
  onReload,
}: {
  review: LineRegistrationReviewResponse;
  onReload: () => void;
}) {
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const queryClient = useQueryClient();
  const fixed = review.mode === "fixed_update";

  const approve = useMutation({
    mutationFn: () => approveLineRegistrationReview(review.request_id, review.comparison_ticket || ""),
    onSuccess: async () => {
      setError("");
      setMessage(fixed ? "紐付いている稼働者へ反映しました。" : "新しい稼働者とLINEの紐付けを確定しました。");
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["registration-request", review.request_id] });
      await queryClient.invalidateQueries({ queryKey: ["line-registration-review", review.request_id] });
    },
    onError: (caught) => {
      setMessage("");
      setError(caught instanceof ApiError ? caught.message : "承認できませんでした。");
    },
  });

  const reject = useMutation({
    mutationFn: () => rejectLineRegistrationReview(review.request_id, reason.trim()),
    onSuccess: async () => {
      setError("");
      setMessage("LINEからの申請を却下し、受付を終えました。");
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["registration-request", review.request_id] });
      await queryClient.invalidateQueries({ queryKey: ["line-registration-review", review.request_id] });
    },
    onError: (caught) => {
      setMessage("");
      setError(caught instanceof ApiError ? caught.message : "却下できませんでした。");
    },
  });

  return (
    <div style={{ display: "grid", gap: "0.75rem" }}>
      <h4 style={{ margin: 0 }}>LINE登録の審査</h4>
      <p style={{ margin: 0 }}>
        {fixed
          ? `反映先は、今有効な紐付けの「${review.worker_name || "稼働者"}」です。別の人へ付け替えません。`
          : "有効な紐付けはありません。承認すると、新しい稼働者とLINEの紐付けを同時に作ります。"}
      </p>
      <div style={{ display: "grid", gap: "0.5rem" }}>
        {Object.keys(FIELD_LABELS).map((field) => (
          <div key={field} style={{ display: "grid", gap: "0.2rem", padding: "0.75rem", border: "1px solid var(--color-border-subtle, #d0d5dd)", borderRadius: "0.5rem" }}>
            <strong>{FIELD_LABELS[field]}</strong>
            <span>変更前: {show(review.before[field] || "")}</span>
            <span>変更後: {show(review.after[field] || "")}</span>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gap: "0.35rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        {Object.keys(COMPONENT_LABELS).map((field) => (
          <div key={field}>
            {COMPONENT_LABELS[field]}: {review.components[field] || "（未入力）"}
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
      {review.can_decide ? (
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!review.comparison_ticket || approve.isPending}
            onClick={() => approve.mutate()}
          >
            承認
          </button>
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
