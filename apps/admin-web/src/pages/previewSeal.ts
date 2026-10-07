export const SEAL_KEY = "vanzai.preview.seal";

export const SEAL_COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#8b5cf6", "#14b8a6", "#f43f5e"] as const;

export function readSealColor(): string {
  const stored = window.localStorage.getItem(SEAL_KEY);
  return SEAL_COLORS.includes(stored as (typeof SEAL_COLORS)[number]) ? stored! : SEAL_COLORS[0];
}
