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
  nearest_station: string;
  station_walk_minutes: string;
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
  nearest_station: "",
  station_walk_minutes: "",
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

export function lineRegistrationPayload(input: LineRegistrationInput, linked: boolean): Record<string, string> {
  const trimmed = Object.fromEntries(
    Object.entries(input).map(([key, value]) => [key, value.trim()]),
  ) as LineRegistrationInput;
  if (!linked) {
    return trimmed;
  }
  const payload: Record<string, string> = {};
  (["last_name", "first_name", "last_name_furigana", "first_name_furigana", "phone", "email", "birth_date", "nearest_station", "station_walk_minutes"] as const)
    .forEach((key) => {
      if (trimmed[key]) {
        payload[key] = trimmed[key];
      }
    });
  const addressTouched = Boolean(trimmed.postal_code || trimmed.prefecture || trimmed.address1 || trimmed.address2);
  if (addressTouched) {
    payload.postal_code = trimmed.postal_code;
    payload.prefecture = trimmed.prefecture;
    payload.address1 = trimmed.address1;
    payload.address2 = trimmed.address2;
  }
  return payload;
}
