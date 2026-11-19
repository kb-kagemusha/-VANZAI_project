/**
 * ダブルヘッダー（同じ日の2件を1件の依頼としてまとめて送る。DEC-148）の「2件の要点」。
 * 1件目・2件目の案件・場所・時間・単価を横に並べて入力し、時間の重なり・移動時間を確かめる。
 * 詳しい項目（依頼元・内容・持ち物など）は「詳細を入力」で切り替えた下のふつうの入力欄で入れる。
 */
import { OrderDatePicker } from "./OrderDatePicker";
import { bundleCheck, bundlePayTotal, legSummary, patchLeg, type BundleLegState } from "../lib/orderBundle";
import { withFullwidthTilde } from "../lib/orderRequestFormat";

function yen(value: number): string {
  return value.toLocaleString("ja-JP", { maximumFractionDigits: 2 });
}

export function OrderBundlePanel({
  legs,
  active,
  onSelect,
  onChangeLeg,
  date,
  onDate,
  travelMinutes,
  onTravel,
  defaultMinutes,
  provisional,
  onEditDefault,
  documentNumbers,
  disabled,
}: {
  legs: [BundleLegState, BundleLegState];
  active: 0 | 1;
  onSelect: (index: 0 | 1) => void;
  onChangeLeg: (index: 0 | 1, next: BundleLegState) => void;
  date: string;
  onDate: (day: string) => void;
  travelMinutes: number;
  onTravel: (minutes: number) => void;
  defaultMinutes: number;
  provisional: boolean;
  onEditDefault: (() => void) | null;
  documentNumbers: [string | null, string | null];
  disabled: boolean;
}) {
  const check = bundleCheck(legs[0].sections, legs[1].sections, travelMinutes);
  const pay = bundlePayTotal(legs[0].sections, legs[1].sections);
  let status: { tone: "ok" | "warn" | "error" | "muted"; text: string };
  if (check.issues.length) status = { tone: "error", text: check.issues[0] };
  else if (!check.complete) status = { tone: "muted", text: "2件の時間を入れると、重なりと移動の間隔を確かめます。" };
  else if (check.overlap) status = { tone: "error", text: `時間が${-(check.gapMinutes ?? 0)}分重なっています。このままでは送付できません（保存はできます）。` };
  else if (check.short) status = { tone: "warn", text: `移動の間隔が${check.gapMinutes}分で、移動に必要な時間（${travelMinutes}分）より短いです。送付するときに確認と理由の入力が必要です。` };
  else status = { tone: "ok", text: `1件目の終了から2件目の開始まで${check.gapMinutes}分あります。` };

  return (
    <section className="order-draft-section order-bundle" aria-label="ダブルヘッダーの2件">
      <h4>ダブルヘッダー（同じ日の2件）</h4>
      <p className="order-field-hint">稼働者には1件の依頼として1通で届き、受諾も辞退も2件まとめて決まります。案件・請求・PDFは2件それぞれです。</p>
      <div className="order-bundle-shared">
        <div className="order-field">
          <span className="order-field-label">稼働日（2件共通）</span>
          <OrderDatePicker label="ダブルヘッダーの稼働日" value={date} disabled={disabled} onChange={onDate} />
        </div>
        <label className="order-field order-bundle-travel">
          <span className="order-field-label">移動に必要な時間</span>
          <span className="order-bundle-minutes">
            <input type="number" inputMode="numeric" min={0} max={720} step={5} value={travelMinutes} disabled={disabled}
              aria-label="移動に必要な時間（分）"
              onChange={(event) => onTravel(Math.max(0, Math.min(720, Number(event.target.value.replace(/[^0-9]/g, "")) || 0)))} />
            分
          </span>
          <span className="order-field-hint">
            初期値 {defaultMinutes}分{provisional ? "（仮の値）" : ""}
            {onEditDefault ? <button type="button" className="btn btn-ghost btn-sm order-bundle-default" onClick={onEditDefault}>初期値を変更</button> : null}
          </span>
        </label>
      </div>
      <div className="order-bundle-legs">
        {legs.map((leg, rawIndex) => {
          const index = rawIndex as 0 | 1;
          const summary = legSummary(leg.sections);
          const change = (next: BundleLegState) => onChangeLeg(index, next);
          const order = check.complete ? (check.earlier === index ? "早い方" : "遅い方") : "";
          return (
            <div key={index} className={`order-bundle-leg${active === index ? " is-active" : ""}`}>
              <div className="order-bundle-leg-head">
                <strong>{index + 1}件目</strong>
                {documentNumbers[index] ? <span className="order-bundle-number">{documentNumbers[index]}</span> : null}
                {order ? <span className="order-bundle-order">{order}</span> : null}
                <button type="button" className={`btn btn-sm ${active === index ? "btn-primary" : "btn-ghost"}`} onClick={() => onSelect(index)} aria-pressed={active === index}>
                  {active === index ? "下で入力中" : "詳細を入力"}
                </button>
              </div>
              <label className="order-field">
                <span className="order-field-label">案件名</span>
                <input value={leg.sections.projectName} disabled={disabled} placeholder="イベント名"
                  onChange={(event) => change({ ...leg, sections: { ...leg.sections, projectName: withFullwidthTilde(event.target.value) } })} />
              </label>
              <label className="order-field">
                <span className="order-field-label">稼働場所</span>
                <input value={leg.form.site_name} disabled={disabled} placeholder="会場名"
                  onChange={(event) => change({ form: { ...leg.form, site_id: null, site_name: withFullwidthTilde(event.target.value) }, sections: { ...leg.sections, placeId: "", mapsUrl: "" } })} />
              </label>
              <div className="order-bundle-times">
                <label className="order-field"><span className="order-field-label">開始（集合）</span>
                  <input type="time" value={summary.start} disabled={disabled} onChange={(event) => change({ ...leg, sections: patchLeg(leg.sections, { start: event.target.value }) })} />
                </label>
                <label className="order-field"><span className="order-field-label">終了</span>
                  <input type="time" value={summary.end} disabled={disabled} onChange={(event) => change({ ...leg, sections: patchLeg(leg.sections, { end: event.target.value }) })} />
                </label>
              </div>
              <label className="order-check">
                <input type="checkbox" checked={summary.endNextDay} disabled={disabled} onChange={(event) => change({ ...leg, sections: patchLeg(leg.sections, { endNextDay: event.target.checked }) })} />
                終了は翌日
              </label>
              <div className="order-bundle-rate">
                <label className="order-field"><span className="order-field-label">単価（税抜）</span>
                  <input inputMode="decimal" value={summary.amount} disabled={disabled} placeholder="例：10000"
                    onChange={(event) => change({ ...leg, sections: patchLeg(leg.sections, { amount: event.target.value.replace(/[^0-9.]/g, "").slice(0, 13) }) })} />
                </label>
                <div className="order-segment order-bundle-unit" role="group" aria-label={`${index + 1}件目の単価の種類`}>
                  <button type="button" className={summary.unit === "day" ? "is-active" : ""} disabled={disabled} onClick={() => change({ ...leg, sections: patchLeg(leg.sections, { unit: "day" }) })}>日給</button>
                  <button type="button" className={summary.unit === "hour" ? "is-active" : ""} disabled={disabled} onClick={() => change({ ...leg, sections: patchLeg(leg.sections, { unit: "hour" }) })}>時給</button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className={`order-bundle-status is-${status.tone}`} role={status.tone === "error" ? "alert" : undefined}>{status.text}</p>
      <p className="order-bundle-pay">
        報酬の合計（2件）：{pay.total !== null ? `¥${yen(pay.total)}（税抜）` : pay.hourly ? "時給の件があるため、実績で決まります" : "2件の単価を入れると出ます"}
      </p>
    </section>
  );
}
