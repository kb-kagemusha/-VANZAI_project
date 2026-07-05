import { useEffect, useMemo, useState, type HTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { ApiError, fetchOcrImageBlobUrl, updateOcrRow } from "../../lib/api/client";
import { formatCurrency } from "../../lib/formatters";
import { getOcrRowDisplayLabels, isOcrRowConfirmable } from "../../lib/ocr/rowDisplay";
import type { OcrParseProgressState } from "../../lib/ocr/batchParse";
import { normalizeTerminalShortIdInput } from "../../lib/ocr/terminalShortId";
import { formatOcrValidationMessages } from "../../lib/ocr/validationMessages";
import type { OcrExtractedRowItem } from "../../types/api";
import { OcrParseProgressHover } from "../OcrParseProgressHover";
import { StatusBadge } from "../StatusBadge";
import { OcrFieldConfidenceLegend, OcrFieldConfidenceValue } from "./OcrFieldConfidence";
import {
  buildOcrRowUpdateBody,
  createOcrRowEditDraft,
  type OcrRowEditDraft,
} from "./OcrRowEditForm";
import { formatTerminalIdDraftLines, SettlementTerminalIdDisplay } from "./SettlementTerminalIdDisplay";

type EditableFieldKey = keyof OcrRowEditDraft;

type ReviewFieldSpec = {
  key: EditableFieldKey;
  label: string;
  confidenceKey?: string;
  monospace?: boolean;
  inputType?: string;
  inputMode?: HTMLAttributes<HTMLInputElement>["inputMode"];
  maxLength?: number;
  placeholder?: string;
  formatDisplay: (draft: OcrRowEditDraft) => string;
  normalizeInput?: (value: string) => string;
  renderDisplay?: (args: {
    draft: OcrRowEditDraft;
    row: OcrExtractedRowItem;
    confidence?: number;
    source?: string | null;
  }) => ReactNode;
};

const SETTLEMENT_REVIEW_FIELDS: ReviewFieldSpec[] = [
  {
    key: "terminal_short_id",
    label: "端末識別番号",
    confidenceKey: "terminal_short_id",
    maxLength: 4,
    formatDisplay: (draft) => draft.terminal_short_id || "—",
    normalizeInput: normalizeTerminalShortIdInput,
  },
  {
    key: "record_date",
    label: "精算日",
    confidenceKey: "record_datetime",
    inputType: "date",
    formatDisplay: (draft) => draft.record_date || "—",
  },
  {
    key: "record_time",
    label: "精算時間",
    confidenceKey: "record_datetime",
    placeholder: "20:52:59",
    formatDisplay: (draft) => draft.record_time || "—",
  },
  {
    key: "terminal_id",
    label: "端末番号",
    confidenceKey: "terminal_id",
    monospace: true,
    formatDisplay: (draft) => draft.terminal_id || "—",
    renderDisplay: ({ draft, row, confidence, source }) => (
      <SettlementTerminalIdDisplay
        row={{
          ...row,
          terminal_id: draft.terminal_id || row.terminal_id,
        }}
        confidence={confidence}
        source={source}
      />
    ),
  },
  {
    key: "subtotal",
    label: "小計",
    confidenceKey: "subtotal",
    formatDisplay: (draft) => (draft.subtotal ? formatCurrency(draft.subtotal) : "—"),
  },
  {
    key: "amount",
    label: "合計",
    confidenceKey: "amount",
    formatDisplay: (draft) => (draft.amount ? formatCurrency(draft.amount) : "—"),
  },
  {
    key: "cash_sales",
    label: "現金売上",
    confidenceKey: "cash_sales",
    formatDisplay: (draft) => (draft.cash_sales ? formatCurrency(draft.cash_sales) : "—"),
  },
  {
    key: "pos_sales",
    label: "PAYGATE POS",
    confidenceKey: "pos_sales",
    formatDisplay: (draft) => (draft.pos_sales ? formatCurrency(draft.pos_sales) : "—"),
  },
  {
    key: "transaction_count",
    label: "通常取引数",
    confidenceKey: "transaction_count",
    inputMode: "numeric",
    formatDisplay: (draft) => draft.transaction_count || "—",
  },
];

const SCREENSHOT_REVIEW_FIELDS: ReviewFieldSpec[] = [
  {
    key: "record_date",
    label: "日付",
    confidenceKey: "record_datetime",
    inputType: "date",
    formatDisplay: (draft) => draft.record_date || "—",
  },
  {
    key: "record_time",
    label: "時刻",
    confidenceKey: "record_datetime",
    placeholder: "20:52:59",
    formatDisplay: (draft) => draft.record_time || "—",
  },
  {
    key: "amount",
    label: "金額",
    confidenceKey: "amount",
    formatDisplay: (draft) => (draft.amount ? formatCurrency(draft.amount) : "—"),
  },
  {
    key: "transaction_no",
    label: "取引番号",
    confidenceKey: "transaction_no",
    inputMode: "numeric",
    formatDisplay: (draft) => draft.transaction_no || "—",
  },
  {
    key: "receipt_no",
    label: "レシート番号",
    confidenceKey: "receipt_no",
    inputMode: "numeric",
    monospace: true,
    formatDisplay: (draft) => draft.receipt_no || "—",
  },
  {
    key: "payment_method",
    label: "決済方法",
    confidenceKey: "payment_method",
    formatDisplay: (draft) => draft.payment_method || "—",
  },
];

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

function OcrReviewFieldRow({
  spec,
  draft,
  row,
  confidence,
  source,
  editing,
  disabled,
  onStartEdit,
  onApply,
  onCancel,
  onDraftChange,
}: {
  spec: ReviewFieldSpec;
  draft: OcrRowEditDraft;
  row: OcrExtractedRowItem;
  confidence?: number | null;
  source?: string | null;
  editing: boolean;
  disabled?: boolean;
  onStartEdit: () => void;
  onApply: () => void;
  onCancel: () => void;
  onDraftChange: (value: string) => void;
}) {
  const value = draft[spec.key];
  const displayValue = spec.formatDisplay(draft);
  const customDisplay = spec.renderDisplay?.({
    draft,
    row,
    confidence: confidence ?? undefined,
    source,
  });

  return (
    <div className={`ocr-row-review-field-row${editing ? " ocr-row-review-field-row--editing" : ""}`}>
      <span className="ocr-row-review-field-label">{spec.label}</span>
      {editing ? (
        <>
          {spec.key === "terminal_id" ? (
            <div className="ocr-terminal-id-edit-preview" aria-hidden="true">
              {formatTerminalIdDraftLines(value, row.terminal_id_segments, row.terminal_id_partial).map((line, index) =>
                line && line !== "—" ? (
                  <span key={index} className="ocr-terminal-id-display-line">
                    {line}
                  </span>
                ) : null,
              )}
            </div>
          ) : null}
          <input
            type={spec.inputType || "text"}
            className={`ocr-row-review-field-input${spec.monospace ? " ocr-row-review-field-input--mono" : ""}`}
            value={value}
            maxLength={spec.maxLength}
            inputMode={spec.inputMode}
            placeholder={spec.placeholder}
            autoFocus
            disabled={disabled}
            onChange={(event) => {
              const next = spec.normalizeInput ? spec.normalizeInput(event.target.value) : event.target.value;
              onDraftChange(next);
            }}
          />
          <div className="ocr-row-review-field-actions">
            <button type="button" className="ghost-button" onClick={onApply} disabled={disabled}>
              適用
            </button>
            <button type="button" className="ghost-button" onClick={onCancel} disabled={disabled}>
              取消
            </button>
          </div>
        </>
      ) : (
        <>
          <span className={`ocr-row-review-field-value${spec.monospace ? " ocr-row-review-field-value--mono" : ""}`}>
            {customDisplay ? (
              customDisplay
            ) : confidence != null ? (
              <OcrFieldConfidenceValue value={displayValue} confidence={confidence} source={source} />
            ) : (
              displayValue
            )}
          </span>
          <button
            type="button"
            className="ghost-button ocr-row-review-field-edit"
            onClick={onStartEdit}
            disabled={disabled}
            aria-label={`${spec.label}を編集`}
          >
            編集
          </button>
        </>
      )}
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
  reparseProgress,
}: {
  row: OcrExtractedRowItem;
  onClose: () => void;
  onSaved: () => Promise<void> | void;
  onConfirm: () => Promise<void> | void;
  confirming: boolean;
  onReparse?: () => void;
  reparsing?: boolean;
  reparseProgress?: OcrParseProgressState | null;
}) {
  const isSettlement = row.source_type === "paygate_settlement";
  const { url, failed } = useOcrImageBlobUrl(row.source_image_id);
  const [savedDraft, setSavedDraft] = useState<OcrRowEditDraft>(() => createOcrRowEditDraft(row));
  const [draft, setDraft] = useState<OcrRowEditDraft>(() => createOcrRowEditDraft(row));
  const [editingField, setEditingField] = useState<EditableFieldKey | null>(null);
  const [editSnapshot, setEditSnapshot] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const confirmable = isOcrRowConfirmable(row);

  const fieldSpecs = isSettlement ? SETTLEMENT_REVIEW_FIELDS : SCREENSHOT_REVIEW_FIELDS;
  const fieldConfidence = row.field_confidence ?? {};
  const fieldSources = row.field_sources ?? {};
  const labels = getOcrRowDisplayLabels(row);
  const validationMessages =
    row.source_type === "paygate_settlement"
      ? [...(row.blocking_errors || []), ...(row.warnings || [])]
      : row.validation_errors || [];

  const isDirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(savedDraft), [draft, savedDraft]);

  useEffect(() => {
    const next = createOcrRowEditDraft(row);
    setSavedDraft(next);
    setDraft(next);
    setEditingField(null);
    setError(null);
  }, [row]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (editingField) {
          setDraft((current) => ({ ...current, [editingField]: editSnapshot }));
          setEditingField(null);
          return;
        }
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editSnapshot, editingField, onClose]);

  const startEdit = (key: EditableFieldKey) => {
    setEditingField(key);
    setEditSnapshot(draft[key]);
  };

  const applyEdit = () => {
    setEditingField(null);
  };

  const cancelEdit = (key: EditableFieldKey) => {
    setDraft((current) => ({ ...current, [key]: editSnapshot }));
    setEditingField(null);
  };

  const handleSave = async () => {
    if (editingField) {
      setError("編集中の項目を適用または取消してから保存してください。");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateOcrRow(row.id, buildOcrRowUpdateBody(row, draft));
      setSavedDraft(draft);
      await onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  const handleConfirm = async () => {
    if (editingField) {
      setError("編集中の項目を適用または取消してから確定してください。");
      return;
    }
    if (isDirty) {
      setError("変更を保存してから確定してください。");
      return;
    }
    if (!confirmable || row.terminal_id_partial) {
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
  const busy = saving || confirming || reparsing;

  return createPortal(
    <div
      className="ocr-row-review-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ocr-row-review-title"
      onClick={onClose}
    >
      <div className={`ocr-row-review-panel${reparsing ? " ocr-row-review-panel--reparsing" : ""}`} onClick={(event) => event.stopPropagation()}>
        <button type="button" className="ocr-row-review-close" onClick={onClose} aria-label="閉じる">
          ×
        </button>
        <div className="ocr-row-review-image-pane">
          {reparsing ? (
            <div className="ocr-row-review-reparse-overlay" aria-live="polite">
              <span className="ocr-row-review-reparse-spinner" aria-hidden="true" />
              <span>再解析中...</span>
            </div>
          ) : null}
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
          <h3 id="ocr-row-review-title">
            {isSettlement ? "精算レシートを確認" : "Paygate SSを確認"}
          </h3>
          <div className="ocr-row-review-summary">
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
            {validationMessages.length ? (
              <p className="ocr-warning-text ocr-row-review-validation">{formatOcrValidationMessages(validationMessages)}</p>
            ) : (
              <p className="ocr-row-review-validation ocr-row-review-validation--ok">検証: OK</p>
            )}
            <OcrFieldConfidenceLegend />
          </div>
          <div className="ocr-row-review-fields" role="list">
            {fieldSpecs.map((spec) => (
              <OcrReviewFieldRow
                key={spec.key}
                spec={spec}
                draft={draft}
                row={row}
                confidence={spec.confidenceKey ? fieldConfidence[spec.confidenceKey] : undefined}
                source={spec.confidenceKey ? fieldSources[spec.confidenceKey] : undefined}
                editing={editingField === spec.key}
                disabled={busy}
                onStartEdit={() => startEdit(spec.key)}
                onApply={applyEdit}
                onCancel={() => cancelEdit(spec.key)}
                onDraftChange={(value) => setDraft((current) => ({ ...current, [spec.key]: value }))}
              />
            ))}
          </div>
          {error ? <p className="ocr-warning-text">{error}</p> : null}
          {isDirty ? <p className="ocr-row-review-dirty-note">未保存の変更があります</p> : null}
          <div className="ocr-modal-actions ocr-row-review-actions">
            <button type="button" className="ghost-button" onClick={onClose} disabled={busy}>
              閉じる
            </button>
            {isSettlement && row.status !== "confirmed" && onReparse ? (
              <OcrParseProgressHover progress={reparseProgress ?? null} active={Boolean(reparsing)}>
                <button
                  type="button"
                  className={`secondary-button${reparsing ? " ocr-reparse-button--active" : ""}`}
                  onClick={onReparse}
                  disabled={busy}
                >
                  {reparsing ? "再解析中..." : "再解析"}
                </button>
              </OcrParseProgressHover>
            ) : null}
            <button type="button" className="secondary-button" onClick={handleSave} disabled={busy || !isDirty}>
              {saving ? "保存中..." : "保存"}
            </button>
            {row.status !== "confirmed" ? (
              <button
                type="button"
                className="primary-button"
                onClick={handleConfirm}
                disabled={busy || !confirmable || isDirty || row.terminal_id_partial}
                title={
                  row.terminal_id_partial
                    ? "端末番号が部分抽出のため確定できません"
                    : confirmable
                      ? "問題なしとして確定します"
                      : "要確認項目を解消してから確定できます"
                }
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
