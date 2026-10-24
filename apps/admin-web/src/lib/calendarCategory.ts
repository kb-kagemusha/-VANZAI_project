/** 依頼書のカテゴリ順に固定。研修併用時は業務カテゴリを優先する。 */
export const CALENDAR_CATEGORIES = ["飲食店巡回", "パーキング/喫煙所系", "商業施設/たばこ屋", "フェス系", "調査系", "履行確認", "研修"];
export function categoryColor(categories: string[] = []): number {
  const main = categories.find((value) => value !== "研修") ?? categories[0];
  const index = CALENDAR_CATEGORIES.indexOf(main);
  return index < 0 ? 7 : index;
}
