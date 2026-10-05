/** 追加案件依頼。保存時は見出し付き本文と、欄を戻すためのJSONにする。 */

export const ORDER_DOCUMENT_TITLE = "【追加案件依頼】";
export const ORDER_FORMAT_ID = "additional-request-v1";
export const DEFAULT_ORDER_NOTES = "報酬の期限等その他の事項は、業務委託契約書記載のとおり。";

export interface OrderDocumentSections {
  projectName: string;
  background: string;
  gatherTime: string;
  workTime: string;
  dismissTime: string;
  content: string;
  belongings: string;
  baseFee: string;
  incentive: string;
  notes: string;
}

export const EMPTY_ORDER_SECTIONS: OrderDocumentSections = {
  projectName: "",
  background: "",
  gatherTime: "",
  workTime: "",
  dismissTime: "",
  content: "",
  belongings: "",
  baseFee: "",
  incentive: "",
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
    gather_time: sections.gatherTime.trim(),
    work_time: sections.workTime.trim(),
    dismiss_time: sections.dismissTime.trim(),
    content: sections.content.trim(),
    belongings: sections.belongings.trim(),
    base_fee: sections.baseFee.trim(),
    incentive: sections.incentive.trim(),
    notes: sections.notes.trim(),
  });
}

export function composeOrderDocument(
  sections: OrderDocumentSections,
  workDateLabel: string,
  siteName: string,
): string {
  const notes = withBullet(sections.notes.trim());
  const base = withYen(sections.baseFee.trim());
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
    `集合時間：${sections.gatherTime.trim()}`,
    `実施時間：${sections.workTime.trim()}`,
    `解散時間：${sections.dismissTime.trim()}`,
    "",
    "■内容：",
    sections.content.trim(),
    "",
    "■持ち物：",
    sections.belongings.trim(),
    "",
    "■単価：",
    `ベース：${base}`,
    `インセンティブ：${sections.incentive.trim()}`,
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
      gatherTime: textOf(data.gather_time),
      workTime: textOf(data.work_time),
      dismissTime: textOf(data.dismiss_time),
      content: textOf(data.content),
      belongings: textOf(data.belongings),
      baseFee: textOf(data.base_fee),
      incentive: textOf(data.incentive),
      notes: textOf(data.notes),
    };
  } catch {
    return null;
  }
}

function textOf(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function withBullet(notes: string): string {
  if (!notes || notes.startsWith("・")) return notes;
  return `・${notes}`;
}

function withYen(amount: string): string {
  if (!amount || amount.startsWith("¥") || amount.startsWith("￥")) return amount;
  return `¥${amount}`;
}
