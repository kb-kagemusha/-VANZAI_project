import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { ApiError, fetchOcrImageBlobUrl, updateOcrRow } from "../../lib/api/client";
import { formatCurrency } from "../../lib/formatters";
import { getOcrRowDisplayLabels, isOcrRowConfirmable } from "../../lib/ocr/rowDisplay";
import { formatOcrValidationMessages } from "../../lib/ocr/validationMessages";
import type { OcrExtractedRowItem } from "../../types/api";
import { StatusBadge } from "../StatusBadge";
import { OcrFieldConfidenceLegend, OcrFieldConfidenceValue } from "./OcrFieldConfidence";
import {
  OcrRowEditForm,
  buildOcrRowUpdateBody,
  createOcrRowEditDraft,
  type OcrRowEditDraft,
} from "./OcrRowEditForm";

function useOcrImageBlobUrl(imageId: string) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setUrl(null);
    setFailed(false);
    fetchOcrImageBlobUrl(imageId)
      .then((blobUrl) => {
        if (!cancelled) {
          setUrl(blobUrl);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [imageId]);

  return { url, failed };
}

function OcrRowReviewSummary({ row }: { row: OcrExtractedRowItem }) {
  const isSettlement = row.source_type === "paygate_settlement";
  const labels = getOcrRowDisplayLabels(row);
  const fieldConfidence = row.field_confidence ?? {};
  const fieldSources = row.field_sources ?? {};
  const validationMessages =
    row.source_type === "paygate_settlement"
      ? [...(row.blocking_errors || []), ...(row.warnings || [])]
      : row.validation_errors || [];

  return (
    <div className="ocr-row-review-summary">
      <div className="ocr-row-review-meta">
        <p className="ocr-row-review-filename" title={row.source_image_filename || row.source_image_id}>
          {row.source_image_filename || row.source_image_id}
        </p>
        <div className="ocr-row-review-badges">
          <StatusBadge value={row.status} />
          {labels.map((label) => (
            <span key={label.key} className={`ocr-quality-badge ocr-quality-badge--${label.tone}`}>
              {label.text}
            </span>
          ))}
        </div>
      </div>
      {validationMessages.length ? (
        <p className="ocr-warning-text ocr-row-review-validation">{formatOcrValidationMessages(validationMessages)}</p>
      ) : (
        <p className="ocr-row-review-validation ocr-row-review-validation--ok">検証: OK</p>
      )}
      <OcrFieldConfidenceLegend />
      <dl className="ocr-row-review-readonly">
        <div>
          <dt>{isSettlement ? "精算日時" : "日時"}</dt>
          <dd>
            <OcrFieldConfidenceValue
              value={`${row.record_date || "—"} ${row.record_time || ""}`.trim()}
              confidence={fieldConfidence.record_datetime}
              source={fieldSources.record_datetime}
            />
          </dd>
        </div>
        <div>
          <dt>合計</dt>
          <dd>
            <OcrFieldConfidenceValue
              value={formatCurrency(row.amount)}
              confidence={fieldConfidence.amount}
              source={fieldSources.amount}
            />
          </dd>
        </div>
        {isSettlement ? (
          <>
            <div>
              <dt>小計</dt>
              <dd>
                <OcrFieldConfidenceValue
                  value={formatCurrency(row.subtotal)}
                  confidence={fieldConfidence.subtotal}
                  source={fieldSources.subtotal}
                />
              </dd>
            </div>
            <div>
              <dt>現金売上</dt>
              <dd>
                <OcrFieldConfidenceValue
                  value={formatCurrency(row.cash_sales)}
                  confidence={fieldConfidence.cash_sales}
                  source={fieldSources.cash_sales}
                />
              </dd>
            </div>
            <div>
              <dt>PAYGATE POS</dt>
              <dd>
                <OcrFieldConfidenceValue
                  value={formatCurrency(row.pos_sales)}
                  confidence={fieldConfidence.pos_sales}
                  source={fieldSources.pos_sales}
                />
              </dd>
            </div>
            <div>
              <dt>端末識別番号</dt>
              <dd>
                <OcrFieldConfidenceValue
                  value={row.terminal_short_id || "—"}
                  confidence={fieldConfidence.terminal_short_id}
                  source={fieldSources.terminal_short_id}
                />
              </dd>
            </div>
            <div className="ocr-row-review-readonly-wide">
              <dt>端末番号</dt>
              <dd className="ocr-row-review-uuid">
                <OcrFieldConfidenceValue
                  value={row.terminal_id || "—"}
                  confidence={fieldConfidence.terminal_id}
                  source={fieldSources.terminal_id}
                />
              </dd>
            </div>
          </>
        ) : (
          <>
            <div>
              <dt>取引番号</dt>
              <dd>{row.transaction_no || "—"}</dd>
            </div>
            <div>
              <dt>レシート番号</dt>
              <dd>{row.receipt_no || "—"}</dd>
            </div>
            <div>
              <dt>決済方法</dt>
              <dd>{row.payment_method || "—"}</dd>
            </div>
          </>
        )}
      </dl>
    </div>
  );
}

export function OcrSavedRowReviewModal({
  row,
  onClose,
  onSaved,
  onConfirm,
  confirming,
  onReparse,
  reparsing,
}: {
  row: OcrExtractedRowItem;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
  onConfirm: () => Promise<void> | void;
  confirming: boolean;
  onReparse?: () => void;
  reparsing?: boolean;
}) {
  const isSettlement = row.source_type === "paygate_settlement";
  const { url, failed } = useOcrImageBlobUrl(row.source_image_id);
  const [draft, setDraft] = useState<OcrRowEditDraft>(() => createOcrRowEditDraft(row));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const confirmable = isOcrRowConfirmable(row);

  useEffect(() => {
    setDraft(createOcrRowEditDraft(row));
    setError(null);
  }, [row]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await updateOcrRow(row.id, buildOcrRowUpdateBody(row, draft));
      await onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleConfirm = async () => {
    if (!confirmable) {
      setError("要確認の項目があります。内容を修正して保存してから確定してください。");
      return;
    }
    setError(null);
    try {
      await onConfirm();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "確定に失敗しました");
    }
  };

  const alt = row.source_image_filename || row.source_image_id;

  return createPortal(
    <div
      className="ocr-row-review-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ocr-row-review-title"
      onClick={onClose}
    >
      <div className="ocr-row-review-panel" onClick={(event) => event.stopPropagation()}>
        <button type="button" className="ocr-row-review-close" onClick={onClose} aria-label="閉じる">
          ×
        </button>
        <div className="ocr-row-review-image-pane">
          {failed ? (
            <div className="ocr-row-review-image-fallback">画像を読み込めませんでした</div>
          ) : url ? (
            <img src={url} alt={alt} className="ocr-row-review-image" />
          ) : (
            <div className="ocr-row-review-image-fallback" aria-hidden="true">
              読み込み中...
            </div>
          )}
        </div>
        <div className="ocr-row-review-data-pane">
          <h3 id="ocr-row-review-title">{isSettlement ? "精算レシートを確認" : "OCR行を確認"}</h3>
          <OcrRowReviewSummary row={row} />
          <h4 className="ocr-row-review-edit-heading">読取データの編集</h4>
          <OcrRowEditForm row={row} draft={draft} onDraftChange={setDraft} />
          {error ? <p className="ocr-warning-text">{error}</p> : null}
          <div className="ocr-modal-actions ocr-row-review-actions">
            <button type="button" className="ghost-button" onClick={onClose} disabled={saving || confirming}>
              閉じる
            </button>
            {isSettlement && row.status !== "confirmed" && onReparse ? (
              <button type="button" className="secondary-button" onClick={onReparse} disabled={reparsing || saving}>
                {reparsing ? "再解析中..." : "再解析"}
              </button>
            ) : null}
            <button type="button" className="secondary-button" onClick={handleSave} disabled={saving || confirming}>
              {saving ? "保存中..." : "保存"}
            </button>
            {row.status !== "confirmed" ? (
              <button
                type="button"
                className="primary-button"
                onClick={handleConfirm}
                disabled={saving || confirming || !confirmable}
                title={confirmable ? "問題なしとして確定します" : "要確認項目を解消してから確定できます"}
              >
                {confirming ? "確定中..." : "問題なしで確定"}
              </button>
            ) : (
              <span className="ocr-row-review-confirmed-note">確定済み</span>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
