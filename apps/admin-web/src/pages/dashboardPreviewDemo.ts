export type DemoSlice = {
  label: string;
  value: number;
  color: string;
};

export const DEMO_PROJECT_TREND = [28, 31, 29, 34, 36, 33, 40, 38, 42, 41, 45, 48];
export const DEMO_WORKER_TREND = [120, 128, 124, 136, 142, 138, 150, 155, 160, 168, 174, 186];

export const DEMO_FINANCE = {
  sales: [820, 860, 790, 910, 980, 940, 1100, 1080, 1160, 1210, 1280, 1340],
  labor: [510, 540, 500, 560, 600, 590, 680, 670, 710, 740, 760, 790],
  profit: [310, 320, 290, 350, 380, 350, 420, 410, 450, 470, 520, 550],
} as const;

export const DEMO_CLIENT_SHARE: DemoSlice[] = [
  { label: "北斗興業", value: 42, color: "#16a34a" },
  { label: "青葉フーズ", value: 33, color: "#2563eb" },
  { label: "みどり企画", value: 26, color: "#d97706" },
  { label: "その他", value: 18, color: "#94a3b8" },
];

export const DEMO_TYPE_SHARE: DemoSlice[] = [
  { label: "イベント", value: 74, color: "#16a34a" },
  { label: "飲食", value: 45, color: "#2563eb" },
];

export const DEMO_STAFF_ORDERS = [
  { name: "佐藤 美咲", count: 8, color: "#16a34a" },
  { name: "鈴木 蓮", count: 6, color: "#2563eb" },
  { name: "高橋 陽菜", count: 5, color: "#d97706" },
  { name: "田中 隼", count: 4, color: "#7c3aed" },
  { name: "伊藤 葵", count: 3, color: "#0f766e" },
];

export const DEMO_EQUIPMENT = [
  { name: "テント", stock: 12, status: "在庫" },
  { name: "長机", stock: 40, status: "在庫" },
  { name: "のぼり", stock: 8, status: "貸出中" },
  { name: "クーラーボックス", stock: 6, status: "在庫" },
  { name: "延長コード", stock: 15, status: "一部貸出" },
];

export const FINANCE_LABELS = {
  sales: "売上",
  labor: "人件費",
  profit: "粗利益",
} as const;

export const FINANCE_COLORS: Record<keyof typeof FINANCE_LABELS, string> = {
  sales: "#16a34a",
  labor: "#2563eb",
  profit: "#0f766e",
};

export type FinanceKey = keyof typeof FINANCE_LABELS;

const MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];

export function demoMonthLabels(): string[] {
  return MONTHS;
}

export type ChartPoint = { x: number; y: number; value: number };

export function axisTicks(maxValue: number): number[] {
  const target = Math.max(maxValue, 1) * 1.18;
  const rough = target / 4;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((factor) => factor * power).find((candidate) => candidate >= rough) ?? rough;
  const ticks: number[] = [];
  for (let value = 0; value <= target + step * 0.01; value += step) {
    ticks.push(Math.round(value));
  }
  const last = ticks[ticks.length - 1] ?? 0;
  if (last <= maxValue) ticks.push(Math.round(last + step));
  return ticks;
}

export function plotPoints(
  values: number[],
  width: number,
  height: number,
  inset: { left: number; right: number; top: number; bottom: number },
  scale: { min: number; max: number },
): ChartPoint[] {
  const span = scale.max - scale.min || 1;
  return values.map((value, index) => ({
    value,
    x: inset.left + (index / Math.max(values.length - 1, 1)) * (width - inset.left - inset.right),
    y: inset.top + (1 - (value - scale.min) / span) * (height - inset.top - inset.bottom),
  }));
}

export function smoothLine(points: ChartPoint[], yMin = Number.NEGATIVE_INFINITY, yMax = Number.POSITIVE_INFINITY): string {
  if (points.length === 0) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  const clampY = (y: number) => Math.min(yMax, Math.max(yMin, y));
  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const previous = points[index - 1] ?? points[index];
    const current = points[index];
    const next = points[index + 1];
    const after = points[index + 2] ?? next;
    const control1x = current.x + (next.x - previous.x) / 6;
    const control1y = clampY(current.y + (next.y - previous.y) / 6);
    const control2x = next.x - (after.x - current.x) / 6;
    const control2y = clampY(next.y - (after.y - current.y) / 6);
    path += ` C ${control1x} ${control1y}, ${control2x} ${control2y}, ${next.x} ${next.y}`;
  }
  return path;
}

export function linePoints(values: number[], width: number, height: number, pad = 8): string {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((value, index) => {
      const x = pad + (index / (values.length - 1)) * (width - pad * 2);
      const y = height - pad - ((value - min) / span) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");
}

export function areaPath(values: number[], width: number, height: number, pad = 8): string {
  const points = linePoints(values, width, height, pad).split(" ");
  const firstX = points[0]?.split(",")[0] ?? String(pad);
  const lastX = points[points.length - 1]?.split(",")[0] ?? String(width - pad);
  return `M ${points.join(" L ")} L ${lastX},${height - pad} L ${firstX},${height - pad} Z`;
}

export function donutSegments(slices: DemoSlice[], radius: number) {
  const total = slices.reduce((sum, slice) => sum + slice.value, 0) || 1;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return slices.map((slice) => {
    const length = (slice.value / total) * circumference;
    const segment = { ...slice, length, offset, share: Math.round((slice.value / total) * 100) };
    offset += length;
    return segment;
  });
}
