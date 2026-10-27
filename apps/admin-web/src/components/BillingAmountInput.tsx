import { useId, useRef, useState } from "react";
import { billingAmountReading, groupedBillingAmount, isValidBillingAmount, normalizeBillingAmount } from "../lib/billingAmountFormat";

export function BillingAmountInput({ label, value, disabled, onChange }: {
  label: string; value: string; disabled: boolean; onChange: (value: string) => void;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const composing = useRef(false);
  const [compositionText, setCompositionText] = useState<string | null>(null);
  const invalid = value !== "" && !isValidBillingAmount(value);

  function commit(text: string, selection: number | null) {
    const logicalCaret = normalizeBillingAmount(text.slice(0, selection ?? text.length)).length;
    onChange(normalizeBillingAmount(text));
    requestAnimationFrame(() => {
      const element = input.current;
      if (!element || document.activeElement !== element) return;
      let position = 0, digits = 0;
      while (position < element.value.length && digits < logicalCaret) {
        if (element.value[position] !== ",") digits += 1;
        position += 1;
      }
      element.setSelectionRange(position, position);
    });
  }

  return <div className="order-field billing-amount-field">
    <label htmlFor={id}>{label}</label>
    <input ref={input} id={id} type="text" inputMode="decimal" autoComplete="off" spellCheck={false}
      value={compositionText ?? groupedBillingAmount(value)} disabled={disabled}
      aria-invalid={invalid || undefined} aria-describedby={`${id}-reading${invalid ? ` ${id}-error` : ""}`}
      onCompositionStart={(event) => { composing.current = true; setCompositionText(event.currentTarget.value); }}
      onCompositionEnd={(event) => { composing.current = false; setCompositionText(null); commit(event.currentTarget.value, event.currentTarget.selectionStart); }}
      onChange={(event) => {
        if (composing.current) setCompositionText(event.currentTarget.value);
        else commit(event.currentTarget.value, event.currentTarget.selectionStart);
      }} />
    <p id={`${id}-reading`} className="billing-amount-reading" aria-live="polite">{billingAmountReading(value) || "\u00a0"}</p>
    {invalid ? <p id={`${id}-error`} className="form-error">0以上の金額を小数点以下2桁までで入力してください（整数部は13桁まで）。</p> : null}
  </div>;
}
