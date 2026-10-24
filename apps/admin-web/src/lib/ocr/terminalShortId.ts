/** 端末識別番号: 必ず4桁の16進（0-9a-f） */
export const TERMINAL_SHORT_ID_PATTERN = /^[0-9a-f]{4}$/;

export function normalizeTerminalShortIdInput(value: string): string {
  return value.replace(/[^0-9a-fA-F]/g, "").slice(0, 4).toLowerCase();
}
