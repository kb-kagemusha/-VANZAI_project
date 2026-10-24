import { stationDrafts } from "../lib/additionalStations";
import "../styles/additionalStations.css";

export function AdditionalStationFields({ value, onChange, disabled = false, error }: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  error?: string;
}) {
  const rows = stationDrafts(value);
  return <div className="additional-stations" role="group" aria-label="追加の最寄り駅">
    <div className="additional-stations-heading"><strong>2駅目以降（任意）</strong><span>駅ごとに徒歩時間を登録できます</span></div>
    {rows.map((row, index) => <div className="additional-station-row" key={index}>
      <label>最寄り駅{index + 2}<input id={index === 0 ? "lr-additional_stations" : undefined} maxLength={100} value={row.nearest_station} disabled={disabled}
        onChange={(event) => onChange(JSON.stringify(rows.map((item, i) => i === index ? { ...item, nearest_station: event.target.value } : item)))} /></label>
      <label>徒歩時間（分・任意）<input inputMode="numeric" maxLength={3} value={row.station_walk_minutes} disabled={disabled} aria-label={`最寄り駅${index + 2}まで徒歩（分）`}
        onChange={(event) => onChange(JSON.stringify(rows.map((item, i) => i === index ? { ...item, station_walk_minutes: event.target.value } : item)))} /></label>
      <button type="button" className="station-remove" disabled={disabled} aria-label={`最寄り駅${index + 2}を削除`}
        onClick={() => onChange(JSON.stringify(rows.filter((_, i) => i !== index)))}>削除</button>
    </div>)}
    {error ? <p className="station-error" role="alert">{error}</p> : null}
    <button type="button" className="station-add" disabled={disabled} onClick={() => onChange(JSON.stringify([...rows, { nearest_station: "", station_walk_minutes: "" }]))}>＋ 最寄り駅を追加</button>
  </div>;
}
