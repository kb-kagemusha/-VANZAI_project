import { useEffect, useState } from "react";

export const SEAL_KEY = "vanzai.preview.seal";

export const SEAL_COLOR_EVENT = "vanzai-seal-color";

export const SEAL_COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#8b5cf6", "#14b8a6", "#f43f5e"] as const;

export type SealColor = (typeof SEAL_COLORS)[number];

function isSealColor(value: string | null): value is SealColor {
  return SEAL_COLORS.includes(value as SealColor);
}

export function readSealColor(): SealColor {
  const stored = window.localStorage.getItem(SEAL_KEY);
  return isSealColor(stored) ? stored : SEAL_COLORS[0];
}

export function applySealAccent(color: string) {
  document.documentElement.style.setProperty("--vanzai-seal", color);
}

export function writeSealColor(color: string): SealColor {
  const next = isSealColor(color) ? color : SEAL_COLORS[0];
  window.localStorage.setItem(SEAL_KEY, next);
  applySealAccent(next);
  window.dispatchEvent(new CustomEvent(SEAL_COLOR_EVENT));
  return next;
}

export function useSealColor(): [SealColor, (color: string) => void] {
  const [color, setColor] = useState(readSealColor);

  useEffect(() => {
    const sync = () => setColor(readSealColor());
    window.addEventListener("storage", sync);
    window.addEventListener(SEAL_COLOR_EVENT, sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(SEAL_COLOR_EVENT, sync);
    };
  }, []);

  return [color, (next: string) => setColor(writeSealColor(next))];
}

if (typeof window !== "undefined") {
  applySealAccent(readSealColor());
  window.addEventListener("storage", (event) => {
    if (event.key === SEAL_KEY || event.key === null) {
      applySealAccent(readSealColor());
    }
  });
}
