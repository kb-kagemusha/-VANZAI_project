export type PostalAddress = { prefecture: string; address: string };

export function normalizePostalCode(value: string): string {
  return value.replace(/[０-９]/g, (digit) => String(digit.charCodeAt(0) - 0xff10)).replace(/[\s\-ー－]/g, "");
}

export async function lookupPostalAddress(postal: string, signal: AbortSignal): Promise<PostalAddress[]> {
  if (!/^[0-9]{7}$/.test(postal)) return [];
  const response = await fetch(`https://zipcloud.ibsnet.co.jp/api/search?zipcode=${postal}`, {
    signal, credentials: "omit", referrerPolicy: "no-referrer",
  });
  if (!response.ok) throw new Error("Postal lookup failed");
  const payload = await response.json();
  if (payload?.status !== 200) throw new Error("Postal lookup failed");
  if (!Array.isArray(payload.results)) return [];
  const choices: PostalAddress[] = [];
  for (const result of payload.results) {
    if (result.zipcode !== postal || ![result.address1, result.address2, result.address3].every((part) => typeof part === "string")) continue;
    const prefecture = result.address1.trim();
    const address = `${result.address2}${result.address3}`.trim();
    if (!prefecture || !address || prefecture.length > 50 || address.length > 1000) continue;
    if (!choices.some((item) => item.prefecture === prefecture && item.address === address)) choices.push({ prefecture, address });
  }
  return choices;
}
