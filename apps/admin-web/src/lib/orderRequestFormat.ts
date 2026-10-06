/** 追加案件依頼。保存時は見出し付き本文と、欄を戻すためのJSONにする。 */

export const ORDER_DOCUMENT_TITLE = "【追加案件依頼】";
export const ORDER_FORMAT_ID = "additional-request-v1";
export const DEFAULT_ORDER_NOTES = "報酬の期限等その他の事項は、業務委託契約書記載のとおり。";

export interface OrderDocumentSections {
  projectName: string;
  background: string;
  hours: string;
  content: string;
  belongings: string;
  fee: string;
  notes: string;
}

export const EMPTY_ORDER_SECTIONS: OrderDocumentSections = {
  projectName: "",
  background: "",
  hours: "",
  content: "",
  belongings: "",
  fee: "",
  notes: DEFAULT_ORDER_NOTES,
};

export function sectionsFromStored(requestConditions: string, body: string): OrderDocumentSections {
  const parsed = parseSections(requestConditions);
  if (parsed) {
    return {
      ...parsed,
      notes: parsed.notes || DEFAULT_ORDER_NOTES,
    };
  }
  const legacy = [requestConditions, body].map((item) => item.trim()).filter(Boolean).join("\n\n");
  return {
    ...EMPTY_ORDER_SECTIONS,
    content: legacy,
  };
}

export function serializeOrderSections(sections: OrderDocumentSections): string {
  return JSON.stringify({
    format: ORDER_FORMAT_ID,
    project_name: sections.projectName.trim(),
    background: sections.background.trim(),
    hours: sections.hours.trim(),
    content: sections.content.trim(),
    belongings: sections.belongings.trim(),
    fee: sections.fee.trim(),
    notes: sections.notes.trim(),
  });
}

export function composeOrderDocument(
  sections: OrderDocumentSections,
  workDateLabel: string,
  siteName: string,
): string {
  const notes = withBullet(sections.notes.trim());
  return [
    ORDER_DOCUMENT_TITLE,
    "",
    "■案件名",
    sections.projectName.trim(),
    "",
    "■背景",
    sections.background.trim(),
    "",
    "■稼働場所",
    siteName.trim(),
    "",
    "■稼働日",
    workDateLabel.trim(),
    "",
    "■稼働時間",
    sections.hours.trim(),
    "",
    "■内容：",
    sections.content.trim(),
    "",
    "■持ち物：",
    sections.belongings.trim(),
    "",
    "■単価：",
    sections.fee.trim(),
    "",
    "■備考：",
    notes,
  ].join("\n");
}

function parseSections(requestConditions: string): OrderDocumentSections | null {
  const text = requestConditions.trim();
  if (!text.startsWith("{")) return null;
  try {
    const data = JSON.parse(text) as Record<string, unknown>;
    if (data.format !== ORDER_FORMAT_ID) return null;
    return {
      projectName: textOf(data.project_name),
      background: textOf(data.background),
      hours: textOf(data.hours) || legacyHours(data),
      content: textOf(data.content),
      belongings: textOf(data.belongings),
      fee: textOf(data.fee) || legacyFee(data),
      notes: textOf(data.notes),
    };
  } catch {
    return null;
  }
}

function legacyHours(data: Record<string, unknown>): string {
  return [
    labeled("集合時間", textOf(data.gather_time)),
    labeled("実施時間", textOf(data.work_time)),
    labeled("解散時間", textOf(data.dismiss_time)),
  ].filter(Boolean).join("\n");
}

function legacyFee(data: Record<string, unknown>): string {
  const base = textOf(data.base_fee);
  const incentive = textOf(data.incentive);
  const lines = [];
  if (base) {
    const amount = base.startsWith("¥") || base.startsWith("￥") ? base : `¥${base}`;
    lines.push(`ベース：${amount}`);
  }
  if (incentive) lines.push(`インセンティブ：${incentive}`);
  return lines.join("\n");
}

function labeled(label: string, value: string): string {
  return value ? `${label}：${value}` : "";
}

function textOf(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function withBullet(notes: string): string {
  if (!notes || notes.startsWith("・")) return notes;
  return `・${notes}`;
}
