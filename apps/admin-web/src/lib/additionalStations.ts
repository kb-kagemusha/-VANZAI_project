export type StationDraft = { nearest_station: string; station_walk_minutes: string };

export function stationDrafts(value: string): StationDraft[] {
  if (!value) return [];
  return JSON.parse(value).map((row: { nearest_station: string; station_walk_minutes: string | number | null }) => ({
    nearest_station: row.nearest_station,
    station_walk_minutes: row.station_walk_minutes == null ? "" : String(row.station_walk_minutes),
  }));
}

export function additionalStationsPayload(value: string): string {
  if (!value) return "";
  const rows = stationDrafts(value).filter((row) => row.nearest_station.trim() || row.station_walk_minutes.trim());
  return JSON.stringify(rows.map((row, index) => {
    const name = row.nearest_station.trim();
    const walk = row.station_walk_minutes.trim();
    if (!name || name.length > 100) throw new Error(`最寄り駅${index + 2}の駅名を100文字以内で入力してください。`);
    if (walk && (!/^[0-9]{1,3}$/.test(walk) || Number(walk) > 300)) throw new Error(`最寄り駅${index + 2}の徒歩時間は0〜300分の整数で入力してください。`);
    return { nearest_station: name, station_walk_minutes: walk ? Number(walk) : null };
  }));
}

export function showAdditionalStations(value: string): string {
  const rows = stationDrafts(value);
  return rows.map((row) => `${row.nearest_station}${row.station_walk_minutes ? `（徒歩${row.station_walk_minutes}分）` : ""}`).join("、") || "（なし）";
}
