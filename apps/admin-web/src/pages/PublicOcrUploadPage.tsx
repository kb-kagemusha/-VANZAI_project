import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { LoadingOverlay } from "../components/LoadingOverlay";
import { accessPublicOcrUpload, uploadPublicOcrImage, ApiError } from "../lib/api/client";
import { PUBLIC_OCR_MAX_FILES_PER_UPLOAD, PublicOcrUploadLimitNote } from "../lib/ocr/publicUploadLimits";
import type { OcrPublicUploadAccessResponse } from "../types/api";

const SESSION_STORAGE_KEY = "vanzai.ocr_upload_session";
const SESSION_META_STORAGE_KEY = "vanzai.ocr_upload_session_meta";
const UPLOADER_NAME_STORAGE_KEY = "vanzai.ocr_upload_uploader_name";

type UploadFileResult = {
  fileName: string;
  status: "success" | "failure";
  message: string;
};

type UploadSummary = {
  results: UploadFileResult[];
  successCount: number;
  failureCount: number;
};

type OverlayState = {
  kind: "uploading";
  current: number;
  total: number;
} | null;

function readStoredSessionMeta(): Pick<OcrPublicUploadAccessResponse, "default_source_type" | "public_memo" | "label"> | null {
  const raw = window.sessionStorage.getItem(SESSION_META_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Pick<OcrPublicUploadAccessResponse, "default_source_type" | "public_memo" | "label">;
  } catch {
    return null;
  }
}

function readStoredUploaderName(): string {
  return window.localStorage.getItem(UPLOADER_NAME_STORAGE_KEY) ?? "";
}

function persistSession(data: OcrPublicUploadAccessResponse) {
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, data.session_token);
  window.sessionStorage.setItem(
    SESSION_META_STORAGE_KEY,
    JSON.stringify({
      default_source_type: data.default_source_type,
      public_memo: data.public_memo,
      label: data.label,
    }),
  );
}

function fixedSourceTypeLabel(defaultSourceType: string | undefined): string | null {
  if (defaultSourceType === "paygate_screenshot") {
    return "Paygateスクリーンショット";
  }
  if (defaultSourceType === "paygate_settlement") {
    return "精算レシート";
  }
  return null;
}

function formatUploadError(error: unknown): string {
  return error instanceof ApiError ? error.message : "アップロードに失敗しました";
}

export function PublicOcrUploadPage() {
  const [searchParams] = useSearchParams();
  const initialToken = searchParams.get("token") ?? "";
  const storedMeta = readStoredSessionMeta();
  const [sessionToken, setSessionToken] = useState<string | null>(
    () => window.sessionStorage.getItem(SESSION_STORAGE_KEY),
  );
  const [accessData, setAccessData] = useState<Pick<OcrPublicUploadAccessResponse, "default_source_type" | "public_memo" | "label"> | null>(
    storedMeta,
  );
  const [uploaderName, setUploaderName] = useState(readStoredUploaderName);
  const [error, setError] = useState<string | null>(null);
  const [uploadSummary, setUploadSummary] = useState<UploadSummary | null>(null);
  const [overlay, setOverlay] = useState<OverlayState>(null);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    const trimmed = uploaderName.trim();
    if (trimmed) {
      window.localStorage.setItem(UPLOADER_NAME_STORAGE_KEY, trimmed);
    } else {
      window.localStorage.removeItem(UPLOADER_NAME_STORAGE_KEY);
    }
  }, [uploaderName]);

  const accessMutation = useMutation({
    mutationFn: () => accessPublicOcrUpload(initialToken),
    onSuccess: (data) => {
      window.history.replaceState(null, "", "/public/ocr-upload");
      persistSession(data);
      setSessionToken(data.session_token);
      setAccessData({
        default_source_type: data.default_source_type,
        public_memo: data.public_memo,
        label: data.label,
      });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "リンクの確認に失敗しました");
    },
  });

  useEffect(() => {
    if (initialToken && !sessionToken && !accessMutation.isPending && !accessData) {
      accessMutation.mutate();
    }
  }, [initialToken, sessionToken, accessMutation, accessData]);

  const uploadFiles = async (files: File[]) => {
    if (!sessionToken) {
      setError("セッションがありません。リンクから再度アクセスしてください。");
      return;
    }

    const normalizedName = uploaderName.trim();
    if (!normalizedName) {
      setUploadSummary(null);
      setError("お名前を入力してください");
      return;
    }

    if (files.length > PUBLIC_OCR_MAX_FILES_PER_UPLOAD) {
      setUploadSummary(null);
      setError(`一度にアップロードできる画像は${PUBLIC_OCR_MAX_FILES_PER_UPLOAD}枚までです。`);
      return;
    }

    setError(null);
    setUploadSummary(null);
    setIsUploading(true);

    const results: UploadFileResult[] = [];

    for (let index = 0; index < files.length; index += 1) {
      const file = files[index];
      setOverlay({ kind: "uploading", current: index + 1, total: files.length });

      try {
        const result = await uploadPublicOcrImage({
          sessionToken,
          file,
          publicUploaderName: normalizedName,
        });
        results.push({
          fileName: file.name,
          status: "success",
          message: result.reused_existing
            ? "この画像は既に登録済みです。受付が完了しました。"
            : result.message,
        });
      } catch (uploadError) {
        results.push({
          fileName: file.name,
          status: "failure",
          message: formatUploadError(uploadError),
        });
      }
    }

    const successCount = results.filter((result) => result.status === "success").length;
    const failureCount = results.length - successCount;
    setUploadSummary({ results, successCount, failureCount });
    setOverlay(null);
    setIsUploading(false);
  };

  const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) {
      return;
    }
    void uploadFiles(files);
  };

  const fixedTypeLabel = fixedSourceTypeLabel(accessData?.default_source_type);
  const autoDetect = accessData?.default_source_type === "required" || !fixedTypeLabel;
  const canUpload = Boolean(uploaderName.trim()) && !isUploading;
  const uploadBlocked = Boolean(overlay) || isUploading;

  if (initialToken && accessMutation.isPending) {
    return (
      <main className="public-form-page">
        <LoadingOverlay label="リンクを確認しています..." />
      </main>
    );
  }

  if (!sessionToken) {
    return (
      <main className="public-form-page">
        <h1>画像アップロード</h1>
        <p className="form-error">有効なアップロードリンクからアクセスしてください。</p>
      </main>
    );
  }

  return (
    <main className="public-form-page">
      <h1>画像アップロード</h1>
      {accessData?.label ? <p className="public-ocr-upload-label">{accessData.label}</p> : null}
      {accessData?.public_memo ? <p className="public-ocr-upload-memo">{accessData.public_memo}</p> : null}

      <section className={`panel-card page-stack public-ocr-upload-card${uploadBlocked ? " is-uploading" : ""}`}>
        <label className="form-field">
          <span>お名前（必須）</span>
          <input
            value={uploaderName}
            onChange={(e) => setUploaderName(e.target.value)}
            placeholder="例: 田中"
            required
            disabled={uploadBlocked}
          />
        </label>

        {fixedTypeLabel ? (
          <p className="public-form-note">
            このリンクの画像種別: <strong>{fixedTypeLabel}</strong>
          </p>
        ) : null}

        {autoDetect ? (
          <div className="public-form-note">
            <p>画像の種類は自動判別します。</p>
            <p>Paygateの画面キャプチャは、各行に「決済方法」（現金・QRコード・クレジット等）が表示されている必要があります。</p>
          </div>
        ) : null}

        <label className="form-field">
          <span>写真を選択（最大{PUBLIC_OCR_MAX_FILES_PER_UPLOAD}枚）</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            multiple
            disabled={!canUpload}
            onChange={onFileChange}
          />
        </label>

        {uploadSummary ? (
          <div className="public-ocr-upload-summary" aria-live="polite">
            <p className="public-ocr-upload-summary-headline">
              成功 {uploadSummary.successCount}/{uploadSummary.results.length}
              {uploadSummary.failureCount > 0 ? (
                <>
                  {" "}
                  失敗 {uploadSummary.failureCount}/{uploadSummary.results.length}
                </>
              ) : null}
            </p>
            {uploadSummary.failureCount > 0 ? (
              <ul className="public-ocr-upload-failure-list">
                {uploadSummary.results
                  .filter((result) => result.status === "failure")
                  .map((result) => (
                    <li key={result.fileName}>
                      <strong>{result.fileName}</strong>
                      <span>{result.message}</span>
                    </li>
                  ))}
              </ul>
            ) : null}
            {uploadSummary.successCount > 0 && uploadSummary.failureCount === 0 ? (
              <p className="form-success">すべての画像の受付が完了しました。内容は事務局で確認します。</p>
            ) : null}
            {uploadSummary.successCount > 0 && uploadSummary.failureCount > 0 ? (
              <p className="public-form-note">受付できた画像は事務局で確認します。失敗した画像は修正して再度アップロードしてください。</p>
            ) : null}
            {uploadSummary.successCount === 0 ? (
              <p className="form-error">すべての画像のアップロードに失敗しました。内容を確認して再度お試しください。</p>
            ) : null}
          </div>
        ) : null}

        {error ? <p className="form-error">{error}</p> : null}
      </section>

      <PublicOcrUploadLimitNote className="public-ocr-upload-limit-note-bottom" />

      {overlay ? (
        <div className="public-ocr-upload-overlay" role="alertdialog" aria-modal="true" aria-live="assertive">
          <div className="public-ocr-upload-overlay-panel">
            <div className="loading-spinner public-ocr-upload-spinner" aria-hidden="true" />
            <p className="public-ocr-upload-overlay-title">アップロード中</p>
            <p className="public-ocr-upload-overlay-note">
              {overlay.current}/{overlay.total} 枚目を送信中です
            </p>
            <p className="public-ocr-upload-overlay-note">通信が完了するまでこの画面を閉じないでください</p>
          </div>
        </div>
      ) : null}
    </main>
  );
}
