import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";

import { ApiError, getLineRegistrationReview } from "../lib/api/client";
import { LineRegistrationReviewPanel } from "./LineRegistrationReviewPanel";

export function LineRegistrationReviewModal({ requestId, onClose }: { requestId: string; onClose: () => void }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const reviewQuery = useQuery({
    queryKey: ["line-registration-review", requestId],
    queryFn: () => getLineRegistrationReview(requestId),
    retry: false,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
      }
      if (event.key === "Tab") {
        const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(
          'button:not(:disabled), input:not(:disabled), select:not(:disabled), a[href], [tabindex="0"]',
        ) ?? []).filter((element) => element.getClientRects().length > 0);
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (!first) { event.preventDefault(); dialogRef.current?.focus(); return; }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialogRef.current)) {
          event.preventDefault(); last?.focus();
        } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialogRef.current)) {
          event.preventDefault(); first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, []);

  return createPortal(
    <div className="order-create-backdrop">
      <div className="order-draft is-modal worker-profile-modal" role="dialog" aria-modal="true"
        aria-labelledby="line-registration-review-title" tabIndex={-1} ref={dialogRef}>
        <header className="order-draft-head">
          <div className="order-draft-head-lead">
            <p className="order-draft-kicker">公式LINEの登録申請</p>
            <h3 id="line-registration-review-title">LINE登録の内容確認</h3>
            <p className="order-draft-lead">反映先と変更前後を確認して承認してください。</p>
          </div>
          <div className="order-draft-head-side">
            <button type="button" className="btn btn-ghost order-draft-close" onClick={onClose}>閉じる</button>
          </div>
        </header>
        <div className="order-draft-body">
          <section className="order-draft-section">
            {reviewQuery.isLoading ? <p>申請内容を読み込み中...</p> : null}
            {reviewQuery.isError ? <>
              <p className="form-error">{reviewQuery.error instanceof ApiError ? reviewQuery.error.message : "申請内容を取得できませんでした。"}</p>
              <button type="button" className="btn btn-ghost" onClick={() => { void reviewQuery.refetch(); }}>最新の内容を読み込む</button>
            </> : null}
            {reviewQuery.data ? <LineRegistrationReviewPanel key={requestId} review={reviewQuery.data} onReload={() => { void reviewQuery.refetch(); }} /> : null}
          </section>
        </div>
      </div>
    </div>, document.body,
  );
}
