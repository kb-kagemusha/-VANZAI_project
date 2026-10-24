export type ParseFailureNotification = {
  title: string;
  message: string;
  detail?: string;
};

export function buildParseFailureNotification(
  failureMessages: string[],
  summary: { successCount: number; failedCount: number },
  options?: { reparse?: boolean; reparseImage?: boolean },
): ParseFailureNotification {
  const reparse = options?.reparse ?? false;
  const defaultTitle = options?.reparseImage
    ? "画像の再解析に失敗しました"
    : reparse
      ? "再解析に失敗しました"
      : "一部の画像の解析に失敗しました";

  if (failureMessages.length === 1) {
    return {
      title: defaultTitle,
      message: failureMessages[0],
    };
  }

  if (failureMessages.length > 1) {
    return {
      title: defaultTitle,
      message: `解析完了: 成功 ${summary.successCount} 件 / 失敗 ${summary.failedCount} 件。`,
      detail: failureMessages.join("\n"),
    };
  }

  const fallback = reparse
    ? "再解析の結果、必要な項目を読み取れませんでした。画像一覧のエラー内容を確認してください。"
    : `解析完了: 成功 ${summary.successCount} 件 / 失敗 ${summary.failedCount} 件。失敗した画像のエラー内容を下の一覧で確認してください。`;

  return {
    title: defaultTitle,
    message: fallback,
  };
}
