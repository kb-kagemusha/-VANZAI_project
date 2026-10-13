/** イベントDは担当できる最大規模。小型の依頼には中型・大型も対応できる。 */
const EVENT_ROLES = ["event_small_d", "event_medium_d", "event_large_d"];

export function matchesWorkerRoles(tags: string[], selected: string[]): boolean {
  return selected.length === 0 || selected.some((role) => {
    const level = EVENT_ROLES.indexOf(role);
    return level < 0 ? tags.includes(role) : EVENT_ROLES.slice(level).some((code) => tags.includes(code));
  });
}
