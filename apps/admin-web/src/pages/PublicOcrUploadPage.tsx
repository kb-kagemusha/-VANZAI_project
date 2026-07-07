import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { accessPublicOcrUpload, uploadPublicOcrImage, ApiError } from "../lib/api/client";

const SESSION_STORAGE_KEY = "vanzai.ocr_upload_session";

export function PublicOcrUploadPage() {
  const [searchParams] = useSearchParams();
  const initialToken = searchParams.get("token") ?? "";
  const [sessionToken, setSessionToken] = useState<string | null>(
    () => window.sessionStorage.getItem(SESSION_STORAGE_KEY),
  );
  const [accessData, setAccessData] = useState<Awaited<ReturnType<typeof accessPublicOcrUpload>> | null>(null);
  const [sourceType, setSourceType] = useState<"paygate_screenshot" | "paygate_settlement" | "">("paygate_screenshot");
  const [uploaderName, setUploaderName] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const accessMutation = useMutation({
    mutationFn: () => accessPublicOcrUpload(initialToken),
    onSuccess: (data) => {
      window.history.replaceState(null, "", "/public/ocr-upload");
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, data.session_token);
      setSessionToken(data.session_token);
      setAccessData(data);
      if (data.default_source_type === "paygate_screenshot" || data.default_source_type === "paygate_settlement") {
        setSourceType(data.default_source_type);
      } else {
        setSourceType("");
      }
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

  const canUpload = Boolean(uploaderName.trim() && sourceType);

  if (initialToken && accessMutation.isPending) {
    return (
      <main className="public-form-page">
        <p>リンクを確認しています...</p>
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

      <section className="panel-card page-stack">
        <label className="form-field">
          <span>お名前（必須）</span>
          <input
            value={uploaderName}
            onChange={(e) => setUploaderName(e.target.value)}
            placeholder="例: 田中"
            required
          />
        </label>

        <label className="form-field">
          <span>画像の種類</span>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value as typeof sourceType)}
            disabled={
              accessData?.default_source_type === "paygate_screenshot" ||
              accessData?.default_source_type === "paygate_settlement"
            }
          >
            {accessData?.default_source_type === "required" ? <option value="">選択してください</option> : null}
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

        {uploadMutation.isPending ? <p>アップロード中...</p> : null}
        {message ? <p className="form-success">{message}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
      </section>
    </main>
  );
}
