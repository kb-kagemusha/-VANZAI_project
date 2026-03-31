import { formatStatus } from "../lib/formatters";

export function StatusBadge({ value }: { value: string }) {
  const tone = value.toLowerCase().includes("closed")
    ? "closed"
    : value.toLowerCase().includes("confirmed") || value.toLowerCase().includes("approved") || value.toLowerCase().includes("active")
      ? "positive"
      : value.toLowerCase().includes("review") || value.toLowerCase().includes("preparing")
        ? "attention"
        : "neutral";

  return <span className={`status-badge ${tone}`}>{formatStatus(value)}</span>;
}