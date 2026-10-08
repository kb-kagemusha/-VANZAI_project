import type { WorkerTagOption } from "../types/api";

export type { WorkerTagOption };

export function WorkerTagPicker({
  options,
  selected,
  onChange,
}: {
  options: WorkerTagOption[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <fieldset className="worker-tag-picker">
      <legend>タグ</legend>
      <div className="worker-tag-picker-options">
        {options.map((option) => {
          const checked = selected.includes(option.code);
          return (
            <label key={option.code} className={checked ? "worker-tag-option is-checked" : "worker-tag-option"}>
              <input
                type="checkbox"
                checked={checked}
                onChange={() => {
                  onChange(
                    checked
                      ? selected.filter((code) => code !== option.code)
                      : [...selected, option.code],
                  );
                }}
              />
              <span className="worker-tag-option-text">
                <span className="worker-tag-option-label">{option.label}</span>
                {option.description ? <span className="worker-tag-option-note">{option.description}</span> : null}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function WorkerTagList({
  options,
  codes,
}: {
  options: WorkerTagOption[];
  codes: string[] | null | undefined;
}) {
  const labels = (codes ?? [])
    .map((code) => options.find((option) => option.code === code)?.label)
    .filter((label): label is string => Boolean(label));

  if (labels.length === 0) {
    return <span style={{ color: "#9ca3af" }}>—</span>;
  }

  return (
    <span className="worker-tag-list">
      {labels.map((label) => (
        <span key={label} className="status-badge neutral">
          {label}
        </span>
      ))}
    </span>
  );
}
