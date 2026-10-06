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
  incentive: string;
  notes: string;
}

export const EMPTY_ORDER_SECTIONS: OrderDocumentSections = {
  projectName: "",
  background: "",
  hours: "",
  content: "",
  belongings: "",
  fee: "",
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
    project_name: wavy(sections.projectName.trim()),
    background: wavy(sections.background.trim()),
    hours: wavy(sections.hours.trim()),
    content: wavy(sections.content.trim()),
    belongings: wavy(sections.belongings.trim()),
    fee: wavy(sections.fee.trim()),
    incentive: wavy(sections.incentive.trim()),
    notes: wavy(sections.notes.trim()),
  });
}

export function composeOrderDocument(
  sections: OrderDocumentSections,
  workDateLabel: string,
  siteName: string,
): string {
  const notes = withBullet(wavy(sections.notes.trim()));
  return [
    ORDER_DOCUMENT_TITLE,
    "",
    "■案件名",
    wavy(sections.projectName.trim()),
    "",
    "■背景",
    wavy(sections.background.trim()),
    "",
    "■稼働場所",
    wavy(siteName.trim()),
    "",
    "■稼働日",
    wavy(workDateLabel.trim()),
    "",
    "■稼働時間",
    wavy(sections.hours.trim()),
    "",
    "■内容：",
    wavy(sections.content.trim()),
    "",
    "■持ち物：",
    wavy(sections.belongings.trim()),
    "",
    "■単価：",
    wavy(sections.fee.trim()),
    "",
    "■インセンティブ：",
    wavy(sections.incentive.trim()),
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
      incentive: textOf(data.incentive),
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
  if (!base) return "";
  const amount = base.startsWith("¥") || base.startsWith("￥") ? base : `¥${base}`;
  return `ベース：${amount}`;
}

export function siteLabelForList(value: string): string {
  const text = value
    .split("\n")
    .map((line) => line.replace(/https?:\/\/\S+/g, "").trim())
    .filter(Boolean)
    .join("\n");
  return text || "—";
}

export function withFullwidthTilde(value: string): string {
  return value.replace(/~/g, "～");
}

/** ダウンロード名。src/services/order_request_pdf.py の order_request_pdf_filename と同じ切り方。 */
export function orderRequestPdfFileName(workDateLabel: string, projectName: string): string {
  const piece = (value: string) =>
    value
      .replace(/[\\/]/g, "／")
      .replace(/:/g, "：")
      .replace(/[*"<>|?\r\n\t]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/^[ .]+|[ .]+$/g, "")
      .slice(0, 80);
  const date = piece(workDateLabel);
  const project = piece(projectName);
  const stem = date && project ? `${date}＋${project}` : date || project || "発注依頼書";
  return `${stem}.pdf`;
}

/** 公式LINEの送信文。src/services/line_order.py の _push_messages と同じ切り方。 */
export const LINE_TEST_BANNER = "テスト・正式な発注ではありません";
export const LINE_ACCEPT_LABEL = "依頼の案件、受諾します";
export const LINE_DECLINE_LABEL = "今回は辞退します";
export const LINE_BUTTON_TEXT = "内容を確認して、受諾または辞退を押してください。";
export const LINE_DECLINE_PROMPT = "辞退理由を簡単にお聞かせください";

export function linePushPreviewText(input: {
  documentNumber: string;
  versionNo: number;
  projectName: string;
  workDateLabel: string;
  siteName: string;
  isTest?: boolean;
}): string {
  const lines = [
    ...(input.isTest === false ? [] : [LINE_TEST_BANNER]),
    `発注依頼書 ${input.documentNumber}（版${input.versionNo}）`,
    `案件名: ${withFullwidthTilde(input.projectName)}`.slice(0, 80),
    `稼働日: ${withFullwidthTilde(input.workDateLabel)}`.slice(0, 80),
    `現場: ${withFullwidthTilde(input.siteName)}`.slice(0, 80),
    ...(input.isTest === false ? [] : ["このメッセージはテスト送信です。"]),
    "PDF: （送信時にリンクが付きます）",
  ];
  return lines.join("\n").slice(0, 500);
}

function labeled(label: string, value: string): string {
  return value ? `${label}：${value}` : "";
}

function textOf(value: unknown): string {
  return typeof value === "string" ? wavy(value.trim()) : "";
}

function wavy(value: string): string {
  return withFullwidthTilde(value);
}

function withBullet(notes: string): string {
  if (!notes || notes.startsWith("・")) return notes;
  return `・${notes}`;
}
