import type { Dispatch, SetStateAction } from "react";

const SUBJECTS: Record<string, string> = {
  dashboard: "ダッシュボード", master: "マスタ", price: "単価", project: "案件", shift: "シフト枠",
  assignment: "配置", actual: "実績", availability: "出勤可能日", csv: "CSV", invoice: "請求",
  payout: "支払", soft_close: "仮締め", hard_close: "本締め", expense: "経費",
  incentive: "インセンティブ", audit_log: "監査ログ", notice: "スタッフ通知", ocr: "OCR・在庫照合",
  order: "発注依頼書", registration: "登録申請", wake_status: "起床状況",
  attendance_note: "遅刻・キャンセル記録",
};
const ACTIONS: Record<string, string> = { read: "閲覧", write: "編集", generate: "生成", issue: "発行", correct: "訂正",
  approve: "承認", submit: "提出", import: "取込", calculate: "計算", release: "解除", response: "回答", remind: "催促・要対応通知" };
const FULL_LABELS: Record<string, string> = { wake_alert_receive: "起床報告が無い場合の連絡受け取り" };
export function permissionLabel(value: string) {
  if (FULL_LABELS[value]) return FULL_LABELS[value];
  if (value === "soft_close" || value === "hard_close") return SUBJECTS[value];
  const index = value.lastIndexOf("_");
  return (SUBJECTS[value.slice(0, index)] ?? value.slice(0, index)) + "：" + (ACTIONS[value.slice(index + 1)] ?? value.slice(index + 1));
}

// 権限の分類（0.53.8、DEC-125）。ここに無い権限は「その他」に出す（新しい権限が増えても選べなくならないように）。
export const PERMISSION_GROUPS: { key: string; title: string; note: string; subjects: string[]; permissions?: string[] }[] = [
  { key: "today", title: "当日の運用", note: "起床の確認、遅刻・キャンセルの記録", subjects: ["wake_status", "attendance_note"], permissions: ["wake_alert_receive"] },
  { key: "orders", title: "案件・配置", note: "案件、発注依頼書、シフト枠、配置、出勤可能日", subjects: ["project", "order", "shift", "assignment", "availability"] },
  { key: "people", title: "稼働者・登録・通知", note: "マスタ、登録申請、スタッフ通知", subjects: ["master", "registration", "notice"] },
  { key: "actuals", title: "実績・取込", note: "実績、CSV、レシートOCR", subjects: ["actual", "csv", "ocr"] },
  { key: "money", title: "お金", note: "単価、請求、支払、経費、インセンティブ", subjects: ["price", "invoice", "payout", "expense", "incentive"] },
  { key: "closing", title: "締め", note: "仮締め・本締めと、その解除", subjects: [], permissions: ["soft_close", "soft_close_release", "hard_close", "hard_close_release"] },
  { key: "admin", title: "管理", note: "ダッシュボード、監査ログ", subjects: ["dashboard", "audit_log"] },
];

// 運営用LINEメニューで使う権限。無いとLINEのボタンを押しても「権限がありません」になる。
export const LINE_MENU_PERMISSIONS: Record<string, string> = {
  wake_status_read: "LINE：起床状況",
  order_read: "LINE：今日の案件・案件カレンダー・発注依頼書",
  availability_read: "LINE：出勤可否・配置",
  wake_alert_receive: "LINE：未報告の連絡",
};

function subjectOf(permission: string) {
  if (permission === "soft_close" || permission === "hard_close") return permission;
  return permission.slice(0, permission.lastIndexOf("_"));
}

export function groupPermissions(available: string[]) {
  const used = new Set<string>();
  const groups = PERMISSION_GROUPS.map(group => {
    const items = available.filter(permission => !used.has(permission) && (group.permissions?.includes(permission) || group.subjects.includes(subjectOf(permission))));
    items.forEach(item => used.add(item));
    return { ...group, items };
  });
  const rest = available.filter(permission => !used.has(permission));
  if (rest.length) groups.push({ key: "other", title: "その他", note: "分類に入っていない権限", subjects: [], items: rest });
  return groups.filter(group => group.items.length);
}

export function RolePermissionPicker({ available, selected, setSelected, disabled }: {
  available: string[]; selected: string[]; setSelected: Dispatch<SetStateAction<string[]>>; disabled: boolean;
}) {
  function readOf(permission: string) {
    return permission.slice(0, permission.lastIndexOf("_")) + "_read";
  }
  function toggle(permission: string, checked: boolean) {
    const read = readOf(permission);
    setSelected(current => {
      if (checked) return Array.from(new Set([...current, permission, ...(available.includes(read) ? [read] : [])]));
      if (permission.endsWith("_read")) return current.filter(item => !item.startsWith(permission.slice(0, -4)));
      return current.filter(item => item !== permission);
    });
  }
  function toggleGroup(items: string[], checked: boolean) {
    setSelected(current => {
      if (checked) {
        const reads = items.map(readOf).filter(read => available.includes(read));
        return Array.from(new Set([...current, ...items, ...reads]));
      }
      // 閲覧を外すと、同じ機能の編集・承認なども外れる（閲覧なしの操作は保存できないため）
      const removedReads = items.filter(item => item.endsWith("_read")).map(item => item.slice(0, -4));
      return current.filter(item => !items.includes(item) && !removedReads.some(prefix => item.startsWith(prefix)));
    });
  }
  const groups = groupPermissions(available);
  return <fieldset disabled={disabled} className="access-permission-groups"><legend>許可する機能</legend>
    <p className="access-permission-hint"><span className="access-line-badge">LINE</span> は運営用LINEメニューで使う権限です。外すと、その方のLINEのボタンを押しても見られません。</p>
    {groups.map(group => {
      const count = group.items.filter(item => selected.includes(item)).length;
      const all = count === group.items.length;
      return <section key={group.key} className="access-permission-group" aria-labelledby={`perm-group-${group.key}`}>
        <header>
          <div><h4 id={`perm-group-${group.key}`}>{group.title}</h4><small>{group.note}</small></div>
          <span className="access-permission-count">{count}／{group.items.length}</span>
          <button type="button" className="access-group-toggle" onClick={() => toggleGroup(group.items, !all)}>{all ? "まとめて外す" : "まとめて選択"}</button>
        </header>
        <div className="access-permissions">
          {group.items.map(permission => <label key={permission}><input type="checkbox" checked={selected.includes(permission)} onChange={e => toggle(permission, e.target.checked)} />
            <span>{permissionLabel(permission)}{LINE_MENU_PERMISSIONS[permission] ? <span className="access-line-badge" title={LINE_MENU_PERMISSIONS[permission]}>LINE</span> : null}{LINE_MENU_PERMISSIONS[permission] ? <small className="access-line-note">{LINE_MENU_PERMISSIONS[permission].slice(5)}</small> : null}</span>
          </label>)}
        </div>
      </section>;
    })}
  </fieldset>;
}
