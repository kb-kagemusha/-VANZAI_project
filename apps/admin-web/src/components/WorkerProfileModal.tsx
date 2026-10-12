import { useEffect, useRef, useState, type ReactNode } from "react";

import { splitStoredName, splitStoredAddress, joinStoredAddress } from "../lib/workerIdentity";
import { PREFECTURES } from "../lib/lineRegistrationUi";
import { lookupPostalAddress, normalizePostalCode, type PostalAddress } from "../lib/postalAddress";

import { WorkerTagPicker } from "./WorkerTags";
import type { WorkerDayAvailability, WorkerDayHours, WorkerListItem, WorkerProfileInput, WorkerTagOption, WorkerWeekday, WorkerWorkHistoryItem } from "../types/api";

const WEEKDAYS: { code: WorkerWeekday; label: string }[] = [
  { code: "mon", label: "月曜" },
  { code: "tue", label: "火曜" },
  { code: "wed", label: "水曜" },
  { code: "thu", label: "木曜" },
  { code: "fri", label: "金曜" },
  { code: "sat", label: "土曜" },
  { code: "sun", label: "日曜" },
];

const EMPLOYMENT_TYPES = ["正社員", "契約社員", "派遣", "アルバイト", "業務委託", "その他"];

type YesNo = "" | "yes" | "no";
type TruckDrive = "" | "2t" | "3t" | "none";

export interface WorkHistoryDraft {
  periodFrom: string;
  periodTo: string;
  companyName: string;
  employmentType: string;
  industry: string;
  jobDescription: string;
  resignationReason: string;
}

const DAY_STATUSES: { value: WorkerDayAvailability; label: string }[] = [
  { value: "all_day", label: "終日OK" },
  { value: "after_15", label: "15時～OK" },
  { value: "consult", label: "要相談" },
  { value: "unavailable", label: "稼働不可" },
];

export interface DayHoursDraft {
  status: WorkerDayAvailability | "";
  from: string;
  to: string;
}

export interface WorkerIntakeForm {
  name: string;
  furigana: string;
  lastName: string;
  firstName: string;
  lastNameFurigana: string;
  firstNameFurigana: string;
  prefecture: string;
  address1: string;
  address2: string;
  email: string;
  phone: string;
  emergencyContactPhone: string;
  emergencyContactName: string;
  emergencyContactRelationship: string;
  supplierId: string;
  notes: string;
  isActive: boolean;
  tags: string[];
  birthDate: string;
  maritalStatus: YesNo;
  postalCode: string;
  address: string;
  hometown: string;
  nearestStation: string;
  stationWalkMinutes: string;
  finalEducation: string;
  licensesQualifications: string;
  carDrive: YesNo;
  hiaceDrive: YesNo;
  truckDrive: TruckDrive;
  workHistory: WorkHistoryDraft[];
  ploomxSalesExperience: string;
  smoking: YesNo;
  luckySelf: string;
  hobbies: string;
  strengths: string;
  weaknesses: string;
  clubActivity: string;
  motivation: string;
  selfPr: string;
  lifeGoal: string;
  desiredIncome: string;
  availableDaysPerWeek: string;
  availableDayHours: Partial<Record<WorkerWeekday, DayHoursDraft>>;
  availableStartDate: string;
  paymentTermsOk: YesNo;
}

function emptyHistory(): WorkHistoryDraft {
  return {
    periodFrom: "",
    periodTo: "",
    companyName: "",
    employmentType: "",
    industry: "",
    jobDescription: "",
    resignationReason: "",
  };
}

export function emptyIntakeForm(): WorkerIntakeForm {
  return {
    name: "", furigana: "",
    lastName: "", firstName: "", lastNameFurigana: "", firstNameFurigana: "",
    prefecture: "", address1: "", address2: "",
    email: "",
    phone: "",
    emergencyContactPhone: "",
    emergencyContactName: "",
    emergencyContactRelationship: "",
    supplierId: "",
    notes: "",
    isActive: true,
    tags: [],
    birthDate: "",
    maritalStatus: "",
    postalCode: "",
    address: "",
    hometown: "",
    nearestStation: "",
    stationWalkMinutes: "",
    finalEducation: "",
    licensesQualifications: "",
    carDrive: "",
    hiaceDrive: "",
    truckDrive: "",
    workHistory: [emptyHistory()],
    ploomxSalesExperience: "",
    smoking: "",
    luckySelf: "",
    hobbies: "",
    strengths: "",
    weaknesses: "",
    clubActivity: "",
    motivation: "",
    selfPr: "",
    lifeGoal: "",
    desiredIncome: "",
    availableDaysPerWeek: "",
    availableDayHours: {},
    availableStartDate: "",
    paymentTermsOk: "",
  };
}

function yesNoFromBool(value: boolean | null | undefined): YesNo {
  if (value === true) return "yes";
  if (value === false) return "no";
  return "";
}

function boolFromYesNo(value: YesNo): boolean | null {
  if (value === "yes") return true;
  if (value === "no") return false;
  return null;
}

function clubInput(stored: string | null | undefined): string {
  const text = (stored ?? "").trim();
  return text.endsWith("部") ? text.slice(0, -1) : text;
}

function clubStored(input: string): string | null {
  const text = input.trim().replace(/部$/, "");
  return text ? `${text}部` : null;
}

function optionalText(value: string): string | null {
  const text = value.trim();
  return text || null;
}

function optionalBoundedInt(value: string, label: string, min: number, max: number): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (!/^\d+$/.test(trimmed)) {
    throw new Error(`${label}は${min}から${max}の整数で入力してください`);
  }
  const parsed = Number(trimmed);
  if (parsed < min || parsed > max) {
    throw new Error(`${label}は${min}から${max}の整数で入力してください`);
  }
  return parsed;
}

function formatPostal(stored: string | null | undefined): string {
  const digits = (stored ?? "").replace(/\D/g, "");
  if (digits.length === 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return digits;
}

function postalDigits(value: string): string | null {
  const digits = value.replace(/\D/g, "").slice(0, 7);
  return digits || null;
}

function isDayStatus(value: string | null | undefined): value is WorkerDayAvailability {
  return DAY_STATUSES.some((option) => option.value === value);
}

function dayStatusLabel(status: WorkerDayAvailability): string {
  return DAY_STATUSES.find((option) => option.value === status)?.label ?? status;
}

function daySummary(hours: DayHoursDraft | undefined): string {
  if (!hours) return "未設定";
  if (hours.status) return dayStatusLabel(hours.status);
  if (hours.from && hours.to) return `${formatClock(hours.from)}〜${formatClock(hours.to)}`;
  return "未設定";
}

function hoursFromProfile(profile: WorkerListItem["profile"]): Partial<Record<WorkerWeekday, DayHoursDraft>> {
  const stored = profile?.available_day_hours ?? [];
  if (stored.length > 0) {
    const hours: Partial<Record<WorkerWeekday, DayHoursDraft>> = {};
    for (const row of stored) {
      if (isDayStatus(row.status)) {
        hours[row.weekday] = { status: row.status, from: "", to: "" };
      } else if (row.time_from && row.time_to) {
        hours[row.weekday] = { status: "", from: row.time_from, to: row.time_to };
      }
    }
    return hours;
  }
  const from = profile?.available_time_from ?? "";
  const to = profile?.available_time_to ?? "";
  const hours: Partial<Record<WorkerWeekday, DayHoursDraft>> = {};
  if (!from || !to) return hours;
  for (const day of profile?.available_weekdays ?? []) {
    hours[day] = { status: "", from, to };
  }
  return hours;
}

function keepBuildingLine(current: string, previousAuto: string): string {
  const trimmed = current.trim();
  if (!trimmed) return "";
  if (previousAuto && trimmed.startsWith(previousAuto)) {
    return trimmed.slice(previousAuto.length).trim();
  }
  const newline = trimmed.indexOf("\n");
  if (newline >= 0) return trimmed.slice(newline + 1).trim();
  if (/[都道府県]/.test(trimmed)) return "";
  return trimmed;
}

function mergeLookedUpAddress(current: string, lookedUp: string, previousAuto: string): string {
  const building = keepBuildingLine(current, previousAuto);
  if (!building) return lookedUp;
  return `${lookedUp}\n${building}`;
}

function historyFromItem(item: WorkerWorkHistoryItem): WorkHistoryDraft {
  return {
    periodFrom: item.period_from ?? "",
    periodTo: item.period_to ?? "",
    companyName: item.company_name ?? "",
    employmentType: item.employment_type ?? "",
    industry: item.industry ?? "",
    jobDescription: item.job_description ?? "",
    resignationReason: item.resignation_reason ?? "",
  };
}

export function intakeFromWorker(worker: WorkerListItem): WorkerIntakeForm {
  const profile = worker.profile;
  const history = profile?.work_history?.length ? profile.work_history.map(historyFromItem) : [emptyHistory()];
  return {
    name: worker.name, furigana: worker.furigana ?? "",
    lastName: splitStoredName(worker.name)[0], firstName: splitStoredName(worker.name)[1],
    lastNameFurigana: splitStoredName(worker.furigana)[0], firstNameFurigana: splitStoredName(worker.furigana)[1],
    ...splitStoredAddress(worker.profile?.address),
    email: worker.email ?? "",
    phone: worker.phone ?? "",
    emergencyContactPhone: worker.emergency_contact_phone ?? "",
    emergencyContactName: worker.emergency_contact_name ?? "",
    emergencyContactRelationship: worker.emergency_contact_relationship ?? "",
    supplierId: worker.introducer_supplier_id ?? "",
    notes: worker.notes ?? "",
    isActive: worker.is_active,
    tags: worker.tags ?? [],
    birthDate: profile?.birth_date ?? "",
    maritalStatus: profile?.marital_status === "yes" || profile?.marital_status === "no" ? profile.marital_status : "",
    postalCode: formatPostal(profile?.postal_code),
    address: profile?.address ?? "",
    hometown: profile?.hometown ?? "",
    nearestStation: profile?.nearest_station ?? "",
    stationWalkMinutes: profile?.station_walk_minutes == null ? "" : String(profile.station_walk_minutes),
    finalEducation: profile?.final_education ?? "",
    licensesQualifications: profile?.licenses_qualifications ?? "",
    carDrive: yesNoFromBool(profile?.car_drive_ok),
    hiaceDrive: yesNoFromBool(profile?.hiace_drive_ok),
    truckDrive: profile?.truck_drive === "2t" || profile?.truck_drive === "3t" || profile?.truck_drive === "none" ? profile.truck_drive : "",
    workHistory: history,
    ploomxSalesExperience: profile?.ploomx_sales_experience ?? "",
    smoking: yesNoFromBool(profile?.smoking_ok),
    luckySelf: profile?.lucky_self ?? "",
    hobbies: profile?.hobbies ?? "",
    strengths: profile?.personality_strengths ?? "",
    weaknesses: profile?.personality_weaknesses ?? "",
    clubActivity: clubInput(profile?.club_activity),
    motivation: profile?.motivation ?? "",
    selfPr: profile?.self_pr ?? "",
    lifeGoal: profile?.life_goal ?? "",
    desiredIncome: profile?.desired_income ?? "",
    availableDaysPerWeek: profile?.available_days_per_week == null ? "" : String(profile.available_days_per_week),
    availableDayHours: hoursFromProfile(profile),
    availableStartDate: profile?.available_start_date ?? "",
    paymentTermsOk: yesNoFromBool(profile?.payment_terms_ok),
  };
}

export function intakeToRequest(form: WorkerIntakeForm, base: WorkerListItem | null) {
  if (!base && (!form.lastName.trim() || !form.firstName.trim() || !form.lastNameFurigana.trim() || !form.firstNameFurigana.trim())) {
    throw new Error("姓・名と、それぞれのふりがなを入力してください");
  }
  if (!base && (!form.emergencyContactPhone.trim() || !form.emergencyContactName.trim() || !form.emergencyContactRelationship.trim())) {
    throw new Error("緊急連絡先の電話番号・お名前・関係を入力してください");
  }
  if (form.emergencyContactPhone.trim() && !/^[0-9+\-]{1,20}$/.test(form.emergencyContactPhone.trim())) {
    throw new Error("緊急連絡先の電話番号は半角数字で入力してください");
  }
  const profile: WorkerProfileInput = {
    birth_date: form.birthDate || null,
    marital_status: form.maritalStatus || null,
    postal_code: postalDigits(form.postalCode),
    address: optionalText(joinStoredAddress(form.prefecture, form.address1, form.address2)),
    hometown: optionalText(form.hometown),
    nearest_station: optionalText(form.nearestStation),
    station_walk_minutes: optionalBoundedInt(form.stationWalkMinutes, "最寄駅から徒歩", 0, 300),
    final_education: optionalText(form.finalEducation),
    licenses_qualifications: optionalText(form.licensesQualifications),
    car_drive_ok: boolFromYesNo(form.carDrive),
    hiace_drive_ok: boolFromYesNo(form.hiaceDrive),
    truck_drive: form.truckDrive || null,
    work_history: form.workHistory
      .map((row) => ({
        period_from: row.periodFrom || null,
        period_to: row.periodTo || null,
        company_name: optionalText(row.companyName),
        employment_type: optionalText(row.employmentType),
        industry: optionalText(row.industry),
        job_description: optionalText(row.jobDescription),
        resignation_reason: optionalText(row.resignationReason),
      }))
      .filter((row) => Object.values(row).some((value) => value)),
    ploomx_sales_experience: optionalText(form.ploomxSalesExperience),
    smoking_ok: boolFromYesNo(form.smoking),
    lucky_self: optionalText(form.luckySelf),
    hobbies: optionalText(form.hobbies),
    personality_strengths: optionalText(form.strengths),
    personality_weaknesses: optionalText(form.weaknesses),
    club_activity: clubStored(form.clubActivity),
    motivation: optionalText(form.motivation),
    self_pr: optionalText(form.selfPr),
    life_goal: optionalText(form.lifeGoal),
    desired_income: optionalText(form.desiredIncome),
    available_days_per_week: optionalBoundedInt(form.availableDaysPerWeek, "稼働できる日数", 0, 7),
    available_day_hours: WEEKDAYS.flatMap((day): WorkerDayHours[] => {
      const hours = form.availableDayHours[day.code];
      if (!hours) return [];
      if (hours.status) {
        return [{ weekday: day.code, status: hours.status, time_from: null, time_to: null }];
      }
      if (hours.from && hours.to) {
        return [{ weekday: day.code, status: null, time_from: hours.from, time_to: hours.to }];
      }
      return [];
    }),
    available_weekdays: WEEKDAYS.map((day) => day.code).filter((code) => {
      const hours = form.availableDayHours[code];
      return Boolean(hours?.status || (hours?.from && hours?.to));
    }),
    available_time_from: null,
    available_time_to: null,
    available_start_date: form.availableStartDate || null,
    payment_terms_ok: boolFromYesNo(form.paymentTermsOk),
  };

  return {
    name: [form.lastName.trim(), form.firstName.trim()].filter(Boolean).join(" "),
    furigana: optionalText([form.lastNameFurigana.trim(), form.firstNameFurigana.trim()].filter(Boolean).join(" ")),
    email: optionalText(form.email),
    phone: optionalText(form.phone),
    sole_proprietor_name: base?.sole_proprietor_name ?? null,
    emergency_contact_name_kana: base?.emergency_contact_name_kana ?? null,
    emergency_contact_phone: optionalText(form.emergencyContactPhone),
    emergency_contact_name: optionalText(form.emergencyContactName),
    emergency_contact_relationship: optionalText(form.emergencyContactRelationship),
    gender: base?.gender ?? null,
    invoice_registration_status: base?.invoice_registration_status ?? null,
    invoice_number: base?.invoice_number ?? null,
    introducer_supplier_id: form.supplierId || null,
    notes: optionalText(form.notes),
    is_active: form.isActive,
    smoking_area_ok: base?.smoking_area_ok ?? null,
    has_p_shirt: base?.has_p_shirt ?? null,
    has_best: base?.has_best ?? null,
    stores_training_done: base?.stores_training_done ?? null,
    pioneer_training_done: base?.pioneer_training_done ?? null,
    p_shirt_count: base?.p_shirt_count ?? null,
    license_type: base?.license_type ?? null,
    tags: form.tags,
    profile,
  };
}

function ageFromBirthDate(iso: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const today = new Date();
  let age = today.getFullYear() - year;
  const todayKey = (today.getMonth() + 1) * 100 + today.getDate();
  if (todayKey < month * 100 + day) age -= 1;
  return age >= 0 ? age : null;
}

function formatBirthSentence(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return "〇年〇月〇日生まれ（〇〇歳）";
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const age = ageFromBirthDate(iso);
  if (age === null) return `${year}年${month}月${day}日生まれ`;
  return `${year}年${month}月${day}日生まれ（${age}歳）`;
}

function formatStartSentence(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return "〇月〇日〜可能";
  return `${Number(match[2])}月${Number(match[3])}日〜可能`;
}

function formatClock(value: string): string {
  const match = /^(\d{2}):(\d{2})$/.exec(value);
  if (!match) return "";
  const hour = Number(match[1]);
  const minute = Number(match[2]);
  return minute === 0 ? `${hour}時` : `${hour}時${minute}分`;
}

function todayInputValue(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function ChoiceButtons<T extends string>({
  label,
  hint,
  value,
  options,
  onChange,
  span = "order-span-6",
}: {
  label: string;
  hint?: string;
  value: T | "";
  options: { value: T; label: string }[];
  onChange: (next: T | "") => void;
  span?: string;
}) {
  return (
    <div className={`order-field ${span}`}>
      <span className="order-field-label">
        {label}
        {hint ? <span className="order-field-hint">{hint}</span> : null}
      </span>
      <div className="worker-choice" role="group" aria-label={label}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            className={value === option.value ? "is-on" : ""}
            aria-pressed={value === option.value}
            onClick={() => onChange(value === option.value ? "" : option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function WorkerProfileModal({
  mode,
  form,
  suppliers,
  tagOptions,
  error,
  message,
  pending,
  deletePending,
  onChange,
  onClose,
  onSubmit,
  onDelete,
  children,
}: {
  mode: "create" | "edit";
  form: WorkerIntakeForm;
  suppliers: { id: string; name: string }[];
  tagOptions: WorkerTagOption[];
  error: string;
  message: string;
  pending: boolean;
  deletePending: boolean;
  onChange: (next: WorkerIntakeForm) => void;
  onClose: () => void;
  onSubmit: () => void;
  onDelete?: () => void;
  children?: ReactNode;
}) {
  const [activeDay, setActiveDay] = useState<WorkerWeekday | null>(null);
  const [draftStatus, setDraftStatus] = useState<WorkerDayAvailability | "">("");
  const [dayMessage, setDayMessage] = useState("");
  const [postalMessage, setPostalMessage] = useState("");
  const formRef = useRef(form);
  const addressEditVersion = useRef(0);
  const [postalChoices, setPostalChoices] = useState<PostalAddress[]>([]);
  const lastLookedUpZip = useRef("");
  const postalTouched = useRef(false);
  formRef.current = form;

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    const digits = normalizePostalCode(form.postalCode);
    setPostalChoices([]);
    if (!postalTouched.current || !/^[0-9]{7}$/.test(digits)) return;
    if (digits === lastLookedUpZip.current) return;
    const controller = new AbortController();
    let active = true;
    const beforeEdit = addressEditVersion.current;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const timer = setTimeout(() => {
      setPostalMessage("住所を検索しています…");
      timeout = setTimeout(() => { controller.abort(); if (active) setPostalMessage("住所を取得できませんでした。手入力で続けられます。"); }, 10000);
      lookupPostalAddress(digits, controller.signal).then((addresses) => {
        if (!active) return;
        lastLookedUpZip.current = digits;
        const current = formRef.current;
        if (addresses.length === 1 && beforeEdit === addressEditVersion.current) {
          const found = addresses[0];
          onChange({ ...current, prefecture: found.prefecture, address1: found.address,
            address: joinStoredAddress(found.prefecture, found.address, current.address2) });
          setPostalMessage("住所を補完しました。番地は追記してください。");
        } else {
          setPostalChoices(addresses);
          setPostalMessage(addresses.length ? "手入力した住所を残しました。必要なら候補を選択してください。" : "住所が見つかりません。手入力してください。");
        }
      }).catch(() => { if (active && !controller.signal.aborted) setPostalMessage("住所を取得できませんでした。手入力で続けられます。"); })
        .finally(() => clearTimeout(timeout));
    }, 300);
    return () => { active = false; controller.abort(); clearTimeout(timer); clearTimeout(timeout); };
  }, [form.postalCode, onChange]);

  function patch(partial: Partial<WorkerIntakeForm>) {
    const next = { ...form, ...partial };
    if (["lastName", "firstName"].some((key) => key in partial)) next.name = [next.lastName.trim(), next.firstName.trim()].filter(Boolean).join(" ");
    if (["lastNameFurigana", "firstNameFurigana"].some((key) => key in partial)) next.furigana = [next.lastNameFurigana.trim(), next.firstNameFurigana.trim()].filter(Boolean).join(" ");
    if (["prefecture", "address1", "address2"].some((key) => key in partial)) {
      addressEditVersion.current += 1;
      next.address = joinStoredAddress(next.prefecture, next.address1, next.address2);
    }
    onChange(next);
  }

  function patchHistory(index: number, partial: Partial<WorkHistoryDraft>) {
    onChange({
      ...form,
      workHistory: form.workHistory.map((row, rowIndex) => (rowIndex === index ? { ...row, ...partial } : row)),
    });
  }

  function openDay(code: WorkerWeekday) {
    const saved = form.availableDayHours[code];
    setActiveDay(code);
    setDraftStatus(saved?.status ?? "");
    setDayMessage("");
  }

  function confirmDay() {
    if (!activeDay) return;
    if (!draftStatus) {
      setDayMessage("区分を選んでください");
      return;
    }
    patch({
      availableDayHours: {
        ...form.availableDayHours,
        [activeDay]: { status: draftStatus, from: "", to: "" },
      },
    });
    setDayMessage("");
    setActiveDay(null);
  }

  const activeDayLabel = WEEKDAYS.find((day) => day.code === activeDay)?.label ?? "";

  return (
    <div className="order-create-backdrop">
      <div
        className="order-draft is-modal worker-profile-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="worker-profile-title"
        tabIndex={-1}
      >
        <header className="order-draft-head">
          <div className="order-draft-head-lead">
            <p className="order-draft-kicker">稼働者登録</p>
            <h3 id="worker-profile-title">{mode === "create" ? "新規登録" : `${form.name || "稼働者"} を編集`}</h3>
            <p className="order-draft-lead">プロフィールと稼働条件を入力して保存します。</p>
          </div>
          <div className="order-draft-head-side">
            <button type="button" className="btn btn-ghost order-draft-close" onClick={onClose}>
              閉じる
            </button>
          </div>
        </header>

        <div className="order-draft-body">
          <section className="order-draft-section">
            <h4>基本</h4>
            <div className="order-draft-grid">
              {([ ["lastName", "姓", "山田"], ["firstName", "名", "太郎"], ["lastNameFurigana", "姓ふりがな", "やまだ"], ["firstNameFurigana", "名ふりがな", "たろう"] ] as const).map(([key, label, example]) => (
                <label key={key} className="order-field order-span-6">
                  <span className="order-field-label">{label}{mode === "create" ? <span style={{ color: "#dc2626" }}> *</span> : null}</span>
                  <input maxLength={100} value={form[key]} onChange={(event) => patch({ [key]: event.target.value })} placeholder={example} autoFocus={key === "lastName"} />
                </label>
              ))}
              <label className="order-field order-span-4">
                <span className="order-field-label">メール</span>
                <input type="email" value={form.email} onChange={(event) => patch({ email: event.target.value })} placeholder="任意" />
              </label>
              <label className="order-field order-span-4">
                <span className="order-field-label">電話</span>
                <input value={form.phone} onChange={(event) => patch({ phone: event.target.value })} placeholder="任意" />
              </label>
              <label className="order-field order-span-4">
                <span className="order-field-label">紹介会社</span>
                <select value={form.supplierId} onChange={(event) => patch({ supplierId: event.target.value })}>
                  <option value="">未設定</option>
                  {suppliers.map((supplier) => (
                    <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
                  ))}
                </select>
              </label>
              <label className="order-field order-span-4">
                <span className="order-field-label">緊急連絡先の電話番号{mode === "create" ? <span style={{ color: "#dc2626" }}> *</span> : null}</span>
                <input type="tel" inputMode="tel" maxLength={20} value={form.emergencyContactPhone} onChange={(event) => patch({ emergencyContactPhone: event.target.value })} placeholder="09012345678" />
              </label>
              <label className="order-field order-span-4">
                <span className="order-field-label">緊急連絡先のお名前{mode === "create" ? <span style={{ color: "#dc2626" }}> *</span> : null}</span>
                <input maxLength={200} value={form.emergencyContactName} onChange={(event) => patch({ emergencyContactName: event.target.value })} placeholder="山田 花子" />
              </label>
              <label className="order-field order-span-4">
                <span className="order-field-label">ご本人との関係{mode === "create" ? <span style={{ color: "#dc2626" }}> *</span> : null}</span>
                <input maxLength={50} value={form.emergencyContactRelationship} onChange={(event) => patch({ emergencyContactRelationship: event.target.value })} placeholder="実父・実兄・配偶者など" />
              </label>
              <label className="order-field order-span-4">
                <span className="order-field-label">備考</span>
                <input value={form.notes} onChange={(event) => patch({ notes: event.target.value })} placeholder="任意" />
              </label>
              <div className="order-field order-span-4">
                <span className="order-field-label">状態</span>
                <span className={form.isActive ? "worker-state-toggle is-active" : "worker-state-toggle"}>
                  <input type="checkbox" checked={form.isActive} onChange={(event) => patch({ isActive: event.target.checked })} />
                  {form.isActive ? "有効" : "無効"}
                </span>
              </div>
              <div className="order-field order-span-12">
                <WorkerTagPicker options={tagOptions} selected={form.tags} onChange={(tags) => patch({ tags })} />
              </div>
            </div>
          </section>

          <section className="order-draft-section">
            <h4>本人</h4>
            <div className="order-draft-grid">
              <label className="order-field order-span-6">
                <span className="order-field-label">生年月日（年齢）</span>
                <span className="worker-inline-input">
                  <input type="date" max={todayInputValue()} value={form.birthDate} onChange={(event) => patch({ birthDate: event.target.value })} />
                  <strong className="worker-age-readout">
                    {form.birthDate && ageFromBirthDate(form.birthDate) !== null ? `${ageFromBirthDate(form.birthDate)}歳` : "〇〇歳"}
                  </strong>
                </span>
                <span className="order-field-hint">{formatBirthSentence(form.birthDate)}</span>
              </label>
              <ChoiceButtons
                label="結婚有無"
                value={form.maritalStatus}
                options={[{ value: "yes", label: "あり" }, { value: "no", label: "なし" }]}
                onChange={(maritalStatus) => patch({ maritalStatus })}
              />
              <label className="order-field order-span-4">
                <span className="order-field-label">
                  郵便番号
                  <span className="order-field-hint">7桁で都道府県・市区町村まで入ります</span>
                </span>
                <input
                  value={form.postalCode}
                  inputMode="numeric"
                  autoComplete="postal-code"
                  placeholder="123-4567"
                  maxLength={8}
                  onChange={(event) => {
                    postalTouched.current = true;
                    patch({ postalCode: normalizePostalCode(event.target.value) });
                  }}
                />
              </label>
              {postalMessage ? <p className="form-error order-span-12">{postalMessage}</p> : null}
              {postalChoices.length ? <label className="order-field order-span-12"><span className="order-field-label">住所の候補</span><select defaultValue="" onChange={(event) => { const choice = postalChoices[Number(event.target.value)]; if (event.target.value && choice) patch({ prefecture: choice.prefecture, address1: choice.address }); }}><option value="">住所を選択してください</option>{postalChoices.map((choice, index) => <option key={index} value={index}>{choice.prefecture}{choice.address}</option>)}</select></label> : null}
              <label className="order-field order-span-4"><span className="order-field-label">都道府県</span><select value={form.prefecture} onChange={(event) => patch({ prefecture: event.target.value })}><option value="">選択してください</option>{PREFECTURES.map((prefecture) => <option key={prefecture} value={prefecture}>{prefecture}</option>)}</select></label>
              <label className="order-field order-span-8"><span className="order-field-label">市区町村・番地</span><input value={form.address1} onChange={(event) => patch({ address1: event.target.value })} placeholder="千代田区1-2-3" /></label>
              <label className="order-field order-span-12"><span className="order-field-label">建物名（任意）</span><input value={form.address2} onChange={(event) => patch({ address2: event.target.value })} placeholder="〇〇マンション101号室" /></label>
              <label className="order-field order-span-6">
                <span className="order-field-label">出身</span>
                <input value={form.hometown} onChange={(event) => patch({ hometown: event.target.value })} />
              </label>
              <label className="order-field order-span-6">
                <span className="order-field-label">最寄り駅</span>
                <input value={form.nearestStation} onChange={(event) => patch({ nearestStation: event.target.value })} />
              </label>
              <label className="order-field order-span-6">
                <span className="order-field-label">
                  最寄駅から徒歩
                  <span className="order-field-hint">{form.stationWalkMinutes.trim() ? `徒歩${form.stationWalkMinutes.trim()}分` : "徒歩〇分"}</span>
                </span>
                <span className="worker-inline-input">
                  <span>徒歩</span>
                  <input
                    inputMode="numeric"
                    value={form.stationWalkMinutes}
                    onChange={(event) => patch({ stationWalkMinutes: event.target.value })}
                    aria-label="最寄駅から徒歩の分数"
                  />
                  <span>分</span>
                </span>
              </label>
              <label className="order-field order-span-6">
                <span className="order-field-label">最終学歴</span>
                <input value={form.finalEducation} onChange={(event) => patch({ finalEducation: event.target.value })} />
              </label>
              <label className="order-field order-span-12">
                <span className="order-field-label">免許資格</span>
                <textarea className="is-short" value={form.licensesQualifications} onChange={(event) => patch({ licensesQualifications: event.target.value })} />
              </label>
              <div className="order-field order-span-12">
                <span className="order-field-label">運転可否</span>
                <div className="worker-drive-grid">
                  <ChoiceButtons
                    label="普通自動車運転"
                    span=""
                    value={form.carDrive}
                    options={[{ value: "yes", label: "可" }, { value: "no", label: "不可" }]}
                    onChange={(carDrive) => patch({ carDrive })}
                  />
                  <ChoiceButtons
                    label="ハイエース運転"
                    span=""
                    value={form.hiaceDrive}
                    options={[{ value: "yes", label: "可" }, { value: "no", label: "不可" }]}
                    onChange={(hiaceDrive) => patch({ hiaceDrive })}
                  />
                  <ChoiceButtons
                    label="トラック運転"
                    span=""
                    value={form.truckDrive}
                    options={[{ value: "2t", label: "2t可能" }, { value: "3t", label: "3t可能" }, { value: "none", label: "不可" }]}
                    onChange={(truckDrive) => patch({ truckDrive })}
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="order-draft-section">
            <h4>職歴</h4>
            <div className="worker-history-list">
              {form.workHistory.map((row, index) => {
                const employmentOptions = row.employmentType && !EMPLOYMENT_TYPES.includes(row.employmentType)
                  ? [row.employmentType, ...EMPLOYMENT_TYPES]
                  : EMPLOYMENT_TYPES;
                return (
                  <div key={index} className="worker-history-card">
                    <div className="worker-history-card-head">
                      <strong>職歴 {index + 1}</strong>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => patch({ workHistory: form.workHistory.filter((_, rowIndex) => rowIndex !== index) })}
                      >
                        この職歴を外す
                      </button>
                    </div>
                    <label className="order-field">
                      <span className="order-field-label">〇年〇月〜〇年〇月</span>
                      <span className="worker-inline-input">
                        <input type="month" value={row.periodFrom} onChange={(event) => patchHistory(index, { periodFrom: event.target.value })} aria-label="職歴の開始年月" />
                        <span>〜</span>
                        <input type="month" value={row.periodTo} onChange={(event) => patchHistory(index, { periodTo: event.target.value })} aria-label="職歴の終了年月" />
                      </span>
                    </label>
                    <div className="order-draft-grid">
                      <label className="order-field order-span-4">
                        <span className="order-field-label">会社名</span>
                        <input value={row.companyName} onChange={(event) => patchHistory(index, { companyName: event.target.value })} />
                      </label>
                      <label className="order-field order-span-4">
                        <span className="order-field-label">雇用形態</span>
                        <select value={row.employmentType} onChange={(event) => patchHistory(index, { employmentType: event.target.value })}>
                          <option value="">未選択</option>
                          {employmentOptions.map((option) => (
                            <option key={option} value={option}>{option}</option>
                          ))}
                        </select>
                      </label>
                      <label className="order-field order-span-4">
                        <span className="order-field-label">業種</span>
                        <input value={row.industry} onChange={(event) => patchHistory(index, { industry: event.target.value })} />
                      </label>
                      <label className="order-field order-span-6">
                        <span className="order-field-label">業務内容</span>
                        <textarea className="is-short" value={row.jobDescription} onChange={(event) => patchHistory(index, { jobDescription: event.target.value })} />
                      </label>
                      <label className="order-field order-span-6">
                        <span className="order-field-label">退職理由</span>
                        <textarea className="is-short" value={row.resignationReason} onChange={(event) => patchHistory(index, { resignationReason: event.target.value })} />
                      </label>
                    </div>
                  </div>
                );
              })}
              <div>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => patch({ workHistory: [...form.workHistory, emptyHistory()] })}
                  disabled={form.workHistory.length >= 20}
                >
                  職歴を追加
                </button>
              </div>
            </div>
          </section>

          <section className="order-draft-section">
            <h4>経験と人物</h4>
            <div className="order-draft-grid">
              <label className="order-field order-span-8">
                <span className="order-field-label">PloomXの販売経験</span>
                <textarea className="is-short" value={form.ploomxSalesExperience} onChange={(event) => patch({ ploomxSalesExperience: event.target.value })} />
              </label>
              <ChoiceButtons
                label="喫煙可否"
                span="order-span-4"
                value={form.smoking}
                options={[{ value: "yes", label: "可" }, { value: "no", label: "不可" }]}
                onChange={(smoking) => patch({ smoking })}
              />
              <label className="order-field order-span-6">
                <span className="order-field-label">自分自身の運がいいと思うか？</span>
                <input value={form.luckySelf} onChange={(event) => patch({ luckySelf: event.target.value })} />
              </label>
              <label className="order-field order-span-6">
                <span className="order-field-label">好きなこと(趣味)</span>
                <textarea className="is-short" value={form.hobbies} onChange={(event) => patch({ hobbies: event.target.value })} />
              </label>
              <label className="order-field order-span-6">
                <span className="order-field-label">自分の性格(長所)</span>
                <textarea className="is-short" value={form.strengths} onChange={(event) => patch({ strengths: event.target.value })} />
              </label>
              <label className="order-field order-span-6">
                <span className="order-field-label">自分の性格(短所)</span>
                <textarea className="is-short" value={form.weaknesses} onChange={(event) => patch({ weaknesses: event.target.value })} />
              </label>
              <label className="order-field order-span-6">
                <span className="order-field-label">
                  部活動
                  <span className="order-field-hint">{form.clubActivity.trim() ? `${form.clubActivity.trim().replace(/部$/, "")}部` : "〇部"}</span>
                </span>
                <span className="worker-inline-input">
                  <input value={form.clubActivity} onChange={(event) => patch({ clubActivity: event.target.value })} placeholder="野球" aria-label="部活動" />
                  <span>部</span>
                </span>
              </label>
              <label className="order-field order-span-6">
                <span className="order-field-label">欲しい年収・月収</span>
                <input value={form.desiredIncome} onChange={(event) => patch({ desiredIncome: event.target.value })} placeholder="例: 年収400万円 / 月収30万円" />
              </label>
              <label className="order-field order-span-12">
                <span className="order-field-label">志望動機</span>
                <textarea value={form.motivation} onChange={(event) => patch({ motivation: event.target.value })} />
              </label>
              <label className="order-field order-span-12">
                <span className="order-field-label">自己PR(スキルなど)</span>
                <textarea value={form.selfPr} onChange={(event) => patch({ selfPr: event.target.value })} />
              </label>
              <label className="order-field order-span-12">
                <span className="order-field-label">最終目標(夢は？)</span>
                <textarea className="is-short" value={form.lifeGoal} onChange={(event) => patch({ lifeGoal: event.target.value })} />
              </label>
            </div>
          </section>

          <section className="order-draft-section">
            <h4>稼働条件</h4>
            <div className="order-draft-grid">
              <label className="order-field order-span-4">
                <span className="order-field-label">
                  稼働できる日数
                  <span className="order-field-hint">{form.availableDaysPerWeek.trim() ? `週${form.availableDaysPerWeek.trim()}日` : "週〇日"}</span>
                </span>
                <span className="worker-inline-input">
                  <span>週</span>
                  <input
                    inputMode="numeric"
                    value={form.availableDaysPerWeek}
                    onChange={(event) => patch({ availableDaysPerWeek: event.target.value })}
                    aria-label="稼働できる日数"
                  />
                  <span>日</span>
                </span>
              </label>
              <div className="order-field order-span-12">
                <span className="order-field-label">稼働できる曜日</span>
                <div className="worker-preferences-card">
                  <div className="worker-preferences-grid">
                    {WEEKDAYS.map((day) => {
                      const sentence = daySummary(form.availableDayHours[day.code]);
                      return (
                        <button
                          key={day.code}
                          type="button"
                          className={activeDay === day.code ? "worker-preference-item worker-day-card is-editing" : "worker-preference-item worker-day-card"}
                          onClick={() => openDay(day.code)}
                        >
                          <span className="worker-preference-label">{day.label}</span>
                          <strong>{sentence}</strong>
                        </button>
                      );
                    })}
                  </div>
                  {activeDay ? (
                    <div className="worker-day-editor">
                      <span className="order-field-label">{activeDayLabel}</span>
                      <div className="worker-choice" role="group" aria-label={`${activeDayLabel}の区分`}>
                        {DAY_STATUSES.map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            className={draftStatus === option.value ? "is-on" : ""}
                            aria-pressed={draftStatus === option.value}
                            onClick={() => {
                              setDraftStatus(option.value);
                              setDayMessage("");
                            }}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                      {dayMessage ? <p className="form-error">{dayMessage}</p> : null}
                      <div className="worker-day-editor-actions">
                        <button type="button" className="btn btn-primary" onClick={confirmDay}>決定</button>
                      </div>
                    </div>
                  ) : (
                    <p className="order-field-hint">曜日をクリックして、終日OK、15時～OK、要相談、稼働不可から選んでください。</p>
                  )}
                </div>
              </div>
              <label className="order-field order-span-6">
                <span className="order-field-label">
                  稼働開始日
                  <span className="order-field-hint">{formatStartSentence(form.availableStartDate)}</span>
                </span>
                <span className="worker-inline-input">
                  <input type="date" value={form.availableStartDate} onChange={(event) => patch({ availableStartDate: event.target.value })} />
                  <span>〜可能</span>
                </span>
              </label>
              <ChoiceButtons
                label="支払いサイトに関して(月末締め→翌々月末～翌々々月10日で問題ないか？)"
                span="order-span-12"
                value={form.paymentTermsOk}
                options={[{ value: "yes", label: "YES" }, { value: "no", label: "NO" }]}
                onChange={(paymentTermsOk) => patch({ paymentTermsOk })}
              />
            </div>
          </section>

          {children}

          {error ? <p className="form-error">{error}</p> : null}
          {message ? <p style={{ margin: 0, color: "#16a34a" }}>{message}</p> : null}
        </div>

        <footer className="order-draft-foot">
          <div className="order-draft-foot-start">
            <button type="button" className="btn btn-ghost" onClick={onClose}>閉じる</button>
            {onDelete ? (
              <button type="button" className="btn btn-danger" onClick={onDelete} disabled={pending || deletePending}>
                {deletePending ? "削除中..." : "削除"}
              </button>
            ) : null}
          </div>
          <div className="order-draft-foot-end">
            <button type="button" className="btn btn-primary" disabled={!form.name.trim() || pending || deletePending} onClick={onSubmit}>
              {pending ? (mode === "create" ? "登録中..." : "更新中...") : (mode === "create" ? "登録する" : "更新する")}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
