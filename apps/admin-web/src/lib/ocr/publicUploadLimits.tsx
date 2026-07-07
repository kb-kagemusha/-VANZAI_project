export const PUBLIC_OCR_MAX_FILES_PER_UPLOAD = 5;

export function PublicOcrUploadLimitNote({ className }: { className?: string }) {
  return (
    <p className={className ?? "public-form-limit-note"}>
      一度にアップロードできる画像は{PUBLIC_OCR_MAX_FILES_PER_UPLOAD}枚までです。
    </p>
  );
}
