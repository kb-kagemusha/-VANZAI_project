import type { LineRegistrationInput } from "./lineRegistrationForm";

export const REGISTRATION_PRIVACY_NOTICE =
  "ご入力いただいた個人情報は、当社の稼働者情報の登録・更新、お仕事のご案内および業務連絡のために利用し、これらの目的以外には利用しません。";

export const PREFECTURES = [
  "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
  "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
  "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
  "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
  "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
  "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
  "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
];

export type RegistrationFieldErrors = Partial<Record<keyof LineRegistrationInput, string>>;

export function todayInJapan(): string {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date());
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

export function validateRegistrationInput(input: LineRegistrationInput, linked: boolean, today = todayInJapan()): RegistrationFieldErrors {
  const v = Object.fromEntries(Object.entries(input).map(([key, value]) => [key, value.trim()])) as LineRegistrationInput;
  const errors: RegistrationFieldErrors = {};
  const pair = (left: "last_name" | "last_name_furigana", right: "first_name" | "first_name_furigana", label: string, limit: number) => {
    if (!linked || v[left] || v[right]) {
      if (!v[left]) errors[left] = `${label}の姓を入力してください`;
      if (!v[right]) errors[right] = `${label}の名を入力してください`;
      if (v[left].length > 100 || v[right].length > 100 || `${v[left]} ${v[right]}`.length > limit) {
        errors[left] = `${label}は合わせて${limit}文字以内で入力してください`;
      }
    }
  };
  pair("last_name", "first_name", "お名前", 100);
  pair("last_name_furigana", "first_name_furigana", "ふりがな", 200);
  if (!linked && !v.phone) errors.phone = "電話番号を入力してください";
  else if (v.phone && !/^[0-9+\-]{1,20}$/.test(v.phone)) errors.phone = "半角数字で入力してください（ハイフンも使えます）";
  if (v.email && (!v.email.includes("@") || v.email.length > 255)) errors.email = "メールアドレスを確認してください";
  if (!linked && !v.birth_date) errors.birth_date = "生年月日を入力してください";
  if (v.birth_date) {
    const date = new Date(`${v.birth_date}T00:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v.birth_date) || Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== v.birth_date || v.birth_date > today) {
      errors.birth_date = "今日以前の実在する日付を選んでください";
    }
  }
  if (!linked || v.postal_code || v.prefecture || v.address1 || v.address2) {
    if (!/^[0-9]{7}$/.test(v.postal_code)) errors.postal_code = "郵便番号を半角数字7桁で入力してください";
    if (!PREFECTURES.includes(v.prefecture)) errors.prefecture = "都道府県を選択してください";
    if (!v.address1) errors.address1 = "市区町村・番地を入力してください";
  }
  if (v.nearest_station.length > 100) errors.nearest_station = "100文字以内で入力してください";
  if (v.station_walk_minutes && (!/^[0-9]{1,3}$/.test(v.station_walk_minutes) || Number(v.station_walk_minutes) > 300)) {
    errors.station_walk_minutes = "0〜300分の整数で入力してください";
  }
  return errors;
}
