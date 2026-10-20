import type { Dispatch, SetStateAction } from "react";

const SUBJECTS: Record<string, string> = {
  dashboard: "ダッシュボード", master: "マスタ", price: "単価", project: "案件", shift: "シフト枠",
  assignment: "配置", actual: "実績", availability: "出勤可能日", csv: "CSV", invoice: "請求",
  payout: "支払", soft_close: "仮締め", hard_close: "本締め", expense: "経費",
  incentive: "インセンティブ", audit_log: "監査ログ", notice: "スタッフ通知", ocr: "OCR・在庫照合",
  order: "発注依頼書", registration: "登録申請",
};
const ACTIONS: Record<string, string> = { read: "閲覧", write: "編集", generate: "生成", issue: "発行", correct: "訂正",
  approve: "承認", submit: "提出", import: "取込", calculate: "計算", release: "解除", response: "回答", remind: "催促・要対応通知" };
export function permissionLabel(value: string) {
  if (value === "soft_close" || value === "hard_close") return SUBJECTS[value];
  const index = value.lastIndexOf("_");
  return (SUBJECTS[value.slice(0, index)] ?? value.slice(0, index)) + "：" + (ACTIONS[value.slice(index + 1)] ?? value.slice(index + 1));
}

export function RolePermissionPicker({ available, selected, setSelected, disabled }: {
  available: string[]; selected: string[]; setSelected: Dispatch<SetStateAction<string[]>>; disabled: boolean;
}) {
  function toggle(permission: string, checked: boolean) {
    const read = permission.slice(0, permission.lastIndexOf("_")) + "_read";
    setSelected(current => {
      if (checked) return Array.from(new Set([...current, permission, ...(available.includes(read) ? [read] : [])]));
      if (permission.endsWith("_read")) return current.filter(item => !item.startsWith(permission.slice(0, -4)));
      return current.filter(item => item !== permission);
    });
  }
  return <fieldset disabled={disabled} className="access-permissions"><legend>許可する機能</legend>
    {available.map(permission => <label key={permission}><input type="checkbox" checked={selected.includes(permission)} onChange={e => toggle(permission, e.target.checked)} />{permissionLabel(permission)}</label>)}
  </fieldset>;
}
