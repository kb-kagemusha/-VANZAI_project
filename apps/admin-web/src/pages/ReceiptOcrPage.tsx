import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Navigate } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import {
  ApiError,
  compareOcrSelfReport,
  confirmOcrRows,
  deleteOcrImages,
  deleteOcrRows,
  downloadAllOcrCsv,
  downloadOcrCsv,
  fetchOcrImageBlobUrl,
  getOcrMonthlySummary,
  listOcrImages,
  listOcrRows,
  parseOcrImages,
  renameOcrImage,
  runOcrReconciliation,
  updateOcrRow,
  uploadOcrImage,
} from "../lib/api/client";
import { formatCurrency, formatDateTime, formatYenAmountPlain } from "../lib/formatters";
import { getOcrRowDisplayLabels, isOcrRowConfirmable, isOcrRowDeletable } from "../lib/ocr/rowDisplay";
import {
  nextSortDirection,
  OCR_ROW_SORTABLE_COLUMNS,
  sortOcrRows,
  type OcrRowSortKey,
  type SortDirection,
} from "../lib/ocr/sortRows";
import type { OcrExtractedRowItem, OcrSourceImageItem, OcrSourceType } from "../types/api";

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
type ImageViewMode = "thumbnail" | "compact";

const IMAGE_VIEW_MODE_KEY = "vanzai.ocr.imageViewMode";

const OCR_PARSE_STATUS_LABELS: Record<string, string> = {
  pending: "解析待ち",
  completed: "完了",
  failed: "失敗",
};

function formatOcrParseStatus(value: string) {
  return OCR_PARSE_STATUS_LABELS[value] || value;
}

function confirmOcrDeletion(message: string) {
  return window.confirm(message);
}

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

type OcrRowEditDraft = {
  record_date: string;
  record_time: string;
  amount: string;
  transaction_no: string;
  receipt_no: string;
  payment_method: string;
};

function OcrRowEditModal({
  row,
  onClose,
  onSaved,
}: {
  row: OcrExtractedRowItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [draft, setDraft] = useState<OcrRowEditDraft>({
    record_date: row.record_date || "",
    record_time: row.record_time || "",
    amount: formatYenAmountPlain(row.amount),
    transaction_no: row.transaction_no || "",
    receipt_no: row.receipt_no || "",
    payment_method: row.payment_method || "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await updateOcrRow(row.id, {
        record_date: draft.record_date || null,
        record_time: draft.record_time || null,
        amount: draft.amount || null,
        transaction_no: draft.transaction_no || null,
        receipt_no: draft.receipt_no || null,
        payment_method: draft.payment_method || null,
      });
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
        <h3 id="ocr-row-edit-title">OCR行を編集</h3>
        <div className="ocr-edit-grid">
          <label>
            日付
            <input
              type="date"
              value={draft.record_date}
              onChange={(event) => setDraft((current) => ({ ...current, record_date: event.target.value }))}
            />
          </label>
          <label>
            時刻 (HH:MM:SS)
            <input
              type="text"
              value={draft.record_time}
              placeholder="20:52:59"
              onChange={(event) => setDraft((current) => ({ ...current, record_time: event.target.value }))}
            />
          </label>
          <label>
            金額
            <input
              type="text"
              value={draft.amount}
              onChange={(event) => setDraft((current) => ({ ...current, amount: event.target.value }))}
            />
          </label>
          <label>
            取引番号
            <input
              type="text"
              value={draft.transaction_no}
              onChange={(event) => setDraft((current) => ({ ...current, transaction_no: event.target.value }))}
            />
          </label>
          <label>
            レシート番号
            <input
              type="text"
              value={draft.receipt_no}
              onChange={(event) => setDraft((current) => ({ ...current, receipt_no: event.target.value }))}
            />
          </label>
          <label>
            決済方法
            <input
              type="text"
              value={draft.payment_method}
              onChange={(event) => setDraft((current) => ({ ...current, payment_method: event.target.value }))}
            />
          </label>
        </div>
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

function OcrImagePreview({
  alt,
  previewUrl,
  children,
  className,
}: {
  alt: string;
  previewUrl: string | null;
  children: ReactNode;
  className?: string;
}) {
  const anchorRef = useRef<HTMLButtonElement>(null);
  const [hovering, setHovering] = useState(false);
  const [pinned, setPinned] = useState(false);
  const showPreview = (hovering || pinned) && Boolean(previewUrl);
  const { style, updatePosition } = useOcrPreviewPosition(anchorRef, showPreview);

  const popover =
    showPreview && previewUrl ? (
      <span
        className="ocr-image-preview-popover ocr-image-preview-popover--portal"
        style={style}
        role="tooltip"
      >
        <img src={previewUrl} alt={alt} onLoad={updatePosition} />
      </span>
    ) : null;

  return (
    <span
      className={["ocr-image-preview-trigger", className].filter(Boolean).join(" ")}
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      <button
        ref={anchorRef}
        type="button"
        className="ocr-image-preview-button"
        aria-label={`${alt} の画像プレビュー`}
        aria-expanded={showPreview}
        onClick={(event) => {
          event.stopPropagation();
          setPinned((value) => !value);
        }}
      >
        {children}
      </button>
      {popover ? createPortal(popover, document.body) : null}
    </span>
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
}: {
  imageId: string;
  filename: string;
  hideExtension?: boolean;
}) {
  const displayName = hideExtension ? stripOcrFilenameExtension(filename) : filename;
  const { url } = useOcrImageBlobUrl(imageId);

  return (
    <OcrImagePreview previewUrl={url} alt={filename} className="ocr-image-preview-trigger--filename">
      <span className="ocr-filename-preview-link" title={displayName}>
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
  isRenaming,
  isDeleting,
}: {
  image: OcrSourceImageItem;
  viewMode: ImageViewMode;
  selected: boolean;
  onToggle: () => void;
  onRename: (imageId: string, filename: string) => Promise<void>;
  onDelete: (imageId: string) => void;
  isRenaming: boolean;
  isDeleting: boolean;
}) {
  const isDuplicate = Boolean(image.reused_existing || image.has_filename_duplicate);
  const fileName = image.original_filename || image.id;
  const sourceLabel = SOURCE_LABELS[image.source_type as OcrSourceType] || image.source_type;

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
        {image.error_message ? <p className="ocr-image-error">{image.error_message}</p> : null}
        <button
          type="button"
          className="ghost-button ocr-inline-delete"
          disabled={isDeleting}
          onClick={() => onDelete(image.id)}
        >
          削除
        </button>
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
        {image.error_message ? <p className="ocr-image-error">{image.error_message}</p> : null}
        <button
          type="button"
          className="ghost-button ocr-inline-delete"
          disabled={isDeleting}
          onClick={() => onDelete(image.id)}
        >
          削除
        </button>
      </div>
    </li>
  );
}

export function ReceiptOcrPage() {
  const queryClient = useQueryClient();
  const [pendingFiles, setPendingFiles] = useState<PendingUpload[]>([]);
  const [selectedImageIds, setSelectedImageIds] = useState<string[]>([]);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [selectedRowIds, setSelectedRowIds] = useState<string[]>([]);
  const [editingRow, setEditingRow] = useState<OcrExtractedRowItem | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
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
  const [imagePageSize, setImagePageSize] = useState<ImagePageSize>(20);
  const [imagePage, setImagePage] = useState(0);
  const [rowSortKey, setRowSortKey] = useState<OcrRowSortKey>("record_date");
  const [rowSortDirection, setRowSortDirection] = useState<SortDirection>("desc");

  const rowsQuery = useQuery({
    queryKey: ["ocr-rows", selectedPeriodKey],
    queryFn: () =>
      listOcrRows({
        period_key: selectedPeriodKey || undefined,
        limit: 500,
      }),
  });

  const summaryQuery = useQuery({
    queryKey: ["ocr-monthly-summary"],
    queryFn: getOcrMonthlySummary,
  });

  const imagesQuery = useQuery({
    queryKey: ["ocr-images", imagePageSize, imagePage],
    queryFn: () =>
      listOcrImages({
        limit: imagePageSize,
        offset: imagePage * imagePageSize,
      }),
  });

  const parseTargetsQuery = useQuery({
    queryKey: ["ocr-images-parse-targets"],
    queryFn: async () => {
      const [pending, failed] = await Promise.all([
        listOcrImages({ parse_status: "pending", limit: 500 }),
        listOcrImages({ parse_status: "failed", limit: 500 }),
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

  const uploadMutation = useMutation({
    mutationFn: async () => {
      const images: OcrSourceImageItem[] = [];
      for (const item of pendingFiles) {
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
      setFormError(error instanceof ApiError ? error.message : "画像アップロードに失敗しました");
    },
  });

  const parseMutation = useMutation({
    mutationFn: async (imageIds: string[]) => parseOcrImages(imageIds),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-monthly-summary"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-images"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-images-parse-targets"] });
      setSelectedImageIds([]);
      setFormError(
        result.failed_count > 0
          ? `解析完了: 成功 ${result.success_count} / 失敗 ${result.failed_count}。失敗した画像のエラー内容を下の一覧で確認してください。`
          : null,
      );
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "解析に失敗しました");
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
  const sortedSavedRows = useMemo(
    () => sortOcrRows(savedRows, rowSortKey, rowSortDirection),
    [savedRows, rowSortDirection, rowSortKey],
  );
  const confirmableRows = savedRows.filter((row) => isOcrRowConfirmable(row));
  const deletableRows = savedRows.filter((row) => isOcrRowDeletable(row));
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
    if (!confirmOcrDeletion(message)) return;
    deleteImagesMutation.mutate(imageIds);
  };

  const handleDeleteRows = (rowIds: string[]) => {
    if (!rowIds.length) return;
    const message =
      rowIds.length === 1
        ? "この保存データを削除しますか？"
        : `選択した ${rowIds.length} 件の保存データを削除しますか？`;
    if (!confirmOcrDeletion(message)) return;
    deleteRowsMutation.mutate(rowIds);
  };

  const periodOptions = useMemo(() => {
    const keys = new Set<string>();
    summaryQuery.data?.items.forEach((item) => keys.add(item.period_key));
    rowsQuery.data?.items.forEach((row) => {
      if (row.period_key) keys.add(row.period_key);
    });
    return Array.from(keys).sort().reverse();
  }, [summaryQuery.data, rowsQuery.data]);

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
  };

  const handleRowSort = (sortKey: OcrRowSortKey) => {
    setRowSortDirection((currentDirection) => nextSortDirection(rowSortKey, sortKey, currentDirection));
    setRowSortKey(sortKey);
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
    { key: "source_type", header: "種別", render: (row: OcrExtractedRowItem) => SOURCE_LABELS[row.source_type] || row.source_type },
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
          />
        );
      },
    },
    {
      key: "record_date",
      header: renderSortableHeader("record_date", "日付"),
      render: (row: OcrExtractedRowItem) => `${row.record_date || "-"} ${row.record_time || ""}`.trim(),
    },
    { key: "amount", header: renderSortableHeader("amount", "金額"), render: (row: OcrExtractedRowItem) => formatCurrency(row.amount) },
    {
      key: "transaction_no",
      header: renderSortableHeader("transaction_no", "取引番号"),
      render: (row: OcrExtractedRowItem) => row.transaction_no || "-",
    },
    {
      key: "receipt_no",
      header: renderSortableHeader("receipt_no", "レシート番号"),
      render: (row: OcrExtractedRowItem) => row.receipt_no || "-",
    },
    {
      key: "transaction_count",
      header: "取引数",
      render: (row: OcrExtractedRowItem) => (row.transaction_count != null ? String(row.transaction_count) : "-"),
    },
    { key: "terminal_id", header: "端末番号", render: (row: OcrExtractedRowItem) => row.terminal_id || "-" },
    {
      key: "status",
      header: "状態",
      render: (row: OcrExtractedRowItem) => <StatusBadge value={row.status} />,
    },
    {
      key: "validation_errors",
      header: "検証",
      render: (row: OcrExtractedRowItem) =>
        row.validation_errors?.length ? (
          <span className="ocr-warning-text">{row.validation_errors.join(" / ")}</span>
        ) : (
          "OK"
        ),
    },
    {
      key: "edit",
      header: "操作",
      render: (row: OcrExtractedRowItem) => (
        <div className="ocr-row-actions">
          <button type="button" className="ghost-button" onClick={() => setEditingRow(row)}>
            編集
          </button>
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

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="運用"
        title="OCR・レシート解析"
        description="Paygateスクリーンショットと精算レシートを解析し、年月別に保存・CSV出力します。"
      />

      <section className="panel-card ocr-upload-grid">
        <DropZone
          label="Paygateスクリーンショット"
          description="取引履歴の画面キャプチャを追加"
          sourceType="paygate_screenshot"
          files={pendingFiles}
          onAddFiles={addFiles}
          onRemove={removeFile}
        />
        <DropZone
          label="精算レシート"
          description="感熱紙の精算レシート写真を追加"
          sourceType="paygate_settlement"
          files={pendingFiles}
          onAddFiles={addFiles}
          onRemove={removeFile}
        />
      </section>

      <section className="panel-card">
        <div className="upload-actions">
          <button
            type="button"
            className="secondary-button"
            disabled={!pendingFiles.length || uploadMutation.isPending}
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
            <div className="upload-actions">
              <button
                type="button"
                className="primary-button"
                disabled={!imageIdsToParse.length || parseMutation.isPending}
                onClick={() => parseMutation.mutate(imageIdsToParse)}
              >
                {parseMutation.isPending ? "解析中..." : `解析 (${imageIdsToParse.length}枚)`}
              </button>
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
            {parseMutation.data ? (
              <p className="upload-help">
                解析完了: 成功 {parseMutation.data.success_count} / 失敗 {parseMutation.data.failed_count} / 抽出行{" "}
                {parseMutation.data.row_count}
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
                      isRenaming={renameImageMutation.isPending}
                      isDeleting={deleteImagesMutation.isPending}
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
          description="レシート日付から自動で YYYYMM に分類されます。"
        />
        <div className="filter-row">
          <label>
            対象月
            <select value={selectedPeriodKey} onChange={(event) => setSelectedPeriodKey(event.target.value)}>
              <option value="">すべて</option>
              {periodOptions.map((periodKey) => (
                <option key={periodKey} value={periodKey}>
                  {formatPeriodKey(periodKey)}
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

        {summaryQuery.data?.items.length ? (
          <div className="upload-result-grid">
            {summaryQuery.data.items.map((item) => (
              <div key={`${item.period_key}-${item.source_type}`}>
                <span className="upload-result-label">
                  {formatPeriodKey(item.period_key)} / {SOURCE_LABELS[item.source_type as OcrSourceType] || item.source_type}
                </span>
                <strong>
                  {item.row_count}件 / {formatCurrency(item.total_amount)}
                </strong>
              </div>
            ))}
          </div>
        ) : null}

        {rowsQuery.isLoading ? (
          <LoadingOverlay label="解析結果を読み込み中..." />
        ) : rowsQuery.isError ? (
          <ErrorState title="解析結果の取得に失敗しました" description="API 接続または権限を確認してください。" />
        ) : (
          <DataTable
            columns={rowColumns}
            rows={sortedSavedRows}
            getRowKey={(row) => row.id}
            emptyTitle="解析結果がありません"
            emptyDescription="画像をアップロードして解析を実行してください。"
          />
        )}
      </section>

      {editingRow ? (
        <OcrRowEditModal
          row={editingRow}
          onClose={() => setEditingRow(null)}
          onSaved={async () => {
            await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
          }}
        />
      ) : null}

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
    </div>
  );
}
