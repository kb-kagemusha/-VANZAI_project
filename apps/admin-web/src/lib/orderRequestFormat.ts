/** 追加案件依頼。保存時は見出し付き本文と、欄を戻すためのJSONにする。 */

export const ORDER_DOCUMENT_TITLE = "【追加案件依頼】";
export const ORDER_FORMAT_ID = "additional-request-v1";
export const DEFAULT_ORDER_NOTES = "報酬の期限等その他の事項は、業務委託契約書記載のとおり。";

export interface OrderDocumentSections {
  projectName: string;
  background: string;
  workDateDetail: string;
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
  workDateDetail: "",
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
    work_date_detail: wavy(sections.workDateDetail.trim()),
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
    "■稼働日の詳細",
    wavy(sections.workDateDetail.trim()),
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
      workDateDetail: textOf(data.work_date_detail),
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

/** 稼働日の2つの日付を「2026年10月8日～2026年10月13日」にする。片方だけならその日付。 */
export function formatWorkDateRange(from: string, to: string): string {
  const start = jpDate(from);
  const end = jpDate(to);
  if (start && end) return `${start}～${end}`;
  if (start) return start;
  if (end) return `～${end}`;
  return "";
}

/** 上の書式だけを日付入力へ戻す。自由文は null。 */
export function parseWorkDateRange(label: string): { from: string; to: string } | null {
  const text = label.trim();
  const range = text.match(/^(\d{4})年(\d{1,2})月(\d{1,2})日[～〜](\d{4})年(\d{1,2})月(\d{1,2})日$/);
  if (range) {
    const from = isoDate(range[1], range[2], range[3]);
    const to = isoDate(range[4], range[5], range[6]);
    if (from && to) return { from, to };
    return null;
  }
  const onlyEnd = text.match(/^[～〜](\d{4})年(\d{1,2})月(\d{1,2})日$/);
  if (onlyEnd) {
    const to = isoDate(onlyEnd[1], onlyEnd[2], onlyEnd[3]);
    if (to) return { from: "", to };
    return null;
  }
  const single = text.match(/^(\d{4})年(\d{1,2})月(\d{1,2})日$/);
  if (single) {
    const from = isoDate(single[1], single[2], single[3]);
    if (from) return { from, to: "" };
  }
  return null;
}

function jpDate(iso: string): string {
  const match = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return "";
  const date = isoDate(match[1], match[2], match[3]);
  if (!date) return "";
  return `${Number(match[1])}年${Number(match[2])}月${Number(match[3])}日`;
}

function isoDate(year: string, month: string, day: string): string {
  const y = Number(year);
  const m = Number(month);
  const d = Number(day);
  if (!Number.isInteger(y) || !Number.isInteger(m) || !Number.isInteger(d)) return "";
  const date = new Date(Date.UTC(y, m - 1, d));
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m - 1 || date.getUTCDate() !== d) return "";
  return `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

/** PDFの見出し。src/services/order_request_pdf.py の order_request_document_title と同じ切り方。 */
export function orderRequestDocumentTitle(
  workDateLabel: string,
  projectName: string,
  notice: "new" | "change" | "cancel" = "new",
): string {
  const line = composeTitle(datePiece(workDateLabel), projectPiece(projectName), "");
  const head = notice === "cancel"
    ? "【発注済み依頼のキャンセル】"
    : notice === "change"
      ? "【発注依頼の変更】"
      : "【新規発注依頼】";
  return line ? `${head}\n${line}` : head;
}

/** ダウンロード名。src/services/order_request_pdf.py の order_request_pdf_filename と同じ切り方。 */
export function orderRequestPdfFileName(workDateLabel: string, projectName: string): string {
  const stem = composeTitle(filePiece(workDateLabel), filePiece(projectPiece(projectName)), "発注依頼書");
  return `${stem}.pdf`;
}

function composeTitle(date: string, project: string, empty: string): string {
  if (date && project) return `${date}：${project}`;
  if (date) return date;
  return project || empty;
}

function datePiece(value: string): string {
  return withFullwidthTilde(value).replace(/\s+/g, " ").trim();
}

function projectPiece(value: string): string {
  const first = value.split("\n").map((line) => line.trim()).find(Boolean) ?? "";
  return stripWrappedBrackets(withFullwidthTilde(first).replace(/\s+/g, " ").trim());
}

function stripWrappedBrackets(value: string): string {
  if (value.startsWith("【") && value.endsWith("】") && value.length > 2) {
    const inner = value.slice(1, -1).trim();
    if (inner) return inner;
  }
  return value;
}

function filePiece(value: string): string {
  return value
    .replace(/[\\/]/g, "／")
    .replace(/:/g, "：")
    .replace(/[*"<>|?\r\n\t]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^[ .]+|[ .]+$/g, "")
    .slice(0, 80);
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
