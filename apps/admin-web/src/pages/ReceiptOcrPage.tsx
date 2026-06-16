import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
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
  downloadAllOcrCsv,
  downloadOcrCsv,
  getOcrMonthlySummary,
  listOcrRows,
  parseOcrImages,
  runOcrReconciliation,
  uploadOcrImage,
} from "../lib/api/client";
import { formatDateTime } from "../lib/formatters";
import type { OcrExtractedRowItem, OcrSourceImageItem, OcrSourceType } from "../types/api";

type PendingUpload = {
  key: string;
  file: File;
  sourceType: OcrSourceType;
  previewUrl: string;
};

const SOURCE_LABELS: Record<OcrSourceType, string> = {
  paygate_screenshot: "Paygateスクリーンショット",
  paygate_settlement: "精算レシート",
};

function formatPeriodKey(periodKey: string) {
  if (periodKey.length !== 6) return periodKey;
  return `${periodKey.slice(0, 4)}年${periodKey.slice(4)}月`;
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
              <img src={item.previewUrl} alt={item.file.name} className="ocr-thumb" />
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

export function ReceiptOcrPage() {
  const queryClient = useQueryClient();
  const [pendingFiles, setPendingFiles] = useState<PendingUpload[]>([]);
  const [uploadedImages, setUploadedImages] = useState<OcrSourceImageItem[]>([]);
  const [selectedPeriodKey, setSelectedPeriodKey] = useState("");
  const [selectedRowIds, setSelectedRowIds] = useState<string[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [hqFile, setHqFile] = useState<File | null>(null);
  const [hqTxnColumn, setHqTxnColumn] = useState("取引番号");
  const [hqReceiptColumn, setHqReceiptColumn] = useState("レシート番号");
  const [hqDateColumn, setHqDateColumn] = useState("日時");
  const [hqAmountColumn, setHqAmountColumn] = useState("金額");
  const [reconcileResult, setReconcileResult] = useState<Awaited<ReturnType<typeof runOcrReconciliation>> | null>(null);
  const [comparePeriodKey, setComparePeriodKey] = useState("");

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
    onSuccess: (images) => {
      setUploadedImages((current) => [...current, ...images]);
      pendingFiles.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      setPendingFiles([]);
      setFormError(null);
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "画像アップロードに失敗しました");
    },
  });

  const parseMutation = useMutation({
    mutationFn: async (imageIds: string[]) => parseOcrImages(imageIds),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
      await queryClient.invalidateQueries({ queryKey: ["ocr-monthly-summary"] });
      setFormError(null);
    },
    onError: (error) => {
      setFormError(error instanceof ApiError ? error.message : "解析に失敗しました");
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (rowIds: string[]) => confirmOcrRows(rowIds),
    onSuccess: async () => {
      setSelectedRowIds([]);
      await queryClient.invalidateQueries({ queryKey: ["ocr-rows"] });
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

  const imageIdsToParse = useMemo(() => {
    const pendingIds = uploadedImages.filter((image) => image.parse_status === "pending").map((image) => image.id);
    return pendingIds;
  }, [uploadedImages]);

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

  const rowColumns = [
    {
      key: "select",
      header: "選択",
      render: (row: OcrExtractedRowItem) => (
        <input
          type="checkbox"
          checked={selectedRowIds.includes(row.id)}
          onChange={() => toggleRowSelection(row.id)}
          aria-label={`行 ${row.id} を選択`}
        />
      ),
    },
    { key: "source_type", header: "種別", render: (row: OcrExtractedRowItem) => SOURCE_LABELS[row.source_type] || row.source_type },
    {
      key: "record_date",
      header: "日付",
      render: (row: OcrExtractedRowItem) => `${row.record_date || "-"} ${row.record_time || ""}`.trim(),
    },
    { key: "amount", header: "金額", render: (row: OcrExtractedRowItem) => (row.amount ? `¥${row.amount}` : "-") },
    { key: "transaction_no", header: "取引番号", render: (row: OcrExtractedRowItem) => row.transaction_no || "-" },
    { key: "receipt_no", header: "レシート番号", render: (row: OcrExtractedRowItem) => row.receipt_no || "-" },
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
          <button
            type="button"
            className="primary-button"
            disabled={!imageIdsToParse.length || parseMutation.isPending}
            onClick={() => parseMutation.mutate(imageIdsToParse)}
          >
            {parseMutation.isPending ? "解析中..." : `解析 (${imageIdsToParse.length}枚)`}
          </button>
        </div>
        {formError ? <p className="form-error">{formError}</p> : null}
        {parseMutation.data ? (
          <p className="upload-help">
            解析完了: 成功 {parseMutation.data.success_count} / 失敗 {parseMutation.data.failed_count} / 抽出行{" "}
            {parseMutation.data.row_count}
          </p>
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
            className="primary-button"
            disabled={!selectedRowIds.length || confirmMutation.isPending}
            onClick={() => confirmMutation.mutate(selectedRowIds)}
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
                  {item.row_count}件 / ¥{item.total_amount}
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
            rows={rowsQuery.data?.items || []}
            getRowKey={(row) => row.id}
            emptyTitle="解析結果がありません"
            emptyDescription="画像をアップロードして解析を実行してください。"
          />
        )}
      </section>

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
              <strong>¥{compareQuery.data.ocr_total_amount}</strong>
            </div>
            <div>
              <span className="upload-result-label">リンク済み</span>
              <strong>{compareQuery.data.linked_count}</strong>
            </div>
          </div>
        ) : null}
        {compareQuery.data?.message ? <p className="upload-help">{compareQuery.data.message}</p> : null}
      </section>

      {uploadedImages.length ? (
        <section className="panel-card page-stack">
          <PageHeader
            eyebrow="履歴"
            title="アップロード済み画像"
            description="このセッションでアップロードした画像の状態です。"
          />
          <ul className="ocr-file-list">
            {uploadedImages.map((image) => (
              <li key={image.id}>
                <div>
                  <strong>{image.original_filename || image.id}</strong>
                  <p>
                    {SOURCE_LABELS[image.source_type as OcrSourceType] || image.source_type} / {image.parse_status} /{" "}
                    {formatDateTime(image.created_at)}
                  </p>
                  {image.error_message ? <p className="form-error">{image.error_message}</p> : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
