export function formatOcrUploaderLabel(image: {
  public_uploader_name?: string | null;
  upload_origin?: string | null;
}): string {
  if (image.public_uploader_name?.trim()) {
    return image.public_uploader_name.trim();
  }
  if (image.upload_origin === "public_link") {
    return "外部";
  }
  return "管理者";
}

export function formatOcrRowUploaderLabel(sourceUploaderName: string | null | undefined): string {
  return sourceUploaderName?.trim() || "-";
}
