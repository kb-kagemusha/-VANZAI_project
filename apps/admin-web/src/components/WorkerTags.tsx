import type { WorkerTagOption } from "../types/api";

export type { WorkerTagOption };

const EVENT_SIZE_CODES = new Set(["event_small_d", "event_medium_d", "event_large_d"]);

function nextWorkerTags(selected: string[], code: string, checked: boolean): string[] {
  if (checked) {
    return selected.filter((item) => item !== code);
  }
  const base = EVENT_SIZE_CODES.has(code)
    ? selected.filter((item) => !EVENT_SIZE_CODES.has(item))
    : selected;
  return [...base, code];
}

function WorkerTagOptionList({
  options,
  selected,
  onChange,
  className,
}: {
  options: WorkerTagOption[];
  selected: string[];
  onChange: (next: string[]) => void;
  className?: string;
}) {
  return (
    <div className={className ? `worker-tag-picker-options ${className}` : "worker-tag-picker-options"}>
      {options.map((option) => {
        const checked = selected.includes(option.code);
        return (
          <label key={option.code} className={checked ? "worker-tag-option is-checked" : "worker-tag-option"}>
            <input
              type="checkbox"
              checked={checked}
              onChange={() => onChange(nextWorkerTags(selected, option.code, checked))}
            />
            <span className="worker-tag-option-text">
              <span className="worker-tag-option-label">{option.label}</span>
              {option.description ? <span className="worker-tag-option-note">{option.description}</span> : null}
            </span>
          </label>
        );
      })}
    </div>
  );
}

export function WorkerTagPicker({
  options,
  selected,
  onChange,
}: {
  options: WorkerTagOption[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const otherOptions = options.filter((option) => !EVENT_SIZE_CODES.has(option.code));
  const eventOptions = options.filter((option) => EVENT_SIZE_CODES.has(option.code));

  return (
    <fieldset className="worker-tag-picker">
      <legend>タグ</legend>
      <div className="worker-tag-picker-rows">
        <WorkerTagOptionList options={otherOptions} selected={selected} onChange={onChange} />
        {eventOptions.length > 0 ? (
          <WorkerTagOptionList
            options={eventOptions}
            selected={selected}
            onChange={onChange}
            className="worker-tag-picker-options-event"
          />
        ) : null}
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
