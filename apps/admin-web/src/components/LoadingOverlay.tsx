export function LoadingOverlay({ label = "読み込み中..." }: { label?: string }) {
  return (
    <div className="loading-overlay" role="status" aria-live="polite">
      <div className="loading-spinner" />
      <span>{label}</span>
    </div>
  );
}