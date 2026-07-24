export const PUBLIC_OCR_MAX_FILES_PER_UPLOAD = 5;

export function PublicOcrUploadLimitNote({
  className,
  variant = "public",
}: {
  className?: string;
  variant?: "public" | "admin-context";
}) {
  const message =
    variant === "admin-context"
      ? `外部共有URLから一度にアップロードできる画像は${PUBLIC_OCR_MAX_FILES_PER_UPLOAD}枚までです。`
      : `一度にアップロードできる画像は${PUBLIC_OCR_MAX_FILES_PER_UPLOAD}枚までです。`;

  const noteClassName = className ? `public-form-limit-note ${className}` : "public-form-limit-note";
  return <p className={noteClassName}>{message}</p>;
}
