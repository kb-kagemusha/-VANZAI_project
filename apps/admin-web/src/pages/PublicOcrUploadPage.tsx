import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { LoadingOverlay } from "../components/LoadingOverlay";
import { accessPublicOcrUpload, uploadPublicOcrImage, ApiError } from "../lib/api/client";
import type { OcrPublicUploadAccessResponse } from "../types/api";

const SESSION_STORAGE_KEY = "vanzai.ocr_upload_session";
const SESSION_META_STORAGE_KEY = "vanzai.ocr_upload_session_meta";

type SourceType = "paygate_screenshot" | "paygate_settlement" | "";

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

function resolveInitialSourceType(
  meta: Pick<OcrPublicUploadAccessResponse, "default_source_type" | "public_memo"> | null,
): SourceType {
  if (meta?.default_source_type === "paygate_screenshot" || meta?.default_source_type === "paygate_settlement") {
    return meta.default_source_type;
  }
  return "";
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
  const [sourceType, setSourceType] = useState<SourceType>(() => resolveInitialSourceType(storedMeta));
  const [uploaderName, setUploaderName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const resetSourceTypeForLink = (meta: Pick<OcrPublicUploadAccessResponse, "default_source_type" | "public_memo"> | null) => {
    setSourceType(resolveInitialSourceType(meta));
  };

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
      resetSourceTypeForLink({
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
      if (!sourceType) {
        throw new Error("画像種別を選択してください");
      }
      return uploadPublicOcrImage({
        sessionToken,
        sourceType,
        file,
        publicUploaderName: uploaderName.trim() || null,
      });
    },
    onSuccess: (result) => {
      setError(null);
      if (result.reused_existing) {
        setMessage("この画像は既に登録済みです。受付が完了しました。");
      } else {
        setMessage(result.message);
      }
      if (accessData?.default_source_type === "required") {
        setSourceType("");
      }
    },
    onError: (err) => {
      setMessage(null);
      setError(err instanceof ApiError ? err.message : "アップロードに失敗しました");
    },
  });

  useEffect(() => {
    if (initialToken && !sessionToken && !accessMutation.isPending && !accessData) {
      accessMutation.mutate();
    }
  }, [initialToken, sessionToken, accessMutation, accessData]);

  useEffect(() => {
    if (!initialToken && sessionToken && accessData) {
      resetSourceTypeForLink(accessData);
    }
  }, [initialToken, sessionToken, accessData]);

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
    if (!sourceType) {
      setMessage(null);
      setError("画像の種類を選択してください");
      return;
    }
    uploadMutation.mutate(file);
  };

  const sourceTypeLocked =
    accessData?.default_source_type === "paygate_screenshot" ||
    accessData?.default_source_type === "paygate_settlement";
  const canUpload = Boolean(uploaderName.trim() && sourceType);

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

      <section className={`panel-card page-stack public-ocr-upload-card${uploadMutation.isPending ? " is-uploading" : ""}`}>
        <label className="form-field">
          <span>お名前（必須）</span>
          <input
            value={uploaderName}
            onChange={(e) => setUploaderName(e.target.value)}
            placeholder="例: 田中"
            required
            disabled={uploadMutation.isPending}
          />
        </label>

        <label className="form-field">
          <span>画像の種類</span>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as SourceType)}
            disabled={sourceTypeLocked || uploadMutation.isPending}
          >
            {!sourceTypeLocked ? <option value="">選択してください</option> : null}
            <option value="paygate_screenshot">Paygateスクリーンショット</option>
            <option value="paygate_settlement">精算レシート</option>
          </select>
        </label>

        {sourceType === "paygate_screenshot" ? (
          <div className="public-form-note">
            <p>
              正しい画像の例: Paygateの取引履歴画面で、各行に「決済方法」（現金・QRコード・クレジット等）が表示されているスクリーンショット
            </p>
          </div>
        ) : null}

        <label className="form-field">
          <span>写真を選択</span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            disabled={uploadMutation.isPending || !canUpload}
            onChange={onFileChange}
          />
        </label>

        {message ? <p className="form-success">{message}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
      </section>

      {uploadMutation.isPending ? (
        <div className="public-ocr-upload-overlay" role="status" aria-live="assertive" aria-busy="true">
          <div className="public-ocr-upload-overlay-panel">
            <div className="loading-spinner public-ocr-upload-spinner" />
            <p className="public-ocr-upload-overlay-title">アップロード中</p>
            <p className="public-ocr-upload-overlay-note">通信が完了するまでこの画面を閉じないでください</p>
          </div>
        </div>
      ) : null}
    </main>
  );
}
