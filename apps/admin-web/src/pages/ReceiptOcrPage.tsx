import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Navigate } from "react-router-dom";

import { ConfirmDialog } from "../components/ConfirmDialog";
import { DataTable } from "../components/DataTable";
import { AppNotification, type AppNotificationState } from "../components/AppNotification";
import { ErrorState } from "../components/ErrorState";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { OcrSavedRowReviewModal } from "../components/ocr/OcrSavedRowReviewModal";
import { OcrFieldConfidenceLegend } from "../components/ocr/OcrFieldConfidence";
import { OcrRowConfidenceCell } from "../components/ocr/OcrRowConfidenceCell";
import { SettlementTerminalIdDisplay } from "../components/ocr/SettlementTerminalIdDisplay";
import {
  OcrRowEditForm,
  buildOcrRowUpdateBody,
  createOcrRowEditDraft,
} from "../components/ocr/OcrRowEditForm";
import {
  createSingleImageParseProgress,
  OcrParseProgressHover,
} from "../components/OcrParseProgressHover";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  ApiError,
  compareOcrSelfReport,
  confirmOcrRows,
  createInventorySnapshot,
  deleteInventorySnapshot,
  deleteOcrImages,
  deleteOcrRows,
  downloadAllOcrCsv,
  downloadOcrCsv,
  downloadSettlementCsv,
  fetchOcrImageBlobUrl,
  getOcrMonthlySummary,
  listInventorySnapshots,
  listOcrImages,
  listOcrRows,
  parseOcrImages,
  reparseOcrRow,
  reparseOcrImage,
  renameOcrImage,
  runInventoryReconciliation,
  runOcrReconciliation,
  setOcrRowReconciliationEligibility,
  updateInventorySnapshot,
  updateInventoryReconciliationResult,
  updateOcrRow,
  uploadOcrImage,
  voidOcrRow,
} from "../lib/api/client";
import { formatRequestError } from "../lib/formatRequestError";
import { formatCurrency, formatDateTime, formatYenAmountPlain } from "../lib/formatters";
import {
  runBatchedOcrParse,
  type OcrBatchParseResult,
  type OcrParseProgressState,
} from "../lib/ocr/batchParse";
import { getOcrRowDisplayLabels, isOcrRowConfirmable, isOcrRowDeletable } from "../lib/ocr/rowDisplay";
import { formatOcrImageErrorMessage, formatOcrValidationMessages, formatUnitBreakdownStatus } from "../lib/ocr/validationMessages";
import { normalizeTerminalShortIdInput } from "../lib/ocr/terminalShortId";
import {
  nextSortDirection,
  OCR_ROW_SORTABLE_COLUMNS,
  sortOcrRows,
  type OcrRowSortKey,
  type SortDirection,
} from "../lib/ocr/sortRows";
import type {
  InventoryReconciliationResultItem,
  InventorySnapshotItem,
  OcrExtractedRowItem,
  OcrSourceImageItem,
  OcrSourceType,
} from "../types/api";

const DIFF_REASON_CATEGORY_LABELS: Record<string, string> = {
  ocr_error: "OCR読取ミス",
  inventory_input_error: "実在庫入力ミス",
  receipt_missing: "レシート不足",
  image_duplicate: "画像重複",
  partial_settlement: "途中精算",
  terminal_mismatch: "端末違い",
  staff_mismatch: "担当者違い",
  loss_damage: "紛失・破損",
  unclassified: "未分類",
};

const MATCH_STATUS_LABELS: Record<string, string> = {
  matched: "一致",
  adjusted_matched: "調整済み一致",
  count_mismatch: "差異あり",
  sales_only: "OCRのみ",
  inventory_only: "在庫のみ",
  excluded: "除外",
};

function formatMatchStatus(value: string) {
  return MATCH_STATUS_LABELS[value] || value;
}

type PendingUpload = {
  key: string;
  file: File;
  sourceType: OcrSourceType;
  previewUrl: string;
};

const SOURCE_LABELS: Record<OcrSourceType, string> = {
  paygate_screenshot: "Paygate",
  paygate_settlement: "レシート",
};

const OCR_FILENAME_DISPLAY_MAX = 24;

function truncateOcrFilename(filename: string, maxLength = OCR_FILENAME_DISPLAY_MAX) {
  if (filename.length <= maxLength) {
    return filename;
  }
  return `${filename.slice(0, maxLength)}・・・`;
}

function stripOcrFilenameExtension(filename: string) {
  return filename.replace(/\.[^./\\]+$/i, "");
}

function formatOcrFilenameDisplay(filename: string, hideExtension = false) {
  const displayName = hideExtension ? stripOcrFilenameExtension(filename) : filename;
  return truncateOcrFilename(displayName);
}

const IMAGE_PAGE_SIZES = [10, 20, 50] as const;
type ImagePageSize = (typeof IMAGE_PAGE_SIZES)[number];
const SAVED_ROW_PAGE_SIZES = [10, 20, 50] as const;
type SavedRowPageSize = (typeof SAVED_ROW_PAGE_SIZES)[number];
type ImageViewMode = "thumbnail" | "compact";

const IMAGE_VIEW_MODE_KEY = "vanzai.ocr.imageViewMode";
const IMAGE_PAGE_SIZE_KEY = "vanzai.ocr.imagePageSize";
const SAVED_ROW_PAGE_SIZE_KEY = "vanzai.ocr.savedRowPageSize";
const SAVED_ROW_UI_KEY_PREFIX = "vanzai.ocr.savedRowUi";

type SavedRowValidationFilter = "" | "ok" | "error";

type SavedRowFilters = {
  terminalShortId: string;
  status: string;
  validation: SavedRowValidationFilter;
  keyword: string;
};

const DEFAULT_SAVED_ROW_FILTERS: SavedRowFilters = {
  terminalShortId: "",
  status: "",
  validation: "",
  keyword: "",
};

function savedRowUiKey(sourceType: OcrSourceType) {
  return `${SAVED_ROW_UI_KEY_PREFIX}.${sourceType}`;
}

function readStoredPageSize(key: string, allowed: readonly number[], fallback: number) {
  try {
    const stored = window.localStorage.getItem(key);
    if (!stored) {
      return fallback;
    }
    const parsed = Number(stored);
    return allowed.includes(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function writeStoredPageSize(key: string, size: number) {
  try {
    window.localStorage.setItem(key, String(size));
  } catch {
    // private browsing 等
  }
}

type SavedRowUiPersist = {
  page: number;
  filters: SavedRowFilters;
};

function readSavedRowUi(sourceType: OcrSourceType): SavedRowUiPersist | null {
  try {
    const raw = window.sessionStorage.getItem(savedRowUiKey(sourceType));
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<SavedRowUiPersist>;
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    return {
      page: typeof parsed.page === "number" && parsed.page >= 0 ? parsed.page : 0,
      filters: { ...DEFAULT_SAVED_ROW_FILTERS, ...(parsed.filters || {}) },
    };
  } catch {
    return null;
  }
}

function writeSavedRowUi(sourceType: OcrSourceType, state: SavedRowUiPersist) {
  try {
    window.sessionStorage.setItem(savedRowUiKey(sourceType), JSON.stringify(state));
  } catch {
    // ignore
  }
}

const OCR_PARSE_STATUS_LABELS: Record<string, string> = {
  pending: "解析待ち",
  completed: "完了",
  failed: "失敗",
};

function formatOcrParseStatus(value: string) {
  return OCR_PARSE_STATUS_LABELS[value] || value;
}


type PendingConfirm = {
  title: string;
  message: string;
  onConfirm: () => void;
};

function formatPeriodKey(periodKey: string) {
  if (periodKey.length !== 6) return periodKey;
  return `${periodKey.slice(0, 4)}年${periodKey.slice(4)}月`;
}

function OcrRowQualityBadges({ row }: { row: OcrExtractedRowItem }) {
  const labels = getOcrRowDisplayLabels(row);
  if (!labels.length) {
    return <span className="ocr-muted-text">—</span>;
  }
  return (
    <div className="ocr-row-labels">
      {labels.map((label) => (
        <span key={label.key} className={`ocr-quality-badge ocr-quality-badge--${label.tone}`}>
          {label.text}
        </span>
      ))}
    </div>
  );
}

function OcrRowEditModal({
  row,
  onClose,
  onSaved,
}: {
  row: OcrExtractedRowItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isSettlement = row.source_type === "paygate_settlement";
  const [draft, setDraft] = useState(() => createOcrRowEditDraft(row));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await updateOcrRow(row.id, buildOcrRowUpdateBody(row, draft));
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="ocr-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="ocr-modal-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ocr-row-edit-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="ocr-row-edit-title">{isSettlement ? "精算レシート行を編集" : "OCR行を編集"}</h3>
        <OcrRowEditForm row={row} draft={draft} onDraftChange={setDraft} />
        {error ? <p className="ocr-warning-text">{error}</p> : null}
        <div className="ocr-modal-actions">
          <button type="button" className="ghost-button" onClick={onClose} disabled={saving}>
            キャンセル
          </button>
          <button type="button" className="primary-button" onClick={handleSave} disabled={saving}>
            {saving ? "保存中..." : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

function OcrSortableHeader({
  label,
  active,
  direction,
  onClick,
}: {
  label: string;
  active: boolean;
  direction: SortDirection;
  onClick: () => void;
}) {
  return (
    <button type="button" className="ocr-sort-button" onClick={onClick} aria-pressed={active}>
      <span>{label}</span>
      <span className="ocr-sort-indicator" aria-hidden="true">
        {active ? (direction === "asc" ? "▲" : "▼") : "↕"}
      </span>
    </button>
  );
}

function DropZone({
  label,
  description,
  sourceType,
  files,
  onAddFiles,
  onRemove,
}: {
  label: string;
  description: string;
  sourceType: OcrSourceType;
  files: PendingUpload[];
  onAddFiles: (sourceType: OcrSourceType, files: FileList | File[]) => void;
  onRemove: (key: string) => void;
}) {
  const zoneFiles = files.filter((item) => item.sourceType === sourceType);

  return (
    <section
      className="ocr-drop-zone"
      onDragOver={(event) => {
        event.preventDefault();
        event.currentTarget.classList.add("drag-over");
      }}
      onDragLeave={(event) => {
        event.currentTarget.classList.remove("drag-over");
      }}
      onDrop={(event) => {
        event.preventDefault();
        event.currentTarget.classList.remove("drag-over");
        if (event.dataTransfer.files?.length) {
          onAddFiles(sourceType, event.dataTransfer.files);
        }
      }}
    >
      <div className="ocr-drop-zone-header">
        <h3>{label}</h3>
        <p>{description}</p>
      </div>
      <label className="ocr-drop-zone-input">
        <span>画像を選択またはドロップ</span>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          multiple
          onChange={(event) => {
            if (event.target.files?.length) {
              onAddFiles(sourceType, event.target.files);
              event.target.value = "";
            }
          }}
        />
      </label>
      {zoneFiles.length ? (
        <ul className="ocr-file-list">
          {zoneFiles.map((item) => (
            <li key={item.key}>
              <OcrImagePreview previewUrl={item.previewUrl} alt={item.file.name}>
                <img src={item.previewUrl} alt={item.file.name} className="ocr-thumb" />
              </OcrImagePreview>
              <div>
                <strong>{item.file.name}</strong>
                <p>{Math.round(item.file.size / 1024)} KB</p>
              </div>
              <button type="button" className="ghost-button" onClick={() => onRemove(item.key)}>
                削除
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="ocr-empty-hint">まだ画像がありません</p>
      )}
    </section>
  );
}

function useOcrImageBlobUrl(imageId: string) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    setUrl(null);
    setFailed(false);

    fetchOcrImageBlobUrl(imageId)
      .then((blobUrl) => {
        if (!active) {
          URL.revokeObjectURL(blobUrl);
          return;
        }
        objectUrl = blobUrl;
        setUrl(blobUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [imageId]);

  return { url, failed };
}

function useOcrPreviewPosition(
  anchorRef: React.RefObject<HTMLElement | null>,
  visible: boolean,
) {
  const [style, setStyle] = useState<CSSProperties>({ visibility: "hidden" });

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;

    const rect = anchor.getBoundingClientRect();
    const gap = 10;
    const pad = 12;
    const maxWidth = Math.min(360, window.innerWidth - pad * 2);
    const maxHeight = Math.min(480, window.innerHeight - pad * 2);
    const clampLeft = (left: number) => Math.max(pad, Math.min(left, window.innerWidth - maxWidth - pad));
    const clampTop = (top: number) => Math.max(pad, Math.min(top, window.innerHeight - maxHeight - pad));

    const candidates: CSSProperties[] = [
      {
        left: rect.right + gap,
        top: clampTop(rect.top + rect.height / 2 - maxHeight / 2),
        transform: undefined,
      },
      {
        left: rect.left - maxWidth - gap,
        top: clampTop(rect.top + rect.height / 2 - maxHeight / 2),
        transform: undefined,
      },
      {
        left: clampLeft(rect.left),
        top: rect.bottom + gap,
        transform: undefined,
      },
      {
        left: clampLeft(rect.left),
        bottom: window.innerHeight - rect.top + gap,
        top: "auto",
        maxHeight: Math.min(maxHeight, Math.max(120, rect.top - pad - gap)),
        transform: undefined,
      },
    ];

    const fits = [
      rect.right + gap + maxWidth <= window.innerWidth - pad,
      rect.left - maxWidth - gap >= pad,
      rect.bottom + gap + 160 <= window.innerHeight - pad,
      rect.top >= pad + 80,
    ];

    const chosenIndex = fits.findIndex(Boolean);
    const chosen = candidates[chosenIndex >= 0 ? chosenIndex : 0];

    setStyle({
      position: "fixed",
      width: maxWidth,
      maxHeight,
      zIndex: 10000,
      visibility: "visible",
      ...chosen,
    });
  }, [anchorRef]);

  useEffect(() => {
    if (!visible) {
      setStyle({ visibility: "hidden" });
      return;
    }

    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [visible, updatePosition]);

  return { style, updatePosition };
}

function OcrImageLightbox({
  previewUrl,
  alt,
  onClose,
}: {
  previewUrl: string;
  alt: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return createPortal(
    <div className="ocr-image-lightbox" role="dialog" aria-modal="true" aria-label={`${alt} の拡大表示`} onClick={onClose}>
      <div className="ocr-image-lightbox-panel" onClick={(event) => event.stopPropagation()}>
        <button type="button" className="ocr-image-lightbox-close" onClick={onClose} aria-label="閉じる">
          ×
        </button>
        <img src={previewUrl} alt={alt} className="ocr-image-lightbox-image" />
      </div>
    </div>,
    document.body,
  );
}

function OcrImagePreview({
  alt,
  previewUrl,
  children,
  className,
  onClickPreview,
}: {
  alt: string;
  previewUrl: string | null;
  children: ReactNode;
  className?: string;
  onClickPreview?: () => void;
}) {
  const anchorRef = useRef<HTMLButtonElement>(null);
  const [hovering, setHovering] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const showHoverPreview = hovering && !lightboxOpen && Boolean(previewUrl);
  const { style, updatePosition } = useOcrPreviewPosition(anchorRef, showHoverPreview);

  const hoverPopover =
    showHoverPreview && previewUrl ? (
      <span
        className="ocr-image-preview-popover ocr-image-preview-popover--portal"
        style={style}
        role="tooltip"
      >
        <img src={previewUrl} alt={alt} onLoad={updatePosition} />
      </span>
    ) : null;

  return (
    <>
      <span
        className={["ocr-image-preview-trigger", className].filter(Boolean).join(" ")}
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
      >
        <button
          ref={anchorRef}
          type="button"
          className="ocr-image-preview-button"
          aria-label={`${alt} の画像を拡大表示`}
          aria-haspopup="dialog"
          disabled={!previewUrl}
          onClick={(event) => {
            event.stopPropagation();
            if (!previewUrl) {
              return;
            }
            if (onClickPreview) {
              onClickPreview();
              return;
            }
            setLightboxOpen(true);
          }}
        >
          {children}
        </button>
        {hoverPopover ? createPortal(hoverPopover, document.body) : null}
      </span>
      {lightboxOpen && previewUrl ? (
        <OcrImageLightbox previewUrl={previewUrl} alt={alt} onClose={() => setLightboxOpen(false)} />
      ) : null}
    </>
  );
}

function OcrImageThumbnail({
  alt,
  url,
  failed,
}: {
  alt: string;
  url: string | null;
  failed: boolean;
}) {
  if (failed) {
    return <div className="ocr-thumb ocr-thumb-fallback">No img</div>;
  }
  if (!url) {
    return <div className="ocr-thumb ocr-thumb-loading" aria-hidden="true" />;
  }
  return <img src={url} alt={alt} className="ocr-thumb" loading="lazy" />;
}

function OcrImageThumbnailWithPreview({ imageId, alt }: { imageId: string; alt: string }) {
  const { url, failed } = useOcrImageBlobUrl(imageId);

  return (
    <OcrImagePreview previewUrl={url} alt={alt}>
      <OcrImageThumbnail alt={alt} url={url} failed={failed} />
    </OcrImagePreview>
  );
}

function OcrFilenamePreviewLink({
  imageId,
  filename,
  hideExtension = false,
  clampLines = false,
  onClickPreview,
}: {
  imageId: string;
  filename: string;
  hideExtension?: boolean;
  clampLines?: boolean;
  onClickPreview?: () => void;
}) {
  const displayName = hideExtension ? stripOcrFilenameExtension(filename) : filename;
  const { url } = useOcrImageBlobUrl(imageId);

  return (
    <OcrImagePreview
      previewUrl={url}
      alt={filename}
      className="ocr-image-preview-trigger--filename"
      onClickPreview={onClickPreview}
    >
      <span
        className={`ocr-filename-preview-link${clampLines ? " ocr-filename-clamp-2" : ""}`}
        title={displayName}
      >
        {formatOcrFilenameDisplay(filename, hideExtension)}
      </span>
    </OcrImagePreview>
  );
}

function OcrParseStatusBadge({ value }: { value: string }) {
  const tone =
    value === "completed"
      ? "positive"
      : value === "failed"
        ? "attention"
        : "neutral";
  return <span className={`status-badge ${tone}`}>{formatOcrParseStatus(value)}</span>;
}

function OcrImageFilenameEditor({
  image,
  onRename,
  isSaving,
}: {
  image: OcrSourceImageItem;
  onRename: (imageId: string, filename: string) => Promise<void>;
  isSaving: boolean;
}) {
  const fullName = image.original_filename || image.id;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(fullName);

  useEffect(() => {
    if (!editing) {
      setDraft(fullName);
    }
  }, [fullName, editing]);

  if (editing) {
    return (
      <div className="ocr-filename-editor">
        <input
          type="text"
          value={draft}
          maxLength={255}
          disabled={isSaving}
          onChange={(event) => setDraft(event.target.value)}
          aria-label="画像ファイル名"
        />
        <button
          type="button"
          className="ghost-button"
          disabled={isSaving || !draft.trim()}
          onClick={async () => {
            const name = draft.trim();
            if (!name) return;
            try {
              await onRename(image.id, name);
              setEditing(false);
            } catch {
              // エラーは親の mutation で formError に表示
            }
          }}
        >
          保存
        </button>
        <button
          type="button"
          className="ghost-button"
          disabled={isSaving}
          onClick={() => {
            setDraft(fullName);
            setEditing(false);
          }}
        >
          取消
        </button>
      </div>
    );
  }

  return (
    <div className="ocr-filename-display">
      <OcrFilenamePreviewLink imageId={image.id} filename={fullName} />
      <button type="button" className="ghost-button ocr-filename-edit" onClick={() => setEditing(true)}>
        名前変更
      </button>
    </div>
  );
}

function OcrUploadedImageItem({
  image,
  viewMode,
  selected,
  onToggle,
  onRename,
  onDelete,
  onReparse,
  isRenaming,
  isDeleting,
  isReparsing,
}: {
  image: OcrSourceImageItem;
  viewMode: ImageViewMode;
  selected: boolean;
  onToggle: () => void;
  onRename: (imageId: string, filename: string) => Promise<void>;
  onDelete: (imageId: string) => void;
  onReparse?: (imageId: string) => void;
  isRenaming: boolean;
  isDeleting: boolean;
  isReparsing: boolean;
}) {
  const isDuplicate = Boolean(image.reused_existing || image.has_filename_duplicate);
  const fileName = image.original_filename || image.id;
  const sourceLabel = SOURCE_LABELS[image.source_type as OcrSourceType] || image.source_type;
  const canReparse = image.parse_status === "completed" || image.parse_status === "failed";

  if (viewMode === "compact") {
    return (
      <li className={isDuplicate ? "ocr-image-row is-duplicate" : "ocr-image-row"}>
        <label className="ocr-image-row-select">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            aria-label={`${fileName} を選択`}
          />
        </label>
        <div className="ocr-image-row-main">
          <OcrImageFilenameEditor image={image} onRename={onRename} isSaving={isRenaming} />
          <span className="ocr-image-row-meta">{formatDateTime(image.created_at)}</span>
        </div>
        <div className="ocr-image-row-status">
          <OcrParseStatusBadge value={image.parse_status} />
          {isDuplicate ? (
            <span className="ocr-duplicate-badge-inline">
              {image.reused_existing ? "同一画像" : "同名"}
            </span>
          ) : null}
        </div>
        {image.error_message ? (
          <p className="ocr-image-error">{formatOcrImageErrorMessage(image.error_message)}</p>
        ) : null}
        <div className="ocr-image-row-actions">
          {canReparse && onReparse ? (
            <OcrParseProgressHover progress={null} active={isReparsing}>
              <button
                type="button"
                className="ghost-button"
                disabled={isReparsing || isDeleting}
                onClick={() => onReparse(image.id)}
              >
                {isReparsing ? "再解析中..." : "再解析"}
              </button>
            </OcrParseProgressHover>
          ) : null}
          <button
            type="button"
            className="ghost-button ocr-inline-delete"
            disabled={isDeleting || isReparsing}
            onClick={() => onDelete(image.id)}
          >
            削除
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className={isDuplicate ? "ocr-image-card is-duplicate" : "ocr-image-card"}>
      <div className="ocr-image-card-top">
        <label className="ocr-image-card-select">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            aria-label={`${fileName} を選択`}
          />
        </label>
        <OcrImageThumbnailWithPreview imageId={image.id} alt={fileName} />
      </div>
      <div className="ocr-image-card-body">
        <OcrImageFilenameEditor image={image} onRename={onRename} isSaving={isRenaming} />
        <div className="ocr-image-source">{sourceLabel}</div>
        <div className="ocr-image-status-row">
          <OcrParseStatusBadge value={image.parse_status} />
          <span className="ocr-image-meta">{formatDateTime(image.created_at)}</span>
        </div>
        {isDuplicate ? (
          <p className="ocr-duplicate-badge">
            {image.reused_existing ? "同一画像（再アップロード）" : "同名ファイルあり"}
          </p>
        ) : null}
        {image.error_message ? (
          <p className="ocr-image-error">{formatOcrImageErrorMessage(image.error_message)}</p>
        ) : null}
        <div className="ocr-image-row-actions">
          {canReparse && onReparse ? (
            <OcrParseProgressHover progress={null} active={isReparsing}>
              <button
                type="button"
                className="ghost-button"
                disabled={isReparsing || isDeleting}
                onClick={() => onReparse(image.id)}
              >
                {isReparsing ? "再解析中..." : "再解析"}
              </button>
            </OcrParseProgressHover>
          ) : null}
          <button
            type="button"
            className="ghost-button ocr-inline-delete"
            disabled={isDeleting || isReparsing}
            onClick={() => onDelete(image.id)}
          >
            削除
          </button>
        </div>
      </div>
    </li>
  );
}

function InventorySnapshotEditForm({
  snapshot,
  saving,
  onCancel,
  onSave,
}: {
  snapshot: InventorySnapshotItem;
  saving: boolean;
  onCancel: () => void;
  onSave: (body: {
    staff_id?: string | null;
    opening_count?: number;
    closing_count?: number;
    adjustment_count?: number;
    adjustment_reason?: string | null;
    note?: string | null;
  }) => void;
}) {
  const [draft, setDraft] = useState({
    staff_id: snapshot.staff_id || "",
    opening_count: String(snapshot.opening_count),
    closing_count: String(snapshot.closing_count),
    adjustment_count: String(snapshot.adjustment_count),
    adjustment_reason: snapshot.adjustment_reason || "",
    note: snapshot.note || "",
  });

  return (
    <>
      <div className="ocr-edit-grid">
        <label>
          稼働者ID
          <input value={draft.staff_id} onChange={(event) => setDraft((current) => ({ ...current, staff_id: event.target.value }))} />
        </label>
        <label>
          開始在庫
          <input
            type="number"
            value={draft.opening_count}
            onChange={(event) => setDraft((current) => ({ ...current, opening_count: event.target.value }))}
          />
        </label>
        <label>
          終了在庫
          <input
            type="number"
            value={draft.closing_count}
            onChange={(event) => setDraft((current) => ({ ...current, closing_count: event.target.value }))}
          />
        </label>
        <label>
          調整数（減少=正/増加=負）
          <input
            type="number"
            value={draft.adjustment_count}
            onChange={(event) => setDraft((current) => ({ ...current, adjustment_count: event.target.value }))}
          />
        </label>
        <label>
          調整理由
          <input
            value={draft.adjustment_reason}
            onChange={(event) => setDraft((current) => ({ ...current, adjustment_reason: event.target.value }))}
          />
        </label>
        <label>
          メモ
          <input value={draft.note} onChange={(event) => setDraft((current) => ({ ...current, note: event.target.value }))} />
        </label>
      </div>
      <div className="ocr-modal-actions">
        <button type="button" className="ghost-button" onClick={onCancel} disabled={saving}>
          キャンセル
        </button>
        <button
          type="button"
          className="primary-button"
          disabled={saving}
          onClick={() =>
            onSave({
              staff_id: draft.staff_id || null,
              opening_count: Number(draft.opening_count),
              closing_count: Number(draft.closing_count),
              adjustment_count: Number(draft.adjustment_count || 0),
              adjustment_reason: draft.adjustment_reason || null,
              note: draft.note || null,
            })
          }
        >
          {saving ? "保存中..." : "保存"}
        </button>
      </div>
    </>
  );
}

export function ReceiptOcrPage({ sourceType }: { sourceType: OcrSourceType }) {
  const queryClient = useQueryClient();
  const [pendingFiles, setPendingFiles] = useState<PendingUpload[]>([]);
  const [selectedImageIds, setSelectedImageIds] = useState<string[]>([]);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [selectedRowIds, setSelectedRowIds] = useState<string[]>([]);
  const [editingRow, setEditingRow] = useState<OcrExtractedRowItem | null>(null);
  const [reviewingRow, setReviewingRow] = useState<OcrExtractedRowItem | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [notification, setNotification] = useState<AppNotificationState & { open: boolean }>({
    open: false,
    tone: "info",
    title: "",
    message: "",
  });

  const showNotification = useCallback((next: AppNotificationState) => {
    setNotification({ ...next, open: true });
  }, []);

  const closeNotification = useCallback(() => {
    setNotification((current) => ({ ...current, open: false }));
  }, []);
  const [hqFile, setHqFile] = useState<File | null>(null);
  const [hqTxnColumn, setHqTxnColumn] = useState("取引番号");
  const [hqReceiptColumn, setHqReceiptColumn] = useState("レシート番号");
  const [hqDateColumn, setHqDateColumn] = useState("日時");
  const [hqAmountColumn, setHqAmountColumn] = useState("金額");
  const [reconcileResult, setReconcileResult] = useState<Awaited<ReturnType<typeof runOcrReconciliation>> | null>(null);
  const [comparePeriodKey, setComparePeriodKey] = useState("");
  const [imagesSectionCollapsed, setImagesSectionCollapsed] = useState(false);
  const [imageViewMode, setImageViewMode] = useState<ImageViewMode>(() => {
    const stored = window.localStorage.getItem(IMAGE_VIEW_MODE_KEY);
    return stored === "compact" ? "compact" : "thumbnail";
  });
  const [imagePageSize, setImagePageSize] = useState<ImagePageSize>(() =>
    readStoredPageSize(IMAGE_PAGE_SIZE_KEY, IMAGE_PAGE_SIZES, 20) as ImagePageSize,
  );
  const [imagePage, setImagePage] = useState(0);
  const [rowSortKey, setRowSortKey] = useState<OcrRowSortKey>("record_date");
  const [rowSortDirection, setRowSortDirection] = useState<SortDirection>("desc");
  const [savedRowPageSize, setSavedRowPageSize] = useState<SavedRowPageSize>(() =>
    readStoredPageSize(SAVED_ROW_PAGE_SIZE_KEY, SAVED_ROW_PAGE_SIZES, 20) as SavedRowPageSize,
  );
  const [savedRowPage, setSavedRowPage] = useState(() => readSavedRowUi(sourceType)?.page ?? 0);
  const [savedRowFilters, setSavedRowFilters] = useState<SavedRowFilters>(
    () => readSavedRowUi(sourceType)?.filters ?? DEFAULT_SAVED_ROW_FILTERS,
  );
  const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);
  const [parseProgress, setParseProgress] = useState<OcrParseProgressState | null>(null);
  const [parseResultSummary, setParseResultSummary] = useState<OcrBatchParseResult | null>(null);
  const [reparseProgress, setReparseProgress] = useState<OcrParseProgressState | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const isParsingRef = useRef(false);

  useEffect(() => {
    writeSavedRowUi(sourceType, { page: savedRowPage, filters: savedRowFilters });
  }, [sourceType, savedRowPage, savedRowFilters]);

  useEffect(() => {
    writeStoredPageSize(SAVED_ROW_PAGE_SIZE_KEY, savedRowPageSize);
  }, [savedRowPageSize]);

  const rowsQuery = useQuery({
    queryKey: ["ocr-rows", selectedPeriodKey],
    queryFn: () =>
      listOcrRows({
        period_key: selectedPeriodKey || undefined,
        limit: 500,
      }),
    placeholderData: keepPreviousData,
  });

  const summaryQuery = useQuery({
    queryKey: ["ocr-monthly-summary"],
    queryFn: getOcrMonthlySummary,
  });

  const imagesQuery = useQuery({
    queryKey: ["ocr-images", sourceType, imagePageSize, imagePage],
    queryFn: () =>
      listOcrImages({
        source_type: sourceType,
        limit: imagePageSize,
        offset: imagePage * imagePageSize,
      }),
  });

  const parseTargetsQuery = useQuery({
    queryKey: ["ocr-images-parse-targets", sourceType],
    queryFn: async () => {
      const [pending, failed] = await Promise.all([
        listOcrImages({ source_type: sourceType, parse_status: "pending", limit: 500 }),
        listOcrImages({ source_type: sourceType, parse_status: "failed", limit: 500 }),
      ]);
      const byId = new Map<string, OcrSourceImageItem>();
      for (const item of [...pending.items, ...failed.items]) {
        byId.set(item.id, item);
      }
      return Array.from(byId.values());
    },
  });

  const compareQuery = useQuery({
    queryKey: ["ocr-self-report-compare", comparePeriodKey],
    queryFn: () => compareOcrSelfReport(comparePeriodKey),
    enabled: comparePeriodKey.length === 6,
  });

  const addFiles = useCallback((sourceType: OcrSourceType, fileList: FileList | File[]) => {
    const next = Array.from(fileList).map((file) => ({
      key: `${sourceType}-${file.name}-${file.size}-${file.lastModified}`,
      file,
      sourceType,
      previewUrl: URL.createObjectURL(file),
    }));
    setPendingFiles((current) => {
      const existing = new Set(current.map((item) => item.key));
      return [...current, ...next.filter((item) => !existing.has(item.key))];
    });
  }, []);

  const removeFile = useCallback((key: string) => {
    setPendingFiles((current) => {
      const target = current.find((item) => item.key === key);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return current.filter((item) => item.key !== key);
    });
  }, []);

  const listRetryTargets = useCallback(async (candidateIds: string[]) => {
    if (!candidateIds.length) {
      return [];
    }
    const candidateSet = new Set(candidateIds);
    const [pending, failed] = await Promise.all([
      listOcrImages({ parse_status: "pending", limit: 500 }),
      listOcrImages({ parse_status: "failed", limit: 500 }),
    ]);
    const targets = new Set<string>();
    for (const item of [...pending.items, ...failed.items]) {
      if (candidateSet.has(item.id)) {
        targets.add(item.id);
      }
    }
    return Array.from(targets);
  }, []);

  const invalidateParseQueries = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["ocr-rows"] }),
      queryClient.invalidateQueries({ queryKey: ["ocr-monthly-summary"] }),
      queryClient.invalidateQueries({ queryKey: ["ocr-images"] }),
      queryClient.invalidateQueries({ queryKey: ["ocr-images-parse-targets"] }),
    ]);
  }, [queryClient]);

  const handleParseImages = useCallback(async () => {
    const images = parseTargetsQuery.data ?? [];
    if (!images.length || isParsingRef.current) {
      return;
    }

    isParsingRef.current = true;
    setIsParsing(true);
    setParseResultSummary(null);
    setFormError(null);

    try {
      const result = await runBatchedOcrParse({
        images,
        parseBatch: parseOcrImages,
        listRetryTargets,
        onProgress: setParseProgress,
      });
      setParseResultSummary(result);
      await invalidateParseQueries();
      setSelectedImageIds([]);

      if (result.timedOut) {
        const message = `10分の上限に達したため解析を中断しました。成功 ${result.successCount} 件 / 未完了・失敗 ${result.failedCount} 件。残りは再度「解析」を押してください。`;
        setFormError(message);
        showNotification({
          tone: "warning",
          title: "解析が時間上限で中断されました",
          message,
        });
        return;
      }

      if (result.failedCount > 0) {
        const message = `解析完了: 成功 ${result.successCount} 件 / 失敗 ${result.failedCount} 件。失敗した画像のエラー内容を下の一覧で確認してください。`;
        setFormError(message);
        showNotification({
          tone: "warning",
          title: "一部の画像の解析に失敗しました",
          message,
        });
        return;
      }

      setFormError(null);
    } catch (error) {
      const formatted = formatRequestError(error, "解析に失敗しました");
      setFormError(formatted.message);
      showNotification({
        tone: "error",
        title: formatted.title,
        message: formatted.message,
        detail: formatted.detail,
      });
    } finally {
      isParsingRef.current = false;
      setIsParsing(false);
    }
  }, [invalidateParseQueries, listRetryTargets, parseTargetsQuery.data, showNotification]);

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const images: OcrSourceImageItem[] = [];
      for (const item of pendingFiles.filter((file) => file.sourceType === sourceType)) {
        const uploaded = await uploadOcrImage(item.file, item.sourceType);
        images.push(uploaded);
      }
      return images;
    },
    onSuccess: async (images) => {
      pendingFiles.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      setPendingFiles([]);
      setFormError(null);
      const duplicateCount = images.filter((image) => image.reused_existing).length;
      if (duplicateCount > 0) {
        setFormError(`${duplicateCount}件は同一画像のため既存レコードを再利用しました`);
      }
      await queryClient.invalidateQueries({ queryKey: ["ocr-images"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-images-parse-targets"] });
    },
    onError: (error) => {
      const formatted = formatRequestError(error, "画像アップロードに失敗しました");
      setFormError(formatted.message);
      showNotification({
        tone: "error",
        title: formatted.title,
        message: formatted.message,
        detail: formatted.detail,
      });
    },
  });

  const reparseRowMutation = useMutation({
    mutationFn: async (rowId: string) => reparseOcrRow(rowId),
    onMutate: () => {
      setReparseProgress(createSingleImageParseProgress());
    },
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-monthly-summary"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-images"] });
      if (result.failed_count > 0) {
        const message = "再解析の結果、必要な項目を読み取れませんでした。画像一覧のエラー内容を確認してください。";
        setFormError(message);
        showNotification({
          tone: "warning",
          title: "再解析に失敗しました",
          message,
        });
        return;
      }
      setFormError(null);
    },
    onError: (error) => {
      const formatted = formatRequestError(error, "再解析に失敗しました");
      setFormError(formatted.message);
      showNotification({
        tone: "error",
        title: formatted.title,
        message: formatted.message,
        detail: formatted.detail,
      });
    },
    onSettled: (result, error) => {
      const failed = Boolean(error) || (result?.failed_count ?? 0) > 0;
      setReparseProgress((current) => {
        if (!current) {
          return null;
        }
        return {
          ...current,
          phase: "done",
          processedImages: 1,
          successCount: failed ? 0 : 1,
          failedCount: failed ? 1 : 0,
        };
      });
      window.setTimeout(() => setReparseProgress(null), 2500);
    },
  });

  const reparseImageMutation = useMutation({
    mutationFn: async (imageId: string) => reparseOcrImage(imageId),
    onMutate: () => {
      setReparseProgress(createSingleImageParseProgress());
    },
    onSuccess: async (result) => {
      await invalidateParseQueries();
      if (result.failed_count > 0) {
        const message = "再解析の結果、必要な項目を読み取れませんでした。画像のエラー内容を確認してください。";
        setFormError(message);
        showNotification({
          tone: "warning",
          title: "画像の再解析に失敗しました",
          message,
        });
        return;
      }
      setFormError(null);
      showNotification({
        tone: "success",
        title: "画像を再解析しました",
        message: `${result.row_count} 件のデータを読み込みました。`,
      });
    },
    onError: (error) => {
      const formatted = formatRequestError(error, "画像の再解析に失敗しました");
      setFormError(formatted.message);
      showNotification({
        tone: "error",
        title: formatted.title,
        message: formatted.message,
        detail: formatted.detail,
      });
    },
    onSettled: (result, error) => {
      const failed = Boolean(error) || (result?.failed_count ?? 0) > 0;
      setReparseProgress((current) => {
        if (!current) {
          return null;
        }
        return {
          ...current,
          phase: "done",
          processedImages: 1,
          successCount: failed ? 0 : 1,
          failedCount: failed ? 1 : 0,
        };
      });
      window.setTimeout(() => setReparseProgress(null), 2500);
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (rowIds: string[]) => confirmOcrRows(rowIds),
    onSuccess: async () => {
      setSelectedRowIds([]);
      setFormError(null);
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 422 && error.detail && typeof error.detail === "object") {
        const payload = error.detail as {
          rejected_row_ids?: string[];
          reasons?: Record<string, string[]>;
        };
        const count = payload.rejected_row_ids?.length ?? 0;
        setFormError(`確定できない行が ${count} 件含まれています。要確認行を修正してから再度お試しください。`);
        return;
      }
      setFormError(error instanceof ApiError ? error.message : "確定に失敗しました");
    },
  });

  const deleteRowsMutation = useMutation({
    mutationFn: (rowIds: string[]) => deleteOcrRows(rowIds),
    onSuccess: async (result) => {
      setSelectedRowIds([]);
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-monthly-summary"] });
      if (result.deleted_count === 0) {
        setFormError("削除対象の保存データが見つかりませんでした");
      } else {
        setFormError(null);
      }
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "保存データの削除に失敗しました");
    },
  });

  const deleteImagesMutation = useMutation({
    mutationFn: (imageIds: string[]) => deleteOcrImages(imageIds),
    onSuccess: async (result) => {
      setSelectedImageIds([]);
      await queryClient.invalidateQueries({ queryKey: ["ocr-images"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-images-parse-targets"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-monthly-summary"] });
      if (result.deleted_count === 0) {
        setFormError("削除対象の画像が見つかりませんでした");
      } else {
        setFormError(null);
      }
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "画像の削除に失敗しました");
    },
  });

  const renameImageMutation = useMutation({
    mutationFn: ({ imageId, filename }: { imageId: string; filename: string }) =>
      renameOcrImage(imageId, filename),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["ocr-images"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
      setFormError(null);
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "ファイル名の変更に失敗しました");
    },
  });

  const reconcileMutation = useMutation({
    mutationFn: async () => {
      if (!hqFile) throw new Error("本部CSVを選択してください");
      return runOcrReconciliation({
        file: hqFile,
        periodKey: selectedPeriodKey || undefined,
        columnMapping: {
          transaction_no: hqTxnColumn,
          receipt_no: hqReceiptColumn,
          record_date: hqDateColumn,
          amount: hqAmountColumn,
        },
      });
    },
    onSuccess: (result) => {
      setReconcileResult(result);
      setFormError(null);
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "突合に失敗しました");
    },
  });

  const voidRowMutation = useMutation({
    mutationFn: ({ rowId, reason }: { rowId: string; reason: string }) => voidOcrRow(rowId, reason),
    onSuccess: async () => {
      setFormError(null);
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "無効化に失敗しました");
    },
  });

  const setEligibilityMutation = useMutation({
    mutationFn: ({
      rowId,
      eligible,
      excludedReason,
    }: {
      rowId: string;
      eligible: boolean;
      excludedReason?: string | null;
    }) => setOcrRowReconciliationEligibility(rowId, eligible, excludedReason),
    onSuccess: async () => {
      setFormError(null);
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "在庫照合対象の切り替えに失敗しました");
    },
  });

  const handleVoidRow = (row: OcrExtractedRowItem) => {
    const reason = window.prompt(
      "この精算行を無効化します。理由を入力してください（誤アップロード・誤確定など）。",
      "",
    );
    if (reason === null) return;
    if (!reason.trim()) {
      setFormError("無効化には理由の入力が必須です");
      return;
    }
    voidRowMutation.mutate({ rowId: row.id, reason: reason.trim() });
  };

  const handleToggleReconciliationEligibility = (row: OcrExtractedRowItem) => {
    if (row.reconciliation_eligible) {
      const reason = window.prompt(
        "この行を在庫照合対象から除外します。理由を入力してください（途中精算・重複など）。",
        "",
      );
      if (reason === null) return;
      if (!reason.trim()) {
        setFormError("在庫照合対象から除外するには理由の入力が必須です");
        return;
      }
      setEligibilityMutation.mutate({ rowId: row.id, eligible: false, excludedReason: reason.trim() });
    } else {
      setEligibilityMutation.mutate({ rowId: row.id, eligible: true, excludedReason: null });
    }
  };

  // --- 実在庫入力・在庫照合（計画書 v4 Phase 2b） -------------------------

  const [inventoryFormError, setInventoryFormError] = useState<string | null>(null);
  const [inventoryDraft, setInventoryDraft] = useState({
    branch_id: "UNASSIGNED",
    terminal_short_id: "",
    work_date: "",
    staff_id: "",
    opening_count: "",
    closing_count: "",
    adjustment_count: "0",
    adjustment_reason: "",
    note: "",
  });
  const [editingSnapshot, setEditingSnapshot] = useState<InventorySnapshotItem | null>(null);
  const [reconcilePeriodKey, setReconcilePeriodKey] = useState("");
  const [reconcileDateFrom, setReconcileDateFrom] = useState("");
  const [reconcileDateTo, setReconcileDateTo] = useState("");
  const [reconciliationBatch, setReconciliationBatch] = useState<Awaited<
    ReturnType<typeof runInventoryReconciliation>
  > | null>(null);

  const snapshotsQuery = useQuery({
    queryKey: ["inventory-snapshots"],
    queryFn: () => listInventorySnapshots({ limit: 200 }),
  });

  const createSnapshotMutation = useMutation({
    mutationFn: () =>
      createInventorySnapshot({
        branch_id: inventoryDraft.branch_id || "UNASSIGNED",
        terminal_short_id: inventoryDraft.terminal_short_id,
        work_date: inventoryDraft.work_date,
        staff_id: inventoryDraft.staff_id || null,
        opening_count: Number(inventoryDraft.opening_count),
        closing_count: Number(inventoryDraft.closing_count),
        adjustment_count: Number(inventoryDraft.adjustment_count || 0),
        adjustment_reason: inventoryDraft.adjustment_reason || null,
        note: inventoryDraft.note || null,
      }),
    onSuccess: async () => {
      setInventoryFormError(null);
      setInventoryDraft((current) => ({
        ...current,
        terminal_short_id: "",
        work_date: "",
        staff_id: "",
        opening_count: "",
        closing_count: "",
        adjustment_count: "0",
        adjustment_reason: "",
        note: "",
      }));
      await queryClient.invalidateQueries({ queryKey: ["inventory-snapshots"] });
    },
    onError: (error) => {
      setInventoryFormError(error instanceof ApiError ? error.message : "実在庫記録の登録に失敗しました");
    },
  });

  const updateSnapshotMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateInventorySnapshot>[1] }) =>
      updateInventorySnapshot(id, body),
    onSuccess: async () => {
      setInventoryFormError(null);
      setEditingSnapshot(null);
      await queryClient.invalidateQueries({ queryKey: ["inventory-snapshots"] });
    },
    onError: (error) => {
      setInventoryFormError(error instanceof ApiError ? error.message : "実在庫記録の更新に失敗しました");
    },
  });

  const deleteSnapshotMutation = useMutation({
    mutationFn: (id: string) => deleteInventorySnapshot(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["inventory-snapshots"] });
    },
    onError: (error) => {
      setInventoryFormError(error instanceof ApiError ? error.message : "実在庫記録の削除に失敗しました");
    },
  });

  const runReconciliationMutation = useMutation({
    mutationFn: () =>
      runInventoryReconciliation({
        date_from: reconcileDateFrom || undefined,
        date_to: reconcileDateTo || undefined,
        period_key: reconcilePeriodKey || undefined,
      }),
    onSuccess: (batch) => {
      setReconciliationBatch(batch);
      setInventoryFormError(null);
    },
    onError: (error) => {
      setInventoryFormError(error instanceof ApiError ? error.message : "在庫照合の実行に失敗しました");
    },
  });

  const updateResultMutation = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string;
      body: Parameters<typeof updateInventoryReconciliationResult>[1];
    }) => updateInventoryReconciliationResult(id, body),
    onSuccess: (updated) => {
      setReconciliationBatch((current) =>
        current
          ? {
              ...current,
              results: current.results.map((result) => (result.id === updated.id ? updated : result)),
            }
          : current,
      );
    },
    onError: (error) => {
      setInventoryFormError(error instanceof ApiError ? error.message : "差異理由の更新に失敗しました");
    },
  });

  const uploadedImages = imagesQuery.data?.items ?? [];
  const totalImages = imagesQuery.data?.total ?? 0;
  const totalImagePages = Math.max(1, Math.ceil(totalImages / imagePageSize));

  const imageIdsToParse = useMemo(
    () => (parseTargetsQuery.data ?? []).map((image) => image.id),
    [parseTargetsQuery.data],
  );

  const allVisibleImagesSelected =
    uploadedImages.length > 0 && uploadedImages.every((image) => selectedImageIds.includes(image.id));

  const savedRows = rowsQuery.data?.items ?? [];
  const reviewingRowLive = useMemo(() => {
    if (!reviewingRow) {
      return null;
    }
    return savedRows.find((row) => row.id === reviewingRow.id) ?? reviewingRow;
  }, [reviewingRow, savedRows]);

  const reviewingRowSiblings = useMemo(() => {
    if (!reviewingRowLive) {
      return [];
    }
    return savedRows.filter((row) => row.source_image_id === reviewingRowLive.source_image_id);
  }, [reviewingRowLive, savedRows]);

  const invalidateSavedRowQueries = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["ocr-rows"] }),
      queryClient.invalidateQueries({ queryKey: ["ocr-images"] }),
    ]);
  }, [queryClient]);
  const tabSavedRows = useMemo(
    () => savedRows.filter((row) => row.source_type === sourceType),
    [savedRows, sourceType],
  );
  const filteredSavedRows = useMemo(() => {
    const terminalFilter = savedRowFilters.terminalShortId.trim().toLowerCase();
    const keyword = savedRowFilters.keyword.trim().toLowerCase();
    return tabSavedRows.filter((row) => {
      if (terminalFilter) {
        const shortId = (row.terminal_short_id || "").toLowerCase();
        if (shortId !== terminalFilter) {
          return false;
        }
      }
      if (savedRowFilters.status && row.status !== savedRowFilters.status) {
        return false;
      }
      if (savedRowFilters.validation === "ok") {
        const messages = [
          ...(row.blocking_errors || []),
          ...(row.warnings || []),
          ...(row.validation_errors || []),
        ];
        if (messages.length > 0 || row.confirm_required) {
          return false;
        }
      }
      if (savedRowFilters.validation === "error") {
        const messages = [
          ...(row.blocking_errors || []),
          ...(row.warnings || []),
          ...(row.validation_errors || []),
        ];
        if (messages.length === 0 && !row.confirm_required) {
          return false;
        }
      }
      if (keyword) {
        const haystack = [
          row.source_image_filename,
          row.terminal_short_id,
          row.terminal_id,
          row.transaction_no,
          row.receipt_no,
          row.store_name,
          row.period_key,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!haystack.includes(keyword)) {
          return false;
        }
      }
      return true;
    });
  }, [savedRowFilters, tabSavedRows]);
  const sortedSavedRows = useMemo(
    () => sortOcrRows(filteredSavedRows, rowSortKey, rowSortDirection),
    [filteredSavedRows, rowSortDirection, rowSortKey],
  );
  const totalSavedRowPages = Math.max(1, Math.ceil(sortedSavedRows.length / savedRowPageSize));
  const paginatedSavedRows = useMemo(() => {
    const start = savedRowPage * savedRowPageSize;
    return sortedSavedRows.slice(start, start + savedRowPageSize);
  }, [savedRowPage, savedRowPageSize, sortedSavedRows]);
  const confirmableRows = filteredSavedRows.filter((row) => isOcrRowConfirmable(row));
  const deletableRows = filteredSavedRows.filter((row) => isOcrRowDeletable(row));
  const allSavedRowsSelected =
    deletableRows.length > 0 && deletableRows.every((row) => selectedRowIds.includes(row.id));
  const allConfirmableRowsSelected =
    confirmableRows.length > 0 && confirmableRows.every((row) => selectedRowIds.includes(row.id));

  const handleDeleteImages = (imageIds: string[]) => {
    if (!imageIds.length) return;
    const message =
      imageIds.length === 1
        ? "この画像を削除しますか？\n関連する保存データ（解析行）もあわせて削除されます。"
        : `選択した ${imageIds.length} 件の画像を削除しますか？\n関連する保存データ（解析行）もあわせて削除されます。`;
    setPendingConfirm({
      title: "画像を削除",
      message,
      onConfirm: () => deleteImagesMutation.mutate(imageIds),
    });
  };

  const handleDeleteRows = (rowIds: string[]) => {
    if (!rowIds.length) return;
    const message =
      rowIds.length === 1
        ? "この保存データを削除しますか？"
        : `選択した ${rowIds.length} 件の保存データを削除しますか？`;
    setPendingConfirm({
      title: "保存データを削除",
      message,
      onConfirm: () => deleteRowsMutation.mutate(rowIds),
    });
  };

  const periodOptions = useMemo(() => {
    const keys = new Set<string>();
    summaryQuery.data?.items.forEach((item) => keys.add(item.period_key));
    rowsQuery.data?.items.forEach((row) => {
      if (row.period_key) keys.add(row.period_key);
    });
    return Array.from(keys).sort().reverse();
  }, [summaryQuery.data, rowsQuery.data]);

  const tabSummaryItems = useMemo(() => {
    if (!summaryQuery.data?.items.length) return [];
    return summaryQuery.data.items.filter((item) => item.source_type === sourceType);
  }, [sourceType, summaryQuery.data]);

  if (rowsQuery.error instanceof ApiError && rowsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  const toggleRowSelection = (rowId: string) => {
    setSelectedRowIds((current) =>
      current.includes(rowId) ? current.filter((id) => id !== rowId) : [...current, rowId],
    );
  };

  const toggleImageSelection = (imageId: string) => {
    setSelectedImageIds((current) =>
      current.includes(imageId) ? current.filter((id) => id !== imageId) : [...current, imageId],
    );
  };

  const toggleAllImageSelection = () => {
    const visibleIds = new Set(uploadedImages.map((image) => image.id));
    if (allVisibleImagesSelected) {
      setSelectedImageIds((current) => current.filter((id) => !visibleIds.has(id)));
      return;
    }
    setSelectedImageIds((current) => [...new Set([...current, ...visibleIds])]);
  };

  const toggleAllRowSelection = () => {
    const visibleIds = new Set(deletableRows.map((row) => row.id));
    if (allSavedRowsSelected) {
      setSelectedRowIds((current) => current.filter((id) => !visibleIds.has(id)));
      return;
    }
    setSelectedRowIds((current) => [...new Set([...current, ...visibleIds])]);
  };

  const toggleAllConfirmableRowSelection = () => {
    const visibleIds = new Set(confirmableRows.map((row) => row.id));
    if (allConfirmableRowsSelected) {
      setSelectedRowIds((current) => current.filter((id) => !visibleIds.has(id)));
      return;
    }
    setSelectedRowIds((current) => [...new Set([...current, ...visibleIds])]);
  };

  const handleImageViewModeChange = (mode: ImageViewMode) => {
    setImageViewMode(mode);
    window.localStorage.setItem(IMAGE_VIEW_MODE_KEY, mode);
  };

  const handleImagePageSizeChange = (size: ImagePageSize) => {
    setImagePageSize(size);
    setImagePage(0);
    setSelectedImageIds([]);
    writeStoredPageSize(IMAGE_PAGE_SIZE_KEY, size);
  };

  const handleRowSort = (sortKey: OcrRowSortKey) => {
    setRowSortDirection((currentDirection) => nextSortDirection(rowSortKey, sortKey, currentDirection));
    setRowSortKey(sortKey);
  };

  const handleSavedRowPageSizeChange = (size: SavedRowPageSize) => {
    setSavedRowPageSize(size);
    setSavedRowPage(0);
    setSelectedRowIds([]);
    writeStoredPageSize(SAVED_ROW_PAGE_SIZE_KEY, size);
  };

  const handleSavedRowFilterChange = (patch: Partial<SavedRowFilters>) => {
    setSavedRowFilters((current) => ({ ...current, ...patch }));
    setSavedRowPage(0);
    setSelectedRowIds([]);
  };

  const renderSortableHeader = (sortKey: OcrRowSortKey, label: string) => (
    <OcrSortableHeader
      label={label}
      active={rowSortKey === sortKey}
      direction={rowSortDirection}
      onClick={() => handleRowSort(sortKey)}
    />
  );

  const rowColumns = [
    {
      key: "select",
      header: "選択",
      render: (row: OcrExtractedRowItem) => (
        <input
          type="checkbox"
          checked={selectedRowIds.includes(row.id)}
          disabled={!isOcrRowDeletable(row)}
          onChange={() => toggleRowSelection(row.id)}
          aria-label={`行 ${row.id} を選択`}
        />
      ),
    },
    {
      key: "quality",
      header: "確認",
      render: (row: OcrExtractedRowItem) => <OcrRowQualityBadges row={row} />,
    },
    {
      key: "source_image_filename",
      header: renderSortableHeader("source_image_filename", "画像ファイル"),
      render: (row: OcrExtractedRowItem) => {
        const name = row.source_image_filename;
        if (!name) return "-";
        return (
          <OcrFilenamePreviewLink
            imageId={row.source_image_id}
            filename={name}
            hideExtension
            clampLines={sourceType === "paygate_settlement"}
            onClickPreview={() => setReviewingRow(row)}
          />
        );
      },
    },
    {
      key: "record_date",
      header: renderSortableHeader("record_date", "日付"),
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell
          row={row}
          confidenceKey="record_datetime"
          value={row.record_date || "-"}
        />
      ),
    },
    {
      key: "record_time",
      header: "時刻",
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell
          row={row}
          confidenceKey="record_datetime"
          value={row.record_time || "-"}
        />
      ),
    },
    {
      key: "settlement_date",
      header: renderSortableHeader("record_date", "精算日"),
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell row={row} confidenceKey="record_datetime" value={row.record_date || "-"} />
      ),
    },
    {
      key: "settlement_time",
      header: "精算時間",
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell row={row} confidenceKey="record_datetime" value={row.record_time || "-"} />
      ),
    },
    {
      key: "amount",
      header: renderSortableHeader("amount", sourceType === "paygate_screenshot" ? "金額" : "合計"),
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell
          row={row}
          confidenceKey="amount"
          value={
            sourceType === "paygate_screenshot"
              ? formatYenAmountPlain(row.amount) || "-"
              : formatCurrency(row.amount)
          }
        />
      ),
    },
    {
      key: "subtotal",
      header: "小計",
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell row={row} confidenceKey="subtotal" value={formatCurrency(row.subtotal)} />
      ),
    },
    {
      key: "cash_sales",
      header: "現金売上",
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell row={row} confidenceKey="cash_sales" value={formatCurrency(row.cash_sales)} />
      ),
    },
    {
      key: "pos_sales",
      header: "PAYGATE POS",
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell row={row} confidenceKey="pos_sales" value={formatCurrency(row.pos_sales)} />
      ),
    },
    {
      key: "transaction_no",
      header: renderSortableHeader("transaction_no", "取引番号"),
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell row={row} confidenceKey="transaction_no" value={row.transaction_no || "-"} />
      ),
    },
    {
      key: "receipt_no",
      header: renderSortableHeader("receipt_no", "レシート番号"),
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell row={row} confidenceKey="receipt_no" value={row.receipt_no || "-"} />
      ),
    },
    {
      key: "transaction_count",
      header: "通常取引数",
      render: (row: OcrExtractedRowItem) => (
        <OcrRowConfidenceCell
          row={row}
          confidenceKey="transaction_count"
          value={row.transaction_count != null ? String(row.transaction_count) : "-"}
        />
      ),
    },
    {
      key: "terminal_id",
      header: "端末番号",
      render: (row: OcrExtractedRowItem) => (
        <SettlementTerminalIdDisplay
          row={row}
          confidence={row.field_confidence?.terminal_id}
          source={row.field_sources?.terminal_id}
        />
      ),
    },
    {
      key: "terminal_short_id",
      header: "端末識別番号",
      render: (row: OcrExtractedRowItem) =>
        row.source_type === "paygate_settlement" ? (
          <OcrRowConfidenceCell
            row={row}
            confidenceKey="terminal_short_id"
            value={row.terminal_short_id || "-"}
          />
        ) : (
          "-"
        ),
    },
    {
      key: "work_date",
      header: "稼働日",
      render: (row: OcrExtractedRowItem) => (row.source_type === "paygate_settlement" ? row.work_date || "-" : "-"),
    },
    {
      key: "unit_breakdown",
      header: "現金/POS台数",
      render: (row: OcrExtractedRowItem) => {
        if (row.source_type !== "paygate_settlement") return "-";
        if (row.cash_unit_count == null && row.pos_unit_count == null) {
          return row.unit_breakdown_status ? `未確定（${formatUnitBreakdownStatus(row.unit_breakdown_status)}）` : "-";
        }
        return `現金${row.cash_unit_count ?? "?"} / POS${row.pos_unit_count ?? "?"}`;
      },
    },
    {
      key: "reconciliation_eligible",
      header: "在庫照合対象",
      render: (row: OcrExtractedRowItem) => {
        if (row.source_type !== "paygate_settlement") return "-";
        if (row.voided_at) return <span className="ocr-muted-text">無効化済み</span>;
        return (
          <button
            type="button"
            className="ghost-button"
            disabled={setEligibilityMutation.isPending}
            onClick={() => handleToggleReconciliationEligibility(row)}
            title={row.excluded_reason || undefined}
          >
            {row.reconciliation_eligible ? "対象" : "対象外（クリックで復帰）"}
          </button>
        );
      },
    },
    {
      key: "status",
      header: "状態",
      render: (row: OcrExtractedRowItem) => <StatusBadge value={row.status} />,
    },
    {
      key: "validation_errors",
      header: "検証",
      render: (row: OcrExtractedRowItem) => {
        if (row.source_type === "paygate_settlement") {
          const messages = [...(row.blocking_errors || []), ...(row.warnings || [])];
          return messages.length ? (
            <span className="ocr-warning-text">{formatOcrValidationMessages(messages)}</span>
          ) : (
            "OK"
          );
        }
        return row.validation_errors?.length ? (
          <span className="ocr-warning-text">{formatOcrValidationMessages(row.validation_errors)}</span>
        ) : (
          "OK"
        );
      },
    },
    {
      key: "edit",
      header: "操作",
      render: (row: OcrExtractedRowItem) => (
        <div className="ocr-row-actions">
          <button type="button" className="ghost-button" onClick={() => setReviewingRow(row)}>
            確認
          </button>
          {row.status !== "confirmed" ? (
            <OcrParseProgressHover
              progress={
                reparseRowMutation.isPending && reparseRowMutation.variables === row.id ? reparseProgress : null
              }
              active={reparseRowMutation.isPending && reparseRowMutation.variables === row.id}
            >
              <button
                type="button"
                className="ghost-button"
                disabled={reparseRowMutation.isPending && reparseRowMutation.variables === row.id}
                onClick={() => reparseRowMutation.mutate(row.id)}
              >
                {reparseRowMutation.isPending && reparseRowMutation.variables === row.id ? "解析中..." : "再解析"}
              </button>
            </OcrParseProgressHover>
          ) : null}
          {row.source_type === "paygate_settlement" && row.status === "confirmed" && !row.voided_at ? (
            <button
              type="button"
              className="ghost-button"
              disabled={voidRowMutation.isPending}
              onClick={() => handleVoidRow(row)}
            >
              無効化
            </button>
          ) : null}
          <button
            type="button"
            className="ghost-button ocr-inline-delete"
            disabled={deleteRowsMutation.isPending}
            onClick={() => handleDeleteRows([row.id])}
          >
            削除
          </button>
        </div>
      ),
    },
  ];

  const PAYGATE_SCREENSHOT_ONLY_COLUMN_KEYS = new Set([
    "transaction_no",
    "receipt_no",
    "record_date",
    "record_time",
  ]);
  const PAYGATE_SCREENSHOT_HIDDEN_COLUMN_KEYS = new Set([
    "transaction_count",
    "work_date",
    "unit_breakdown",
    "reconciliation_eligible",
  ]);
  const PAYGATE_SCREENSHOT_COLUMN_ORDER = [
    "select",
    "quality",
    "source_image_filename",
    "record_date",
    "record_time",
    "transaction_no",
    "receipt_no",
    "amount",
    "status",
    "validation_errors",
    "edit",
  ];
  const SETTLEMENT_ONLY_COLUMN_KEYS = new Set([
    "terminal_short_id",
    "terminal_id",
    "settlement_date",
    "settlement_time",
    "subtotal",
    "cash_sales",
    "pos_sales",
  ]);
  const SETTLEMENT_HIDDEN_COLUMN_KEYS = new Set([
    "work_date",
    "unit_breakdown",
    "reconciliation_eligible",
    "status",
  ]);
  const SETTLEMENT_COLUMN_ORDER = [
    "select",
    "quality",
    "source_image_filename",
    "terminal_short_id",
    "settlement_date",
    "settlement_time",
    "terminal_id",
    "subtotal",
    "amount",
    "cash_sales",
    "pos_sales",
    "transaction_count",
    "validation_errors",
    "edit",
  ];
  const visibleRowColumns = rowColumns
    .filter((column) => {
      if (sourceType === "paygate_screenshot") {
        return (
          !SETTLEMENT_ONLY_COLUMN_KEYS.has(column.key) &&
          !PAYGATE_SCREENSHOT_HIDDEN_COLUMN_KEYS.has(column.key)
        );
      }
      return (
        !PAYGATE_SCREENSHOT_ONLY_COLUMN_KEYS.has(column.key) &&
        !SETTLEMENT_HIDDEN_COLUMN_KEYS.has(column.key)
      );
    })
    .sort((left, right) => {
      const orderSource =
        sourceType === "paygate_settlement"
          ? SETTLEMENT_COLUMN_ORDER
          : sourceType === "paygate_screenshot"
            ? PAYGATE_SCREENSHOT_COLUMN_ORDER
            : null;
      if (!orderSource) {
        return 0;
      }
      const order = new Map(orderSource.map((key, index) => [key, index]));
      return (order.get(left.key) ?? 999) - (order.get(right.key) ?? 999);
    });

  const pendingFilesForPage = useMemo(
    () => pendingFiles.filter((file) => file.sourceType === sourceType),
    [pendingFiles, sourceType],
  );

  const isPaygate = sourceType === "paygate_screenshot";
  const isSettlement = sourceType === "paygate_settlement";
  const pageTitle = isPaygate ? "Paygateスクリーンショット" : "精算レシート";
  const pageDescription = isPaygate
    ? "Paygate画面のスクリーンショットをアップロード・解析し、取引データを保存します。"
    : "感熱紙の精算レシートをアップロード・解析し、端末別の精算データを保存します。";

  return (
    <div className="page-stack">
      <PageHeader eyebrow="OCR" title={pageTitle} description={pageDescription} />

      <section className="panel-card ocr-upload-grid">
        <DropZone
          label={isPaygate ? "Paygateスクリーンショット" : "精算レシート"}
          description={
            isPaygate ? "取引履歴の画面キャプチャを追加" : "感熱紙の精算レシート写真を追加"
          }
          sourceType={sourceType}
          files={pendingFilesForPage}
          onAddFiles={addFiles}
          onRemove={removeFile}
        />
      </section>

      <section className="panel-card">
        <div className="upload-actions">
          <button
            type="button"
            className="secondary-button"
            disabled={!pendingFilesForPage.length || uploadMutation.isPending}
            onClick={() => uploadMutation.mutate()}
          >
            {uploadMutation.isPending ? "アップロード中..." : "画像をアップロード"}
          </button>
        </div>
        {formError ? <p className="form-error">{formError}</p> : null}
      </section>

      <section className="panel-card page-stack">
        <div className="ocr-section-header">
          <PageHeader
            eyebrow="履歴"
            title="アップロード済み画像"
            description={
              imagesSectionCollapsed
                ? `全 ${totalImages} 件（折りたたみ中）`
                : "サーバーに保存された画像のサムネイル・状態を表示します。"
            }
          />
          <button
            type="button"
            className="ghost-button ocr-section-toggle"
            onClick={() => setImagesSectionCollapsed((current) => !current)}
            aria-expanded={!imagesSectionCollapsed}
          >
            {imagesSectionCollapsed ? "展開" : "折りたたむ"}
          </button>
        </div>
        {!imagesSectionCollapsed ? (
          <>
            <div className="ocr-image-toolbar filter-row">
              <label>
                表示形式
                <select
                  value={imageViewMode}
                  onChange={(event) => handleImageViewModeChange(event.target.value as ImageViewMode)}
                >
                  <option value="thumbnail">サムネイル</option>
                  <option value="compact">一覧（名前・日時）</option>
                </select>
              </label>
              <label>
                表示件数
                <select
                  value={imagePageSize}
                  onChange={(event) => handleImagePageSizeChange(Number(event.target.value) as ImagePageSize)}
                >
                  {IMAGE_PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>
                      {size}件
                    </option>
                  ))}
                </select>
              </label>
              <span className="ocr-image-toolbar-summary">
                全 {totalImages} 件中 {uploadedImages.length ? imagePage * imagePageSize + 1 : 0}–
                {imagePage * imagePageSize + uploadedImages.length} 件を表示
              </span>
            </div>
            <div className="upload-actions ocr-parse-actions">
              <OcrParseProgressHover progress={parseProgress} active={isParsing} className="ocr-parse-actions-hover">
                <button
                  type="button"
                  className="primary-button"
                  disabled={!imageIdsToParse.length || isParsing}
                  onClick={() => void handleParseImages()}
                >
                  {isParsing && parseProgress
                    ? `解析中 (${parseProgress.processedImages}/${parseProgress.totalImages})`
                    : `解析 (${imageIdsToParse.length}枚)`}
                </button>
              </OcrParseProgressHover>
              {isParsing && parseProgress ? (
                <span className="ocr-parse-actions-hint" title="ボタンまたは進捗表示にマウスオーバーで詳細">
                  {parseProgress.phase === "retrying"
                    ? `再試行 ${parseProgress.retryImageIndex}/${parseProgress.retryImageTotal}`
                    : `バッチ ${parseProgress.currentBatch}/${parseProgress.totalBatches} · 成功 ${parseProgress.successCount} / 失敗 ${parseProgress.failedCount}`}
                </span>
              ) : null}
              <button
                type="button"
                className="secondary-button"
                disabled={!uploadedImages.length}
                onClick={toggleAllImageSelection}
              >
                {allVisibleImagesSelected ? "選択解除" : "すべて選択"}
              </button>
              <button
                type="button"
                className="ghost-button"
                disabled={!selectedImageIds.length || deleteImagesMutation.isPending}
                onClick={() => handleDeleteImages(selectedImageIds)}
              >
                {deleteImagesMutation.isPending ? "削除中..." : `選択を削除 (${selectedImageIds.length})`}
              </button>
            </div>
            {parseResultSummary && !isParsing ? (
              <p className="upload-help">
                解析完了: 成功 {parseResultSummary.successCount} / 失敗 {parseResultSummary.failedCount}
                {parseResultSummary.timedOut ? "（時間上限で中断）" : ""}
              </p>
            ) : null}
            {imagesQuery.isLoading ? (
              <LoadingOverlay label="画像一覧を読み込み中..." />
            ) : imagesQuery.isError ? (
              <ErrorState title="画像一覧の取得に失敗しました" description="API 接続または権限を確認してください。" />
            ) : uploadedImages.length ? (
              <>
                <ul className={imageViewMode === "thumbnail" ? "ocr-image-grid" : "ocr-image-list"}>
                  {uploadedImages.map((image) => (
                    <OcrUploadedImageItem
                      key={image.id}
                      image={image}
                      viewMode={imageViewMode}
                      selected={selectedImageIds.includes(image.id)}
                      onToggle={() => toggleImageSelection(image.id)}
                      onRename={async (imageId, filename) => {
                        await renameImageMutation.mutateAsync({ imageId, filename });
                      }}
                      onDelete={(imageId) => handleDeleteImages([imageId])}
                      onReparse={(imageId) => reparseImageMutation.mutate(imageId)}
                      isRenaming={renameImageMutation.isPending}
                      isDeleting={deleteImagesMutation.isPending}
                      isReparsing={
                        reparseImageMutation.isPending && reparseImageMutation.variables === image.id
                      }
                    />
                  ))}
                </ul>
                {totalImagePages > 1 ? (
                  <div className="ocr-image-pagination">
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={imagePage === 0}
                      onClick={() => setImagePage((current) => Math.max(0, current - 1))}
                    >
                      前へ
                    </button>
                    <span>
                      {imagePage + 1} / {totalImagePages} ページ
                    </span>
                    <button
                      type="button"
                      className="secondary-button"
                      disabled={imagePage >= totalImagePages - 1}
                      onClick={() => setImagePage((current) => Math.min(totalImagePages - 1, current + 1))}
                    >
                      次へ
                    </button>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="ocr-empty-hint">まだアップロードされた画像がありません</p>
            )}
          </>
        ) : null}
      </section>

      <section className="panel-card page-stack">
        <PageHeader
          eyebrow="年月別"
          title="保存データ"
          description={`${pageTitle}の解析結果を年月別に表示します（${tabSavedRows.length}件）。`}
        />
        <div className="filter-row">
          <label>
            対象月
            <select
              value={selectedPeriodKey}
              onChange={(event) => {
                setSelectedPeriodKey(event.target.value);
                setSavedRowPage(0);
                setSelectedRowIds([]);
              }}
            >
              <option value="">すべて</option>
              {periodOptions.map((periodKey) => (
                <option key={periodKey} value={periodKey}>
                  {formatPeriodKey(periodKey)}
                </option>
              ))}
            </select>
          </label>
          {isSettlement ? (
            <label>
              端末識別番号
              <input
                value={savedRowFilters.terminalShortId}
                placeholder="例: 2c0e"
                maxLength={4}
                onChange={(event) =>
                  handleSavedRowFilterChange({
                    terminalShortId: normalizeTerminalShortIdInput(event.target.value),
                  })
                }
              />
            </label>
          ) : null}
          <label>
            ステータス
            <select
              value={savedRowFilters.status}
              onChange={(event) => handleSavedRowFilterChange({ status: event.target.value })}
            >
              <option value="">すべて</option>
              <option value="pending_review">未確定</option>
              <option value="confirmed">確定済み</option>
            </select>
          </label>
          <label>
            検証
            <select
              value={savedRowFilters.validation}
              onChange={(event) =>
                handleSavedRowFilterChange({ validation: event.target.value as SavedRowValidationFilter })
              }
            >
              <option value="">すべて</option>
              <option value="ok">OKのみ</option>
              <option value="error">要確認・エラー</option>
            </select>
          </label>
          <label>
            キーワード
            <input
              value={savedRowFilters.keyword}
              placeholder="ファイル名・端末番号など"
              onChange={(event) => handleSavedRowFilterChange({ keyword: event.target.value })}
            />
          </label>
          <label>
            表示件数
            <select
              value={savedRowPageSize}
              onChange={(event) => handleSavedRowPageSizeChange(Number(event.target.value) as SavedRowPageSize)}
            >
              {SAVED_ROW_PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}件
                </option>
              ))}
            </select>
          </label>
          <label>
            並び替え
            <select
              value={rowSortKey}
              onChange={(event) => {
                const nextKey = event.target.value as OcrRowSortKey;
                setRowSortKey(nextKey);
                setRowSortDirection("asc");
              }}
            >
              {OCR_ROW_SORTABLE_COLUMNS.map((column) => (
                <option key={column.key} value={column.key}>
                  {column.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="secondary-button"
            onClick={() => setRowSortDirection((current) => (current === "asc" ? "desc" : "asc"))}
          >
            {rowSortDirection === "asc" ? "昇順 ▲" : "降順 ▼"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={!selectedPeriodKey}
            onClick={() => selectedPeriodKey && downloadOcrCsv(selectedPeriodKey)}
          >
            月次CSV
          </button>
          <button type="button" className="secondary-button" onClick={() => downloadAllOcrCsv()}>
            全件CSV
          </button>
          {isSettlement ? (
            <button
              type="button"
              className="secondary-button"
              onClick={() => downloadSettlementCsv(selectedPeriodKey || undefined)}
            >
              精算レシートCSV（拡張）
            </button>
          ) : null}
          <button
            type="button"
            className="secondary-button"
            disabled={!deletableRows.length}
            onClick={toggleAllRowSelection}
          >
            {allSavedRowsSelected ? "選択解除" : "すべて選択"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={!confirmableRows.length}
            onClick={toggleAllConfirmableRowSelection}
          >
            {allConfirmableRowsSelected ? "確定候補の選択解除" : "確定可能な行をすべて選択"}
          </button>
          <button
            type="button"
            className="ghost-button"
            disabled={!selectedRowIds.length || deleteRowsMutation.isPending}
            onClick={() => handleDeleteRows(selectedRowIds)}
          >
            {deleteRowsMutation.isPending ? "削除中..." : `選択を削除 (${selectedRowIds.length})`}
          </button>
          <button
            type="button"
            className="primary-button"
            disabled={!selectedRowIds.length || confirmMutation.isPending}
            onClick={() => {
              const rowIds = selectedRowIds.filter((rowId) => {
                const row = savedRows.find((item) => item.id === rowId);
                return row ? isOcrRowConfirmable(row) : false;
              });
              if (!rowIds.length) {
                setFormError("確定できる行が選択されていません。要確認行は編集するか、削除してください。");
                return;
              }
              if (rowIds.length !== selectedRowIds.length) {
                setFormError(`確定対象 ${rowIds.length} 件のみ確定します（要確認行 ${selectedRowIds.length - rowIds.length} 件は除外）。`);
              }
              confirmMutation.mutate(rowIds);
            }}
          >
            選択行を確定
          </button>
        </div>

        {tabSummaryItems.length ? (
          <div className="upload-result-grid">
            {tabSummaryItems.map((item) => (
              <div key={`${item.period_key}-${item.source_type}`}>
                <span className="upload-result-label">{formatPeriodKey(item.period_key)}</span>
                <strong>
                  {item.row_count}件 / {formatCurrency(item.total_amount)}
                </strong>
              </div>
            ))}
          </div>
        ) : null}

        <p className="ocr-image-toolbar-summary">
          {filteredSavedRows.length
            ? `全 ${filteredSavedRows.length} 件中 ${savedRowPage * savedRowPageSize + 1}–${Math.min(
                (savedRowPage + 1) * savedRowPageSize,
                filteredSavedRows.length,
              )} 件を表示`
            : "該当する保存データはありません"}
          {filteredSavedRows.length !== tabSavedRows.length
            ? `（タブ内 ${tabSavedRows.length} 件から絞り込み）`
            : null}
        </p>

        <div id="ocr-saved-data-panel">
          {rowsQuery.isPending ? (
            <LoadingOverlay label="解析結果を読み込み中..." />
          ) : rowsQuery.isError ? (
            <ErrorState title="解析結果の取得に失敗しました" description="API 接続または権限を確認してください。" />
          ) : (
            <>
              <div className="ocr-saved-data-confidence-legend">
                <OcrFieldConfidenceLegend />
              </div>
              <DataTable
                columns={visibleRowColumns}
                rows={paginatedSavedRows}
                getRowKey={(row) => row.id}
                emptyTitle={
                  isPaygate ? "Paygateの保存データがありません" : "精算レシートの保存データがありません"
                }
                emptyDescription={
                  filteredSavedRows.length !== tabSavedRows.length
                    ? "絞り込み条件を変更するか、フィルタをクリアしてください。"
                    : isPaygate
                      ? "Paygateスクリーンショットをアップロードして解析を実行してください。"
                      : "精算レシートをアップロードして解析を実行してください。"
                }
              />
              {totalSavedRowPages > 1 ? (
                <div className="ocr-image-pagination">
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={savedRowPage === 0}
                    onClick={() => setSavedRowPage((current) => Math.max(0, current - 1))}
                  >
                    前へ
                  </button>
                  <span>
                    {savedRowPage + 1} / {totalSavedRowPages} ページ
                  </span>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={savedRowPage >= totalSavedRowPages - 1}
                    onClick={() => setSavedRowPage((current) => Math.min(totalSavedRowPages - 1, current + 1))}
                  >
                    次へ
                  </button>
                </div>
              ) : null}
            </>
          )}
        </div>
      </section>

      {reviewingRowLive ? (
        <OcrSavedRowReviewModal
          row={reviewingRowLive}
          imageSiblingRows={reviewingRowSiblings}
          onClose={() => setReviewingRow(null)}
          onSaved={invalidateSavedRowQueries}
          onConfirm={async () => {
            await confirmOcrRows([reviewingRowLive.id]);
            setReviewingRow(null);
            setFormError(null);
            await invalidateSavedRowQueries();
          }}
          confirming={confirmMutation.isPending}
          onReparse={
            reviewingRowLive.status !== "confirmed" ? () => reparseRowMutation.mutate(reviewingRowLive.id) : undefined
          }
          reparsing={reparseRowMutation.isPending && reparseRowMutation.variables === reviewingRowLive.id}
          reparseProgress={
            reparseRowMutation.isPending && reparseRowMutation.variables === reviewingRowLive.id
              ? reparseProgress
              : null
          }
        />
      ) : null}

      {editingRow ? (
        <OcrRowEditModal
          row={editingRow}
          onClose={() => setEditingRow(null)}
          onSaved={async () => {
            await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
          }}
        />
      ) : null}

      {isSettlement ? (
      <>
      <section className="panel-card page-stack">
        <PageHeader
          eyebrow="精算レシート"
          title="実在庫入力"
          description="端末識別番号×稼働日ごとの開始/終了在庫と、販売以外の増減（調整数）を記録します。調整数は在庫が減った場合は正、増えた場合は負の値です。"
        />
        <div className="filter-row">
          <label>
            支社/現場ID
            <input
              value={inventoryDraft.branch_id}
              onChange={(event) => setInventoryDraft((current) => ({ ...current, branch_id: event.target.value }))}
            />
          </label>
          <label>
            端末識別番号
            <input
              value={inventoryDraft.terminal_short_id}
              placeholder="f353"
              maxLength={4}
              inputMode="text"
              autoComplete="off"
              spellCheck={false}
              onChange={(event) =>
                setInventoryDraft((current) => ({
                  ...current,
                  terminal_short_id: normalizeTerminalShortIdInput(event.target.value),
                }))
              }
            />
          </label>
          <label>
            稼働日
            <input
              type="date"
              value={inventoryDraft.work_date}
              onChange={(event) => setInventoryDraft((current) => ({ ...current, work_date: event.target.value }))}
            />
          </label>
          <label>
            稼働者ID
            <input
              value={inventoryDraft.staff_id}
              onChange={(event) => setInventoryDraft((current) => ({ ...current, staff_id: event.target.value }))}
            />
          </label>
          <label>
            開始在庫
            <input
              type="number"
              value={inventoryDraft.opening_count}
              onChange={(event) =>
                setInventoryDraft((current) => ({ ...current, opening_count: event.target.value }))
              }
            />
          </label>
          <label>
            終了在庫
            <input
              type="number"
              value={inventoryDraft.closing_count}
              onChange={(event) =>
                setInventoryDraft((current) => ({ ...current, closing_count: event.target.value }))
              }
            />
          </label>
          <label>
            調整数（減少=正/増加=負）
            <input
              type="number"
              value={inventoryDraft.adjustment_count}
              onChange={(event) =>
                setInventoryDraft((current) => ({ ...current, adjustment_count: event.target.value }))
              }
            />
          </label>
          <label>
            調整理由
            <input
              value={inventoryDraft.adjustment_reason}
              placeholder="破損・紛失・移動など"
              onChange={(event) =>
                setInventoryDraft((current) => ({ ...current, adjustment_reason: event.target.value }))
              }
            />
          </label>
          <label>
            メモ
            <input
              value={inventoryDraft.note}
              onChange={(event) => setInventoryDraft((current) => ({ ...current, note: event.target.value }))}
            />
          </label>
          <button
            type="button"
            className="primary-button"
            disabled={
              createSnapshotMutation.isPending ||
              !inventoryDraft.terminal_short_id ||
              !inventoryDraft.work_date ||
              inventoryDraft.opening_count === "" ||
              inventoryDraft.closing_count === ""
            }
            onClick={() => createSnapshotMutation.mutate()}
          >
            {createSnapshotMutation.isPending ? "登録中..." : "実在庫記録を登録"}
          </button>
        </div>
        {inventoryFormError ? <p className="form-error">{inventoryFormError}</p> : null}
        {snapshotsQuery.isLoading ? (
          <LoadingOverlay label="実在庫記録を読み込み中..." />
        ) : (
          <DataTable
            columns={[
              { key: "branch_id", header: "支社", render: (s: InventorySnapshotItem) => s.branch_id },
              { key: "terminal_short_id", header: "端末識別番号", render: (s: InventorySnapshotItem) => s.terminal_short_id },
              { key: "work_date", header: "稼働日", render: (s: InventorySnapshotItem) => s.work_date },
              { key: "opening_count", header: "開始", render: (s: InventorySnapshotItem) => s.opening_count },
              { key: "closing_count", header: "終了", render: (s: InventorySnapshotItem) => s.closing_count },
              {
                key: "adjustment",
                header: "調整数/理由",
                render: (s: InventorySnapshotItem) =>
                  s.adjustment_count !== 0
                    ? `${s.adjustment_count} (${s.adjustment_reason || "理由未記載"})`
                    : "-",
              },
              {
                key: "inventory_decrease",
                header: "販売相当減数",
                render: (s: InventorySnapshotItem) => s.inventory_decrease,
              },
              {
                key: "actions",
                header: "操作",
                render: (s: InventorySnapshotItem) => (
                  <div className="ocr-row-actions">
                    <button type="button" className="ghost-button" onClick={() => setEditingSnapshot(s)}>
                      編集
                    </button>
                    <button
                      type="button"
                      className="ghost-button ocr-inline-delete"
                      disabled={deleteSnapshotMutation.isPending}
                      onClick={() => {
                        if (window.confirm("この実在庫記録を削除しますか？")) {
                          deleteSnapshotMutation.mutate(s.id);
                        }
                      }}
                    >
                      削除
                    </button>
                  </div>
                ),
              },
            ]}
            rows={snapshotsQuery.data?.items ?? []}
            getRowKey={(s: InventorySnapshotItem) => s.id}
            emptyTitle="実在庫記録がありません"
            emptyDescription="上のフォームから稼働日ごとの開始/終了在庫を登録してください。"
          />
        )}
      </section>

      {editingSnapshot ? (
        <div className="ocr-modal-backdrop" role="presentation" onClick={() => setEditingSnapshot(null)}>
          <div
            className="ocr-modal-card"
            role="dialog"
            aria-modal="true"
            onClick={(event) => event.stopPropagation()}
          >
            <h3>実在庫記録を編集（{editingSnapshot.terminal_short_id} / {editingSnapshot.work_date}）</h3>
            <InventorySnapshotEditForm
              snapshot={editingSnapshot}
              saving={updateSnapshotMutation.isPending}
              onCancel={() => setEditingSnapshot(null)}
              onSave={(body) => updateSnapshotMutation.mutate({ id: editingSnapshot.id, body })}
            />
          </div>
        </div>
      ) : null}

      <section className="panel-card page-stack">
        <PageHeader
          eyebrow="精算レシート"
          title="在庫照合実行・結果"
          description="OCR確定済み・在庫照合対象(reconciliation_eligible=true)の精算行と実在庫記録を、支社×端末識別番号×稼働日で突合します。"
        />
        <div className="filter-row">
          <label>
            対象月 (YYYYMM)
            <input
              value={reconcilePeriodKey}
              onChange={(event) => setReconcilePeriodKey(event.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="202606"
            />
          </label>
          <label>
            開始日
            <input type="date" value={reconcileDateFrom} onChange={(event) => setReconcileDateFrom(event.target.value)} />
          </label>
          <label>
            終了日
            <input type="date" value={reconcileDateTo} onChange={(event) => setReconcileDateTo(event.target.value)} />
          </label>
          <button
            type="button"
            className="primary-button"
            disabled={
              runReconciliationMutation.isPending ||
              (!reconcilePeriodKey && !reconcileDateFrom && !reconcileDateTo)
            }
            onClick={() => runReconciliationMutation.mutate()}
          >
            {runReconciliationMutation.isPending ? "照合中..." : "在庫照合を実行"}
          </button>
        </div>
        {reconciliationBatch ? (
          <>
            <div className="upload-result-grid">
              <div>
                <span className="upload-result-label">一致</span>
                <strong>{reconciliationBatch.matched_count}</strong>
              </div>
              <div>
                <span className="upload-result-label">調整済み一致</span>
                <strong>{reconciliationBatch.adjusted_matched_count}</strong>
              </div>
              <div>
                <span className="upload-result-label">差異あり</span>
                <strong>{reconciliationBatch.count_mismatch_count}</strong>
              </div>
              <div>
                <span className="upload-result-label">OCRのみ</span>
                <strong>{reconciliationBatch.sales_only_count}</strong>
              </div>
              <div>
                <span className="upload-result-label">在庫のみ</span>
                <strong>{reconciliationBatch.inventory_only_count}</strong>
              </div>
            </div>
            <DataTable
              columns={[
                { key: "terminal_short_id", header: "端末識別番号", render: (r: InventoryReconciliationResultItem) => r.terminal_short_id },
                { key: "work_date", header: "稼働日", render: (r: InventoryReconciliationResultItem) => r.work_date },
                {
                  key: "ocr_transaction_count",
                  header: "OCR取引数",
                  render: (r: InventoryReconciliationResultItem) => r.ocr_transaction_count ?? "-",
                },
                {
                  key: "inventory_decrease",
                  header: "在庫減数",
                  render: (r: InventoryReconciliationResultItem) => r.inventory_decrease ?? "-",
                },
                { key: "diff", header: "差異", render: (r: InventoryReconciliationResultItem) => r.diff ?? "-" },
                {
                  key: "match_status",
                  header: "ステータス",
                  render: (r: InventoryReconciliationResultItem) => formatMatchStatus(r.match_status),
                },
                {
                  key: "diff_reason_category",
                  header: "差異理由",
                  render: (r: InventoryReconciliationResultItem) => (
                    <select
                      value={r.diff_reason_category || ""}
                      disabled={updateResultMutation.isPending}
                      onChange={(event) =>
                        updateResultMutation.mutate({
                          id: r.id,
                          body: { diff_reason_category: event.target.value || null },
                        })
                      }
                    >
                      <option value="">未分類</option>
                      {Object.entries(DIFF_REASON_CATEGORY_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  ),
                },
              ]}
              rows={reconciliationBatch.results}
              getRowKey={(r: InventoryReconciliationResultItem) => r.id}
              emptyTitle="差異はありません"
              emptyDescription="対象期間に照合結果がありません。"
            />
          </>
        ) : null}
      </section>
      </>
      ) : null}

      {isPaygate ? (
      <>
      <section className="panel-card page-stack">
        <PageHeader
          eyebrow="突合"
          title="本部CSVとの照合"
          description="本部から送られてきたCSVと OCR 結果を突合します。列名はサンプルに合わせて調整してください。"
        />
        <div className="filter-row">
          <label className="upload-file-field">
            本部CSV
            <input type="file" accept=".csv,text/csv" onChange={(event) => setHqFile(event.target.files?.[0] ?? null)} />
          </label>
          <label>
            取引番号列
            <input value={hqTxnColumn} onChange={(event) => setHqTxnColumn(event.target.value)} />
          </label>
          <label>
            レシート番号列
            <input value={hqReceiptColumn} onChange={(event) => setHqReceiptColumn(event.target.value)} />
          </label>
          <label>
            日付列
            <input value={hqDateColumn} onChange={(event) => setHqDateColumn(event.target.value)} />
          </label>
          <label>
            金額列
            <input value={hqAmountColumn} onChange={(event) => setHqAmountColumn(event.target.value)} />
          </label>
          <button
            type="button"
            className="primary-button"
            disabled={!hqFile || reconcileMutation.isPending}
            onClick={() => reconcileMutation.mutate()}
          >
            {reconcileMutation.isPending ? "突合中..." : "突合実行"}
          </button>
        </div>
        {reconcileResult ? (
          <div className="upload-result-grid">
            <div>
              <span className="upload-result-label">一致</span>
              <strong>{reconcileResult.matched_count}</strong>
            </div>
            <div>
              <span className="upload-result-label">OCRのみ</span>
              <strong>{reconcileResult.unmatched_ocr_count}</strong>
            </div>
            <div>
              <span className="upload-result-label">本部のみ</span>
              <strong>{reconcileResult.unmatched_hq_count}</strong>
            </div>
            <div>
              <span className="upload-result-label">金額差異</span>
              <strong>{reconcileResult.amount_diff_count}</strong>
            </div>
          </div>
        ) : null}
      </section>

      <section className="panel-card page-stack">
        <PageHeader
          eyebrow="比較"
          title="自己申告データとの比較"
          description="将来の sales_reports 連携に向けた OCR 集計ビューです。"
        />
        <div className="filter-row">
          <label>
            対象月 (YYYYMM)
            <input
              value={comparePeriodKey}
              onChange={(event) => setComparePeriodKey(event.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="202605"
            />
          </label>
        </div>
        {compareQuery.data ? (
          <div className="upload-result-grid">
            <div>
              <span className="upload-result-label">OCR行数</span>
              <strong>{compareQuery.data.ocr_row_count}</strong>
            </div>
            <div>
              <span className="upload-result-label">OCR合計</span>
              <strong>{formatCurrency(compareQuery.data.ocr_total_amount)}</strong>
            </div>
            <div>
              <span className="upload-result-label">リンク済み</span>
              <strong>{compareQuery.data.linked_count}</strong>
            </div>
          </div>
        ) : null}
        {compareQuery.data?.message ? <p className="upload-help">{compareQuery.data.message}</p> : null}
      </section>
      </>
      ) : null}

      <AppNotification
        open={notification.open}
        tone={notification.tone}
        title={notification.title}
        message={notification.message}
        detail={notification.detail}
        confirmLabel={notification.confirmLabel}
        onClose={closeNotification}
      />
      <ConfirmDialog
        open={Boolean(pendingConfirm)}
        title={pendingConfirm?.title ?? ""}
        message={pendingConfirm?.message ?? ""}
        confirmLabel="削除"
        busy={deleteImagesMutation.isPending || deleteRowsMutation.isPending}
        onCancel={() => setPendingConfirm(null)}
        onConfirm={() => {
          const action = pendingConfirm?.onConfirm;
          setPendingConfirm(null);
          action?.();
        }}
      />
    </div>
  );
}

export function OcrPaygateScreenshotPage() {
  return <ReceiptOcrPage sourceType="paygate_screenshot" />;
}

export function OcrSettlementReceiptPage() {
  return <ReceiptOcrPage sourceType="paygate_settlement" />;
}
