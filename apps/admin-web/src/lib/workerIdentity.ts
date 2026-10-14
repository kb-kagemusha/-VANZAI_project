import { PREFECTURES } from "./lineRegistrationUi";
export function splitStoredName(value: string | null | undefined): [string, string] {
  const text = (value ?? "").trim();
  const match = text.match(/^([^\s　]+)[\s　]+(.+)$/);
  return match ? [match[1], match[2]] : [text, ""];
}
export function splitStoredAddress(value: string | null | undefined) {
  const text = (value ?? "").trim();
  const newline = text.indexOf("\n");
  const first = newline < 0 ? text : text.slice(0, newline);
  const prefecture = PREFECTURES.find((item) => first.startsWith(item)) ?? "";
  return { prefecture, address1: first.slice(prefecture.length), address2: newline < 0 ? "" : text.slice(newline + 1) };
}
export function joinStoredAddress(prefecture: string, address1: string, address2: string): string {
  return `${prefecture.trim()}${address1.trim()}${address2.trim() ? `\n${address2.trim()}` : ""}`;
}
