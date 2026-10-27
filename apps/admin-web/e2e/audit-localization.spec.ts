import { test, expect } from "@playwright/test";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { AUDIT_ACTION_OPTIONS, AUDIT_TARGET_TYPE_OPTIONS, formatAuditAction, formatAuditTargetType, formatAuditSummary } from "../src/lib/formatters";

test("監査画像の操作と対象種別を日本語で表示する", () => {
  for (const [code, label] of Object.entries({ ROLE_NAME_CHANGED: "役割名変更", client_updated: "クライアント更新", client_staff_created: "クライアント担当者作成", client_staff_updated: "クライアント担当者更新" })) {
    expect(formatAuditAction(code)).toBe(label);
    expect(AUDIT_ACTION_OPTIONS.find(option => option.value === code)?.label).toBe(label);
  }
  for (const [code, label] of Object.entries({ role_access_policy: "役割権限設定", client: "クライアント", client_staff: "クライアント担当者", worker: "稼働者" })) {
    expect(formatAuditTargetType(code)).toBe(label);
    expect(AUDIT_TARGET_TYPE_OPTIONS.find(option => option.value === code)?.label).toBe(label);
  }
});

test("定義済み操作と静的な監査記録箇所に日本語ラベルがある", () => {
  const root = resolve(process.cwd(), "../../src");
  const files = readdirSync(root, { recursive: true }).map(String).filter(name => name.endsWith(".py"));
  const enums = readFileSync(resolve(root, "models/enums.py"), "utf8").split("class AuditAction")[1].split("class InvoiceStatus")[0];
  const codes = [...enums.matchAll(/= "([a-z_]+)"/g)].map(match => match[1]);
  for (const file of files) {
    const source = readFileSync(resolve(root, file), "utf8");
    for (const match of source.matchAll(/\.log\(\s*(?:action\s*=\s*)?["']([a-zA-Z_]+)["']/g)) codes.push(match[1]);

  }
  for (const code of codes) expect(formatAuditAction(code), code).toMatch(/[一-龯ぁ-んァ-ン]/);
});

test("識別コードの大小文字と未知コード・自由記述を維持する", () => {
  expect(formatAuditAction("ROLE_NAME_CHANGED")).toBe(formatAuditAction("role_name_changed"));
  expect(formatAuditAction("future_action")).toBe("future_action");
  expect(formatAuditTargetType("future_target")).toBe("future_target");
  expect(formatAuditAction("クライアント作成")).toBe("クライアント作成");
  expect(formatAuditSummary("file_name=test.csv, count=2, new_name=管理者")).toBe("ファイル名=test.csv, 件数=2, 変更後の名称=管理者");
  expect(formatAuditSummary("担当者の依頼による変更")).toBe("担当者の依頼による変更");
});
