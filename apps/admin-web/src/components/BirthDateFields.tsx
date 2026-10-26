type BirthDateFieldsProps = {
  value: string;
  onChange: (value: string) => void;
  required: boolean;
  disabled: boolean;
  error?: string;
  today: string;
};

export function BirthDateFields({ value, onChange, required, disabled, error, today }: BirthDateFieldsProps) {
  const [year = "", month = "", day = ""] = value.split("-");
  const currentYear = Number(today.slice(0, 4));
  const firstYear = Math.max(currentYear, Number(year) || currentYear);
  const lastYear = Math.min(1900, Number(year) || 1900);
  const years = Array.from({ length: firstYear - lastYear + 1 }, (_, index) => String(firstYear - index));
  const daysInMonth = (y: string, m: string) => m ? new Date(Date.UTC(Number(y) || 2000, Number(m), 0)).getUTCDate() : 31;
  const change = (part: number, selected: string) => {
    const next = [year, month, day];
    next[part] = selected;
    // 年月の変更で存在しなくなった日は未選択へ戻し、別の日付に置き換えない。
    if (part !== 2 && Number(next[2]) > daysInMonth(next[0], next[1])) next[2] = "";
    onChange(next.some(Boolean) ? next.join("-") : "");
  };
  const choices = [years, Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0")), Array.from({ length: daysInMonth(year, month) }, (_, i) => String(i + 1).padStart(2, "0"))];
  const units = ["年", "月", "日"];
  return <div className="lr-birth-date" role="group" aria-label="生年月日">
    {choices.map((options, index) => <select
      key={index} id={index === 0 ? "lr-birth_date" : `lr-birth_date-${index}`}
      name={`birth_date_${["year", "month", "day"][index]}`} aria-label={`生年月日（${units[index]}）`}
      autoComplete={["bday-year", "bday-month", "bday-day"][index]}
      value={[year, month, day][index]} onChange={(event) => change(index, event.target.value)}
      required={required || Boolean(value)} disabled={disabled} aria-required={required || Boolean(value)}
      aria-invalid={Boolean(error)} aria-describedby={error ? "lr-error-birth_date" : undefined}
    >
      <option value="">{units[index]}</option>
      {options.map((option) => <option key={option} value={option}>{Number(option)}{units[index]}</option>)}
    </select>)}
  </div>;
}
