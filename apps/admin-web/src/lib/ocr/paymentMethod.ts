const ALLOWED_PAYGATE_PAYMENT_METHODS = ["現金", "QRコード", "クレジット"] as const;

export type PaygatePaymentMethod = (typeof ALLOWED_PAYGATE_PAYMENT_METHODS)[number];

export function normalizePaygatePaymentMethod(value: string | null | undefined): PaygatePaymentMethod | null {
  if (!value) {
    return null;
  }
  const cleaned = value.trim().replace(/\u3000/g, " ");
  if ((ALLOWED_PAYGATE_PAYMENT_METHODS as readonly string[]).includes(cleaned)) {
    return cleaned as PaygatePaymentMethod;
  }
  const lowered = cleaned.toLowerCase();
  if (cleaned === "現金" || lowered === "現金") {
    return "現金";
  }
  if (/^qr\s*コード$/i.test(cleaned) || lowered === "qr" || lowered === "qrcode") {
    return "QRコード";
  }
  if (/^クレ[ジヂ]ット(?:カード)?$/.test(cleaned)) {
    return "クレジット";
  }
  return null;
}

export function formatPaygatePaymentMethodDisplay(value: string | null | undefined): string {
  return normalizePaygatePaymentMethod(value) ?? "ー";
}

export { ALLOWED_PAYGATE_PAYMENT_METHODS };
