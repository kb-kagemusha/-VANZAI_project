import { formatYenAmountPlain } from "../../lib/formatters";
import { normalizePaygatePaymentMethod, ALLOWED_PAYGATE_PAYMENT_METHODS } from "../../lib/ocr/paymentMethod";
import { normalizeTerminalShortIdInput } from "../../lib/ocr/terminalShortId";
import type { OcrExtractedRowItem } from "../../types/api";

export type OcrRowEditDraft = {
  record_date: string;
  record_time: string;
  amount: string;
  transaction_no: string;
  receipt_no: string;
  payment_method: string;
  terminal_id: string;
  terminal_short_id: string;
  subtotal: string;
  cash_sales: string;
  pos_sales: string;
  transaction_count: string;
};

export function createOcrRowEditDraft(row: OcrExtractedRowItem): OcrRowEditDraft {
  return {
    record_date: row.record_date || "",
    record_time: row.record_time || "",
    amount: formatYenAmountPlain(row.amount),
    transaction_no: row.transaction_no || "",
    receipt_no: row.receipt_no || "",
    payment_method: normalizePaygatePaymentMethod(row.payment_method) ?? "",
    terminal_id: row.terminal_id || "",
    terminal_short_id: row.terminal_short_id || "",
    subtotal: formatYenAmountPlain(row.subtotal),
    cash_sales: formatYenAmountPlain(row.cash_sales),
    pos_sales: formatYenAmountPlain(row.pos_sales),
    transaction_count: row.transaction_count != null ? String(row.transaction_count) : "",
  };
}

export function buildOcrRowUpdateBody(
  row: Pick<OcrExtractedRowItem, "source_type">,
  draft: OcrRowEditDraft,
): Record<string, unknown> {
  const isSettlement = row.source_type === "paygate_settlement";
  const body: Record<string, unknown> = {
    record_date: draft.record_date || null,
    record_time: draft.record_time || null,
    amount: draft.amount || null,
    transaction_no: draft.transaction_no || null,
    receipt_no: draft.receipt_no || null,
    payment_method: normalizePaygatePaymentMethod(draft.payment_method),
  };
  if (isSettlement) {
    body.terminal_id = draft.terminal_id || null;
    body.terminal_short_id = draft.terminal_short_id || null;
    body.subtotal = draft.subtotal || null;
    body.cash_sales = draft.cash_sales || null;
    body.pos_sales = draft.pos_sales || null;
    body.transaction_count = draft.transaction_count ? Number(draft.transaction_count) : null;
  }
  return body;
}

export function OcrRowEditForm({
  row,
  draft,
  onDraftChange,
}: {
  row: Pick<OcrExtractedRowItem, "source_type">;
  draft: OcrRowEditDraft;
  onDraftChange: (next: OcrRowEditDraft) => void;
}) {
  const isSettlement = row.source_type === "paygate_settlement";
  const setDraft = (patch: Partial<OcrRowEditDraft>) => onDraftChange({ ...draft, ...patch });

  return (
    <div className="ocr-edit-grid">
      <label>
        {isSettlement ? "精算日" : "日付"}
        <input
          type="date"
          value={draft.record_date}
          onChange={(event) => setDraft({ record_date: event.target.value })}
        />
      </label>
      <label>
        {isSettlement ? "精算時間 (HH:MM:SS)" : "時刻 (HH:MM:SS)"}
        <input
          type="text"
          value={draft.record_time}
          placeholder="20:52:59"
          onChange={(event) => setDraft({ record_time: event.target.value })}
        />
      </label>
      <label>
        {isSettlement ? "合計" : "金額（合計）"}
        <input type="text" value={draft.amount} onChange={(event) => setDraft({ amount: event.target.value })} />
      </label>
      {isSettlement ? (
        <>
          <label>
            端末識別番号
            <input
              type="text"
              value={draft.terminal_short_id}
              placeholder="f353"
              maxLength={4}
              inputMode="text"
              autoComplete="off"
              spellCheck={false}
              onChange={(event) =>
                setDraft({ terminal_short_id: normalizeTerminalShortIdInput(event.target.value) })
              }
            />
          </label>
          <label>
            端末番号
            <input
              type="text"
              value={draft.terminal_id}
              placeholder="UUID"
              onChange={(event) => setDraft({ terminal_id: event.target.value })}
            />
          </label>
          <label>
            小計
            <input type="text" value={draft.subtotal} onChange={(event) => setDraft({ subtotal: event.target.value })} />
          </label>
          <label>
            現金売上
            <input
              type="text"
              value={draft.cash_sales}
              onChange={(event) => setDraft({ cash_sales: event.target.value })}
            />
          </label>
          <label>
            PAYGATE POS
            <input type="text" value={draft.pos_sales} onChange={(event) => setDraft({ pos_sales: event.target.value })} />
          </label>
          <label>
            通常取引数
            <input
              type="text"
              value={draft.transaction_count}
              onChange={(event) => setDraft({ transaction_count: event.target.value })}
            />
          </label>
        </>
      ) : (
        <>
          <label>
            取引番号
            <input
              type="text"
              value={draft.transaction_no}
              onChange={(event) => setDraft({ transaction_no: event.target.value })}
            />
          </label>
          <label>
            レシート番号
            <input
              type="text"
              value={draft.receipt_no}
              onChange={(event) => setDraft({ receipt_no: event.target.value })}
            />
          </label>
          <label>
            決済方法
            <select
              value={draft.payment_method}
              onChange={(event) => setDraft({ payment_method: event.target.value })}
            >
              <option value="">ー</option>
              {ALLOWED_PAYGATE_PAYMENT_METHODS.map((method) => (
                <option key={method} value={method}>
                  {method}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
    </div>
  );
}
