import { ApiError } from "./api/client";
import { formatLocalizedErrorMessage } from "./ocr/validationMessages";

export type RequestErrorPresentation = {
  title: string;
  message: string;
  detail?: string;
};

const TIMEOUT_STATUSES = new Set([502, 503, 504, 408]);

function isNetworkFailure(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }
  if (error.name === "AbortError") {
    return true;
  }
  const message = error.message.toLowerCase();
  return (
    error instanceof TypeError ||
    message.includes("failed to fetch") ||
    message.includes("networkerror") ||
    message.includes("load failed")
  );
}

export function isRequestTimeoutError(error: unknown): boolean {
  if (error instanceof ApiError && TIMEOUT_STATUSES.has(error.status)) {
    return true;
  }
  return isNetworkFailure(error);
}

export function formatRequestError(error: unknown, fallback: string): RequestErrorPresentation {
  if (error instanceof ApiError) {
    if (TIMEOUT_STATUSES.has(error.status)) {
      return {
        title: "タイムアウト",
        message:
          "解析処理が時間内に完了しませんでした。画像枚数が多い場合は少しずつ解析するか、しばらく待ってから再度お試しください。",
        detail: error.message,
      };
    }
    return {
      title: "処理に失敗しました",
      message: formatLocalizedErrorMessage(error.message, fallback),
    };
  }

  if (isNetworkFailure(error)) {
    return {
      title: "通信エラー",
      message:
        "サーバーへの接続がタイムアウトしたか、通信に失敗しました。ネットワーク状態を確認し、画像枚数を減らして再度お試しください。",
      detail: error instanceof Error ? error.message : undefined,
    };
  }

  if (error instanceof Error && error.message) {
    return {
      title: "処理に失敗しました",
      message: formatLocalizedErrorMessage(error.message, fallback),
    };
  }

  return {
    title: "処理に失敗しました",
    message: fallback,
  };
}
