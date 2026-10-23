import { useSearchParams } from "react-router-dom";
export function CalendarTestToggle() {
  const [params, setParams] = useSearchParams();
  const enabled = params.get("test") === "1";
  return <div className="calendar-test-toggle" role="group" aria-label="テスト依頼書の表示">
    {[false, true].map((value) => <button type="button" key={String(value)} aria-pressed={enabled === value}
      className={`btn btn-ghost btn-sm${enabled === value ? " is-active" : ""}`}
      onClick={() => setParams((current) => { const next = new URLSearchParams(current); if (value) next.set("test", "1"); else next.delete("test"); return next; })}>
      {value ? "テストも表示" : "正式のみ"}
    </button>)}
  </div>;
}
