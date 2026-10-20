import { additionalStationsPayload } from "./additionalStations";

export const LINE_REGISTRATION_NOT_SAVED =
  "前回の申請を管理者が確認中です。今回入力した内容は申請本文に保存していません";

export type LineRegistrationInput = {
  last_name: string;
  first_name: string;
  last_name_furigana: string;
  first_name_furigana: string;
  phone: string;
  email: string;
  birth_date: string;
  postal_code: string;
  prefecture: string;
  address1: string;
  address2: string;
  additional_stations: string;
  nearest_station: string;
  station_walk_minutes: string;
  emergency_contact_phone: string;
  emergency_contact_name: string;
  emergency_contact_relationship: string;
};

export const emptyLineRegistrationInput = (): LineRegistrationInput => ({
  last_name: "",
  first_name: "",
  last_name_furigana: "",
  first_name_furigana: "",
  phone: "",
  email: "",
  birth_date: "",
  postal_code: "",
  prefecture: "",
  address1: "",
  address2: "",
  additional_stations: "",
  nearest_station: "",
  station_walk_minutes: "",
  emergency_contact_phone: "",
  emergency_contact_name: "",
  emergency_contact_relationship: "",
});

export function registrationInputAfterSubjectChange(
  previousTag: string,
  nextTag: string,
  current: LineRegistrationInput,
): LineRegistrationInput {
  if (previousTag && previousTag !== nextTag) {
    return emptyLineRegistrationInput();
  }
  return current;
}

export type LineRegistrationScreen = {
  input: LineRegistrationInput;
  token: string;
  subject: string;
  linked: boolean;
  baseline?: LineRegistrationInput;
  formTicket?: string;
  targetTag?: string;
  needsReauth: boolean;
  error: string;
  message: string;
};

export function screenAfterUnauthorized(screen: LineRegistrationScreen, error: string): LineRegistrationScreen {
  return {
    ...screen,
    needsReauth: true,
    error,
    message: "",
  };
}

export function screenAfterReauthentication(
  screen: LineRegistrationScreen,
  next: { token: string; subject: string; linked: boolean },
): LineRegistrationScreen {
  const input = registrationInputAfterSubjectChange(screen.subject, next.subject, screen.input);
  const samePerson = screen.subject === next.subject;
  return {
    input,
    token: next.token,
    subject: next.subject,
    linked: next.linked,
    targetTag: samePerson ? screen.targetTag : undefined,
    baseline: samePerson ? screen.baseline : undefined,
    formTicket: samePerson ? screen.formTicket : undefined,
    needsReauth: false,
    error: samePerson ? "" : "別のLINEアカウントになったため、入力を消しました。",
    message: samePerson ? "本人確認をやり直しました。もう一度送信してください。" : "",
  };
}

export type RetainedSubmission = {
  key: string;
  payload: Record<string, string> | null;
};

export function idempotencyKeyAfterAttempt(current: string, status: number | "network"): string {
  return submissionRetentionAfterAttempt(current, { kept: "1" }, status).key;
}

export function submissionRetentionAfterAttempt(
  key: string,
  payload: Record<string, string>,
  status: number | "network",
): RetainedSubmission {
  if (status === "network" || status >= 500 || status === 401) {
    return { key, payload };
  }
  return { key: "", payload: null };
}

export function submissionRetentionAfterReauthentication(
  retained: RetainedSubmission,
  samePerson: boolean,
): RetainedSubmission {
  if (!samePerson) {
    return { key: "", payload: null };
  }
  return retained;
}

export function submissionRetentionAfterNewApplication(): RetainedSubmission {
  return { key: "", payload: null };
}

export function lineLoginExpired(error: string): boolean {
  return error.includes("LINEのログイン期限が切れました");
}

export function lineRegistrationPayload(input: LineRegistrationInput, linked: boolean, baseline?: LineRegistrationInput): Record<string, string> {
  const trimmed = Object.fromEntries(
    Object.entries(input).map(([key, value]) => [key, value.trim()]),
  ) as LineRegistrationInput;
  trimmed.additional_stations = additionalStationsPayload(trimmed.additional_stations);
  if (!linked) {
    return trimmed;
  }
  if (baseline) {
    const payload: Record<string, string> = {};
    const groups = [
      ["last_name", "first_name"], ["last_name_furigana", "first_name_furigana"],
      ["postal_code", "prefecture", "address1", "address2"],
      ["emergency_contact_phone", "emergency_contact_name", "emergency_contact_relationship"],
    ] as const;
    const grouped = new Set<string>(groups.flat());
    for (const keys of groups) {
      if (keys.some((key) => trimmed[key] !== baseline[key].trim())) {
        for (const key of keys) payload[key] = trimmed[key];
      }
    }
    for (const key of Object.keys(trimmed) as Array<keyof LineRegistrationInput>) {
      if (!grouped.has(key) && trimmed[key] && trimmed[key] !== baseline[key].trim()) payload[key] = trimmed[key];
    }
    return payload;
  }
  const payload: Record<string, string> = {};
  (["last_name", "first_name", "last_name_furigana", "first_name_furigana", "phone", "email", "birth_date", "nearest_station", "station_walk_minutes", "additional_stations"] as const)
    .forEach((key) => {
      if (trimmed[key]) {
        payload[key] = trimmed[key];
      }
    });
  const addressTouched = Boolean(trimmed.postal_code || trimmed.prefecture || trimmed.address1 || trimmed.address2);
  const contactTouched = Boolean(trimmed.emergency_contact_phone || trimmed.emergency_contact_name || trimmed.emergency_contact_relationship);
  if (contactTouched) {
    payload.emergency_contact_phone = trimmed.emergency_contact_phone;
    payload.emergency_contact_name = trimmed.emergency_contact_name;
    payload.emergency_contact_relationship = trimmed.emergency_contact_relationship;
  }
  if (addressTouched) {
    payload.postal_code = trimmed.postal_code;
    payload.prefecture = trimmed.prefecture;
    payload.address1 = trimmed.address1;
    payload.address2 = trimmed.address2;
  }
  return payload;
}

export function screenAfterRegisteredForm(
  screen: LineRegistrationScreen,
  form: { linked: boolean; registered?: Record<string, string> | null; form_ticket?: string | null; target_tag?: string | null },
  preserveEdits = false,
): LineRegistrationScreen {
  const fresh = { ...emptyLineRegistrationInput(), ...form.registered };
  const sameTarget = Boolean(screen.targetTag && screen.targetTag === form.target_tag);
  const input = { ...fresh };
  if (preserveEdits && sameTarget && screen.baseline) {
    for (const key of Object.keys(fresh) as Array<keyof LineRegistrationInput>) {
      if (screen.input[key] !== screen.baseline[key]) input[key] = screen.input[key];
    }
  } else if (preserveEdits && !form.registered && !screen.baseline) {
    Object.assign(input, screen.input);
  }
  return { ...screen, input, linked: form.linked,
    baseline: form.registered ? fresh : undefined,
    formTicket: form.form_ticket ?? undefined, targetTag: form.target_tag ?? undefined,
    message: preserveEdits && screen.targetTag && !sameTarget ? "紐付け先が変わったため、最新の登録情報を表示しました。内容を確認してください。" : screen.message };
}
