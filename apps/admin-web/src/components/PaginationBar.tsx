export function PaginationBar({
  page,
  total,
  limit,
  onPrevious,
  onNext,
}: {
  page: number;
  total: number;
  limit: number;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="pagination-bar">
      <span>
        {page + 1} / {totalPages} ページ
      </span>
      <div className="pagination-actions">
        <button type="button" className="ghost-button" onClick={onPrevious} disabled={page === 0}>
          前へ
        </button>
        <button type="button" className="ghost-button" onClick={onNext} disabled={(page + 1) * limit >= total}>
          次へ
        </button>
      </div>
    </div>
  );
}