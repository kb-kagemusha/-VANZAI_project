/** 連続する日だけを期間にまとめ、離れた日は別の行にする。 */
export function participationDateLines(values: string[]): string {
  const days = [...new Set(values)].sort();
  const runs: string[][] = [];
  for (const day of days) {
    const previous = runs[runs.length - 1];
    if (previous && Date.parse(`${day}T00:00:00Z`) - Date.parse(`${previous[1]}T00:00:00Z`) === 86_400_000) previous[1] = day;
    else runs.push([day, day]);
  }
  const label = (day: string) => {
    const [, month, date] = day.split("-").map(Number);
    return `${month}月${date}日（${"日月火水木金土"[new Date(`${day}T00:00:00Z`).getUTCDay()]}）`;
  };
  return runs.map(([first, last]) => first === last ? label(first) : `${label(first)}〜${label(last)}`).join("\n");
}

export function participationPeriodLabel(period: { from: string; to: string } | null): string {
  if (!period) return "未設定";
  return period.from === period.to ? participationDateLines([period.from]) : `${participationDateLines([period.from])}〜${participationDateLines([period.to])}`;
}
