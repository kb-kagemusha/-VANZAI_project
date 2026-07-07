import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { LoadingOverlay } from "../components/LoadingOverlay";
import { accessPublicOcrUpload, uploadPublicOcrImage, ApiError } from "../lib/api/client";
import type { OcrPublicUploadAccessResponse } from "../types/api";

const SESSION_STORAGE_KEY = "vanzai.ocr_upload_session";
const SESSION_META_STORAGE_KEY = "vanzai.ocr_upload_session_meta";
const UPLOADER_NAME_STORAGE_KEY = "vanzai.ocr_upload_uploader_name";

type OverlayState =
  | { kind: "uploading" }
  | { kind: "error"; message: string }
  | null;

function readStoredSessionMeta(): Pick<OcrPublicUploadAccessResponse, "default_source_type" | "public_memo"> | null {
  const raw = window.sessionStorage.getItem(SESSION_META_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as Pick<OcrPublicUploadAccessResponse, "default_source_type" | "public_memo">;
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

export function PublicOcrUploadPage() {
  const [searchParams] = useSearchParams();
  const initialToken = searchParams.get("token") ?? "";
  const storedMeta = readStoredSessionMeta();
  const [sessionToken, setSessionToken] = useState<string | null>(
    () => window.sessionStorage.getItem(SESSION_STORAGE_KEY),
  );
  const [accessData, setAccessData] = useState<Pick<OcrPublicUploadAccessResponse, "default_source_type" | "public_memo"> | null>(
    storedMeta,
  );
  const [uploaderName, setUploaderName] = useState(readStoredUploaderName);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [overlay, setOverlay] = useState<OverlayState>(null);

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
      });
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "リンクの確認に失敗しました");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => {
      if (!sessionToken) {
        throw new Error("セッションがありません");
      }
      return uploadPublicOcrImage({
        sessionToken,
        file,
        publicUploaderName: uploaderName.trim() || null,
      });
    },
    onMutate: () => {
      setOverlay({ kind: "uploading" });
      setMessage(null);
      setError(null);
    },
    onSuccess: (result) => {
      setOverlay(null);
      setError(null);
      if (result.reused_existing) {
        setMessage("この画像は既に登録済みです。受付が完了しました。");
      } else {
        setMessage(result.message);
      }
    },
    onError: (err) => {
      const message = err instanceof ApiError ? err.message : "アップロードに失敗しました";
      setOverlay({ kind: "error", message });
    },
  });

  useEffect(() => {
    if (initialToken && !sessionToken && !accessMutation.isPending && !accessData) {
      accessMutation.mutate();
    }
  }, [initialToken, sessionToken, accessMutation, accessData]);

  const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    if (!uploaderName.trim()) {
      setMessage(null);
      setError("お名前を入力してください");
      return;
    }
    uploadMutation.mutate(file);
  };

  const fixedTypeLabel = fixedSourceTypeLabel(accessData?.default_source_type);
  const autoDetect = accessData?.default_source_type === "required" || !fixedTypeLabel;
  const canUpload = Boolean(uploaderName.trim());

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
        <h1>OCR 画像アップロード</h1>
        <p className="form-error">有効なアップロードリンクからアクセスしてください。</p>
      </main>
    );
  }

  return (
    <main className="public-form-page">
      <h1>OCR 画像アップロード</h1>
      {accessData?.public_memo ? <p className="public-form-lead">{accessData.public_memo}</p> : null}

      <section className={`panel-card page-stack public-ocr-upload-card${overlay ? " is-uploading" : ""}`}>
        <label className="form-field">
          <span>お名前（必須）</span>
          <input
            value={uploaderName}
            onChange={(e) => setUploaderName(e.target.value)}
            placeholder="例: 田中"
            required
            disabled={Boolean(overlay)}
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
          <span>写真を選択</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            disabled={Boolean(overlay) || !canUpload}
            onChange={onFileChange}
          />
        </label>

        {message ? <p className="form-success">{message}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
      </section>

      {overlay ? (
        <div className="public-ocr-upload-overlay" role="alertdialog" aria-modal="true" aria-live="assertive">
          <div className={`public-ocr-upload-overlay-panel${overlay.kind === "error" ? " is-error" : ""}`}>
            {overlay.kind === "uploading" ? (
              <>
                <div className="loading-spinner public-ocr-upload-spinner" aria-hidden="true" />
                <p className="public-ocr-upload-overlay-title">アップロード中</p>
                <p className="public-ocr-upload-overlay-note">通信が完了するまでこの画面を閉じないでください</p>
              </>
            ) : (
              <>
                <p className="public-ocr-upload-overlay-title">アップロードできませんでした</p>
                <p className="public-ocr-upload-overlay-note public-ocr-upload-overlay-error">{overlay.message}</p>
                <button
                  type="button"
                  className="primary-button registration-action-button"
                  onClick={() => setOverlay(null)}
                >
                  閉じる
                </button>
              </>
            )}
          </div>
        </div>
      ) : null}
    </main>
  );
}
