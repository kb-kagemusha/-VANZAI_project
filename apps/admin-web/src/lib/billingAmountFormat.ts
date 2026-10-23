/** Keep the API decimal string separate from the grouped display; never round money. */
export function normalizeBillingAmount(value: string): string {
  return value.normalize("NFKC").replace(/,/g, "");
}

export function isValidBillingAmount(value: string): boolean {
  return /^\d+(?:\.\d{0,2})?$/.test(value) && value.split(".")[0].replace(/^0+/, "").length <= 13;
}

export function groupedBillingAmount(value: string): string {
  if (!/^\d*(?:\.\d*)?$/.test(value)) return value;
  const [whole, fraction] = value.split(".");
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + (fraction === undefined ? "" : `.${fraction}`);
}

/** Japanese units, matching e.g. 200000 → 20万円, without floating-point conversion. */
export function billingAmountReading(value: string): string {
  if (!isValidBillingAmount(value)) return "";
  const [digits, fraction = ""] = value.split(".");
  const whole = digits.replace(/^0+(?=\d)/, "");
  const units = ["", "万", "億", "兆"];
  const groups: string[] = [];
  let yen = "";
  for (let end = whole.length, index = 0; end > 0; end -= 4, index += 1) {
    const group = whole.slice(Math.max(0, end - 4), end).replace(/^0+/, "");
    if (index === 0) yen = group;
    else if (group) groups.unshift(group + units[index]);
  }
  const decimal = fraction.replace(/0+$/, "");
  if (decimal) yen = `${yen || "0"}.${decimal}`;
  return (groups.join("") + yen || "0") + "円";
}
