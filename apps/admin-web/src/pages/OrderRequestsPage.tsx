/**
 * 発注依頼書の作成・確定・共有一覧。
 * 確定した版は、稼働者登録・一覧で紐付けた送付先へ公式LINEで送る。
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { FormDialog } from "../components/FormDialog";
import { OrderDatePicker } from "../components/OrderDatePicker";
import { OrderRequestTemplatesDialog } from "../components/OrderRequestTemplatesDialog";
import { HolidayPicker, OrderScheduleEditor } from "../components/OrderScheduleEditor";
import { OrderLocationEditor } from "../components/OrderLocationEditor";
import { OrderInternalSourceEditor } from "../components/OrderInternalSourceEditor";
import { VersionParticipationSummary } from "./ParticipationCalendarPage";
import { applyPeriodHolidays, singleDaysOnHolidays, compactDateList, dateGroupLabel, emptySchedule, newWorkGroup, scheduleDateLabel, scheduleWorkDates, syncSchedule, type OrderSchedule } from "../lib/orderSchedule";
import { matchesWorkerRoles } from "../lib/workerRoleFilter";
import {
  ApiError,
  addOrderRequestNote,
  cancelOrderRequest,
  confirmOrderRequest,
  createOrderRequest,
  downloadOrderRequestPdf,
  fetchOrderRequestPdfPreview,
  getOrderRequestVersion,
  getOrderRequestTemplate,
  saveOrderRequestTemplate,
  getWorkers,
  getWorkerTags,
  hideOrderRequest,
  listLineLinks,
  listOrderRequestReplies,
  listOrderRequests,
  reviseOrderRequest,
  sendOrderRequestLine,
  updateOrderRequestVersion,
  withdrawOrderRequestAcceptance,
} from "../lib/api/client";
import {
  composeOrderDocument,
  EMPTY_ORDER_SECTIONS,
  formatWorkDateRange,
  LINE_ACCEPT_LABEL,
  LINE_BUTTON_TEXT,
  LINE_DECLINE_LABEL,
  LINE_DECLINE_PROMPT,
  LINE_TEST_BANNER,
  linePushPreviewText,
  orderRequestDocumentTitle,
  orderRequestPdfFileName,
  ORDER_DOCUMENT_TITLE,
  parseWorkDateRange,
  sectionHolidays,
  sectionsFromStored,
  serializeOrderSections,
  siteLabelForList,
  categoryLabelForList,
  ORDER_CATEGORY_OPTIONS,
  TRAINING_CATEGORY,
  toggleOrderCategory,
  withFullwidthTilde,
  type OrderDocumentSections,
} from "../lib/orderRequestFormat";
import { confirmApp, promptApp } from "../lib/appDialog";
import { useAuth } from "../lib/auth/auth-context";
import { hasPermission } from "../lib/auth/permissions";
import type {
  OrderRequestChangeLink,
  OrderRequestDelivery,
  OrderRequestKind,
  OrderRequestQueue,
  OrderRequestStatus,
  OrderRequestVersion,
  OrderRequestWrite,
} from "../types/orderRequest";

const SEND_LABEL: Record<string, string> = {
  unsent: "未送信",
  processing: "送信中",
  accepted: "受付済",
  failed: "失敗",
  unknown: "結果不明",
};

const MAX_ORDER_RECIPIENTS = 40;

async function loadOrderRecipients() {
  const first = await getWorkers({ limit: 200, offset: 0, is_active: true, sort_by: "name", sort_order: "asc" });
  const items = [...first.items];
  let offset = first.items.length;
  while (offset < first.total) {
    const page = await getWorkers({ limit: 200, offset, is_active: true, sort_by: "name", sort_order: "asc" });
    if (!page.items.length) break;
    items.push(...page.items);
    offset += page.items.length;
  }
  return { ...first, items: [...new Map(items.map((item) => [item.id, item])).values()] };
}

const REPLY_LABEL: Record<string, string> = {
  unacked: "未回答",
  acked: "受諾",
  decline_pending: "辞退理由待ち",
  declined: "辞退",
};

function formatCreatedOn(value: string | null | undefined): string {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return "";
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

const STATUS_LABEL: Record<OrderRequestStatus, string> = {
  draft: "下書き",
  confirmed: "確定",
  cancelled: "取消",
};

function basedOnNote(
  documentNumber: string,
  sourceNumber: string | null | undefined,
  sourceVersion: number | null | undefined,
): string | null {
  if (!sourceNumber || sourceVersion == null) return null;
  if (sourceNumber === documentNumber) return `第${sourceVersion}版の変更`;
  return `${sourceNumber} の変更`;
}

function changeLinkLabel(documentNumber: string, change: OrderRequestChangeLink): string {
  if (change.document_number === documentNumber) return `変更 第${change.version_no}版`;
  return `変更 ${change.document_number}`;
}

/** 送付先ごとの個人不参加日を、今の送付先と実勤務日（休業日を除く）に合わせて整える（DEC-065）。 */
function currentAbsences(form: OrderRequestWrite, sections: OrderDocumentSections): Record<string, string[]> {
  const days = new Set(scheduleWorkDates(sections.schedule));
  const result: Record<string, string[]> = {};
  for (const workerId of form.worker_ids) {
    const dates = (form.recipient_absences?.[workerId] ?? []).filter((day) => days.has(day));
    if (dates.length > 0) result[workerId] = [...new Set(dates)].sort();
  }
  return result;
}

const EMPTY_FORM: OrderRequestWrite = {
  internal_source: null,
  kind: "formal",
  work_date_label: "",
  site_id: null,
  site_name: "",
  site_address: null,
  request_conditions: "",
  body: "",
  contact_name: "",
  contact_desk: "",
  counterparty_note: "",
  worker_ids: [],
  recipient_absences: {},
  allow_partial_accept: false,
  phone_first: false,
  phone_note: "",
  tracker_user_id: null,
  follow_up_due_on: null,
  follow_up_due_time: "21:00",
  assign_tracker_self: false,
};

/** 全体の稼働日が空のときは、日付・期間ごとの入力の最初と最後の日から補う（送付前の入力漏れで止まらないように）。 */
function withScheduleDateLabel(form: OrderRequestWrite, sections: OrderDocumentSections): OrderRequestWrite {
  if (form.work_date_label.trim() || !sections.schedule) return form;
  const days = sections.schedule.work_groups.flatMap((group) => [group.from, group.to]).filter(Boolean).sort();
  if (days.length === 0) return form;
  return { ...form, work_date_label: formatWorkDateRange(days[0], days[days.length - 1]) };
}

const CONTACT_NONE = "なし";

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "処理に失敗しました";
}

export function OrderRequestsPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const canWrite = hasPermission(user, "order_write");
  const [templatesOpen, setTemplatesOpen] = useState(false);
  const [saveTemplateFor, setSaveTemplateFor] = useState<{ id: string; label: string } | null>(null);
  const [templateName, setTemplateName] = useState("");
  const [templateSaving, setTemplateSaving] = useState(false);
  const [templateError, setTemplateError] = useState("");
  const [kind, setKind] = useState<OrderRequestKind | "all">("formal");
  const [queue, setQueue] = useState<OrderRequestQueue>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<OrderRequestWrite>(EMPTY_FORM);
  const [sections, setSections] = useState<OrderDocumentSections>(EMPTY_ORDER_SECTIONS);
  const [workerSearch, setWorkerSearch] = useState("");
  const [absenceWorkerId, setAbsenceWorkerId] = useState<string | null>(null);
  const [workerRoleFilters, setWorkerRoleFilters] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [linePreviewOpen, setLinePreviewOpen] = useState(false);
  const linePreviewOpenRef = useRef(linePreviewOpen);
  linePreviewOpenRef.current = linePreviewOpen;
  const [savedDraftId, setSavedDraftId] = useState<string | null>(null);
  const [pdfReview, setPdfReview] = useState<{ phase: "loading" | "ready"; versionId: string | null; url: string | null } | null>(null);
  const [pdfReviewError, setPdfReviewError] = useState("");
  const [pdfSending, setPdfSending] = useState(false);
  const pdfReviewRef = useRef(false);
  pdfReviewRef.current = pdfReview !== null;
  const [sendingSelected, setSendingSelected] = useState(false);
  const [basedOn, setBasedOn] = useState<{ versionId: string; documentNumber: string; versionNo: number } | null>(null);
  const [changeLoading, setChangeLoading] = useState(false);
  const [participationFor, setParticipationFor] = useState<{ versionId: string; title: string } | null>(null);
  const draftRef = useRef<HTMLFormElement>(null);
  const formRef = useRef(form);
  const sectionsRef = useRef(sections);
  const loadedForRef = useRef<string | null>(null);
  formRef.current = form;
  sectionsRef.current = sections;

  const listQuery = useQuery({
    queryKey: ["order-requests", kind, queue],
    queryFn: () => listOrderRequests({ kind, queue, limit: 50, offset: 0 }),
  });
  const repliesQuery = useQuery({
    queryKey: ["order-request-replies"],
    queryFn: listOrderRequestReplies,
    // 公式LINEでの受諾・辞退を、画面を開き直さずに反映する
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });
  const workersQuery = useQuery({
    queryKey: ["order-request-workers"],
    queryFn: loadOrderRecipients,
  });
  const workerRolesQuery = useQuery({ queryKey: ["worker-tags"], queryFn: getWorkerTags });
  const workerRoles = workerRolesQuery.data?.items ?? [];
  const detailQuery = useQuery({
    queryKey: ["order-request", selectedId],
    queryFn: () => getOrderRequestVersion(selectedId as string),
    enabled: Boolean(selectedId) && !creating,
    refetchOnWindowFocus: true,
  });

  const workers = workersQuery.data?.items ?? [];
  const visibleWorkers = useMemo(() => {
    const query = workerSearch.trim().toLocaleLowerCase();
    return workers.filter((worker) => {
      if (!matchesWorkerRoles(worker.tags ?? [], workerRoleFilters)) return false;
      if (!query) return true;
      const roles = (worker.tags ?? []).map((code) => workerRoles.find((role) => role.code === code)?.label ?? code).join(" ");
      return [worker.name, worker.furigana ?? "", roles].some((text) => text.toLocaleLowerCase().includes(query));
    });
  }, [workerSearch, workerRoleFilters, workerRoles, workers]);
  const selectedWorkers = workers.filter((worker) => form.worker_ids.includes(worker.id));
  const workDates = useMemo(() => scheduleWorkDates(sections.schedule), [sections.schedule]);
  const absenceWorker = selectedWorkers.find((worker) => worker.id === absenceWorkerId) ?? null;

  const detail = creating ? null : detailQuery.data;
  const editable = creating || detail?.status === "draft";

  function formFromVersion(version: OrderRequestVersion): OrderRequestWrite {
    return {
      internal_source: version.internal_source ?? null,
      kind: version.kind,
      work_date_label: version.work_date_label,
      site_id: version.site_id,
      site_name: version.site_name,
      site_address: version.site_address,
      request_conditions: version.request_conditions,
      body: version.body,
      contact_name: version.contact_name || version.contact_desk,
      contact_desk: "",
      counterparty_note: version.counterparty_note ?? "",
      worker_ids: version.draft_worker_ids,
      recipient_absences: version.draft_recipient_absences ?? {},
      allow_partial_accept: Boolean(version.allow_partial_accept),
      phone_first: version.phone_first,
      phone_note: version.phone_note ?? "",
      tracker_user_id: version.tracker_user_id,
      follow_up_due_on: version.follow_up_due_on,
      follow_up_due_time: version.follow_up_due_time || "21:00",
      assign_tracker_self: Boolean(version.tracker_user_id),
    };
  }

  function draftPayload(): OrderRequestWrite {
    const current = withScheduleDateLabel(formRef.current, sectionsRef.current);
    const currentSections = sectionsRef.current;
    const phoneNote = current.phone_note?.trim() ? current.phone_note : null;
    return {
      ...current,
      internal_source: current.internal_source ? { client_id: current.internal_source.client_id, client_staff_id: current.internal_source.client_staff_id } : null,
      request_conditions: serializeOrderSections(currentSections),
      body: composeOrderDocument(currentSections, current.work_date_label, current.site_name, current.site_address ?? ""),
      // 担当者がいない依頼もあるため、空欄は「なし」として送る
      contact_name: current.contact_name.trim() || CONTACT_NONE,
      contact_desk: "",
      counterparty_note: current.counterparty_note || null,
      phone_first: Boolean(current.phone_first),
      assign_tracker_self: undefined,
      tracker_user_id: undefined,
      phone_note: phoneNote,
      site_address: current.site_address || null,
      follow_up_due_on: current.follow_up_due_on || null,
      follow_up_due_time: current.follow_up_due_time || "21:00",
      recipient_absences: currentAbsences(current, currentSections),
    };
  }

  function pinSavedVersion(version: OrderRequestVersion) {
    loadedForRef.current = version.id;
    queryClient.setQueryData(["order-request", version.id], version);
  }

  function rememberSavedVersion(version: OrderRequestVersion) {
    pinSavedVersion(version);
    const nextForm = formFromVersion(version);
    const nextSections = sectionsFromStored(version.request_conditions, version.body);
    formRef.current = nextForm;
    sectionsRef.current = nextSections;
    setForm(nextForm);
    setSections(nextSections);
  }

  function dueMissing(): boolean {
    if (formRef.current.follow_up_due_on) return false;
    setActionError("期限の案内の日付を入れてください");
    return true;
  }

  useEffect(() => {
    if (!detail || creating) return;
    if (loadedForRef.current === detail.id) return;
    loadedForRef.current = detail.id;
    const nextForm = formFromVersion(detail);
    const nextSections = sectionsFromStored(detail.request_conditions, detail.body);
    formRef.current = nextForm;
    sectionsRef.current = nextSections;
    setForm(nextForm);
    setSections(nextSections);
  }, [creating, detail]);

  useEffect(() => {
    if (!linePreviewOpen) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setLinePreviewOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [linePreviewOpen]);

  const createModal = creating || Boolean(selectedId);

  useEffect(() => {
    if (!createModal) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => {
      draftRef.current?.focus();
    });
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.key !== "Escape" || linePreviewOpenRef.current || pdfReviewRef.current) return;
      setCreating(false);
      setBasedOn(null);
      setSelectedId(null);
      setSavedDraftId(null);
      setActionError("");
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.cancelAnimationFrame(frame);
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKey);
    };
  }, [createModal]);

  const previewDocumentNumber = detail?.document_number ?? "未採番";
  const previewVersionNo = detail?.version_no ?? 1;
  const previewLineText = linePushPreviewText({
    documentNumber: previewDocumentNumber,
    versionNo: previewVersionNo,
    projectName: sections.projectName,
    workDateLabel: form.work_date_label,
    siteName: form.site_name,
    isTest: form.kind === "test",
  });
  const previewProjectCut = `案件名: ${withFullwidthTilde(sections.projectName)}`.length > 80;
  const previewDateCut = `稼働日: ${withFullwidthTilde(form.work_date_label)}`.length > 80;
  const previewSiteCut = `現場: ${withFullwidthTilde(form.site_name)}`.length > 80;
  const previewDocument = composeOrderDocument(sections, form.work_date_label, form.site_name, form.site_address ?? "");
  const pdfNotice = !creating && detail?.status === "cancelled"
    ? "cancel"
    : (basedOn || detail?.based_on_document_number)
      ? "change"
      : "new";
  const parsedWorkDates = parseWorkDateRange(form.work_date_label);
  const storedWorkDates = sections.schedule?.work_groups.flatMap((group) => [group.from, group.to]).filter(Boolean).sort() ?? [];
  const workDateFrom = sections.workPeriod?.from ?? parsedWorkDates?.from ?? storedWorkDates[0] ?? "";
  const workDateTo = sections.workPeriod?.to ?? parsedWorkDates?.to ?? storedWorkDates[storedWorkDates.length - 1] ?? "";
  const legacyWorkDate = sections.workPeriod || parsedWorkDates || !form.work_date_label.trim() ? "" : form.work_date_label;

  const holidays = sectionHolidays(sections);
  const holidaySingleConflicts = sections.schedule ? singleDaysOnHolidays(sections.schedule, holidays) : [];

  function setWorkDateBound(bound: "from" | "to", value: string) {
    const from = bound === "from" ? value : workDateFrom;
    const to = bound === "to" ? value : workDateTo;
    // 休業日は残す（期間外になった日は休業日の欄で知らせて外せるようにする）
    setSections({ ...sections, workPeriod: { ...(sections.workPeriod ?? {}), from, to } });
    setForm({ ...form, work_date_label: formatWorkDateRange(from, to) });
  }
  function changeSchedule(schedule: OrderSchedule) {
    let next = syncSchedule(schedule);
    // 全体の休業日を、稼働日の詳細（期間）に配り直す
    if (sections.workPeriod?.excluded_dates) next = applyPeriodHolidays(next, sections.workPeriod.excluded_dates);
    setSections({ ...sections, schedule: next });
  }
  function changeHolidays(dates: string[]) {
    const workPeriod = { from: workDateFrom, to: workDateTo, ...(sections.workPeriod ?? {}), excluded_dates: dates };
    setSections({ ...sections, workPeriod, schedule: sections.schedule ? applyPeriodHolidays(sections.schedule, dates) : sections.schedule });
  }
  async function enableSchedule() {
    const accepted = await confirmApp({ title: "日付・期間ごとの入力", message: "勤務時間・単価を日付別の入力に切り替えます。既存の文面は参考として残し、依頼書は新しい日付別の入力から作成します。", confirmLabel: "切り替える" });
    if (!accepted) return;
    switchToSchedule();
  }
  function switchToSchedule() {
    const first = newWorkGroup();
    if (parsedWorkDates?.from) {
      first.from = parsedWorkDates.from;
      first.to = parsedWorkDates.to || first.from;
      first.date_mode = parsedWorkDates.to ? "range" : "single";
    }
    setSections({ ...sections, previousHours: sections.hours, previousFee: sections.fee, schedule: syncSchedule({ ...emptySchedule(), work_groups: [first] }) });
    setForm({ ...form, work_date_label: scheduleDateLabel({ ...emptySchedule(), work_groups: [first] }) });
  }
  const previewPdfBody = previewDocument.startsWith(ORDER_DOCUMENT_TITLE)
    ? previewDocument.slice(ORDER_DOCUMENT_TITLE.length).replace(/^\n+/, "")
    : previewDocument;

  function refresh() {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["order-requests"] }),
      queryClient.invalidateQueries({ queryKey: ["order-request-replies"] }),
    ]);
  }

  function showDetail(versionId: string) {
    if (creating || selectedId !== versionId) loadedForRef.current = null;
    setCreating(false);
    setBasedOn(null);
    setSelectedId(versionId);
    setActionError("");
    setActionMessage("");
    setReason("");
    setNote("");
    setSavedDraftId(null);
  }

  function startNewDraft() {
    loadedForRef.current = null;
    formRef.current = EMPTY_FORM;
    const initialSections = { ...EMPTY_ORDER_SECTIONS, workPeriod: { from: "", to: "" }, schedule: syncSchedule({ ...emptySchedule(), work_groups: [newWorkGroup()] }) };
    sectionsRef.current = initialSections;
    setCreating(true);
    setBasedOn(null);
    setSelectedId(null);
    setForm(EMPTY_FORM);
    setSections(initialSections);
    setWorkerSearch("");
    setWorkerRoleFilters([]);
    setActionError("");
    setActionMessage("");
    setReason("");
    setNote("");
    setSavedDraftId(null);
  }

  function openTemplateSave(id: string, label: string) {
    setSaveTemplateFor({ id, label });
    setTemplateName(label.split("\n")[0].trim().slice(0, 100));
    setTemplateError("");
  }

  async function saveTemplate() {
    if (!saveTemplateFor || !templateName.trim() || templateSaving) return;
    setTemplateSaving(true); setTemplateError("");
    try {
      const saved = await saveOrderRequestTemplate({ name: templateName.trim(), source_version_id: saveTemplateFor.id });
      setSaveTemplateFor(null);
      setActionMessage(`「${saved.name}」をテンプレートに保存しました。新規作成時に「テンプレートから呼び出す」で利用できます。`);
      await queryClient.invalidateQueries({ queryKey: ["order-request-templates"] });
    } catch (error) { setTemplateError(messageOf(error)); }
    finally { setTemplateSaving(false); }
  }

  async function useTemplate(id: string): Promise<boolean> {
    if (createModal && (sections.projectName.trim() || form.site_name.trim())) {
      if (!(await confirmApp({ title: "テンプレートを呼び出す", message: "入力中の内容をテンプレートの内容に置き換えます。保存済みの依頼書はそのまま残ります。", confirmLabel: "呼び出す" }))) return false;
    }
    const template = await getOrderRequestTemplate(id);
    const nextForm = { ...EMPTY_FORM, ...template.payload };
    const stored = sectionsFromStored(nextForm.request_conditions, nextForm.body);
    const nextSections = { ...stored, schedule: stored.schedule ? syncSchedule(stored.schedule) : syncSchedule({ ...emptySchedule(), work_groups: [newWorkGroup()] }) };
    loadedForRef.current = null;
    setCreating(true); setSelectedId(null); setSavedDraftId(null); setBasedOn(null);
    formRef.current = nextForm; sectionsRef.current = nextSections;
    setForm(nextForm); setSections(nextSections);
    setWorkerSearch(""); setWorkerRoleFilters([]); setReason(""); setNote(""); setActionError("");
    setActionMessage(`「${template.name}」から新規作成しています。稼働日・休業日・期限・送付先を設定し、時刻・単価も今回の内容で確認してください。`);
    return true;
  }

  /** 送信が済んだあと、依頼書の画面を閉じるかを確かめる。 */
  async function offerCloseAfterSend(sentCount: number) {
    const close = await confirmApp({
      title: "送信しました",
      message: `${sentCount}人へ送信しました。返事は本人が公式LINEで受諾するか、辞退理由を送ったときに一覧へ反映されます。画面を閉じますか？`,
      confirmLabel: "閉じる",
      cancelLabel: "このまま表示",
    });
    if (close) closeCreateModal();
  }

  function closeCreateModal() {
    setCreating(false);
    setBasedOn(null);
    setSelectedId(null);
    setSavedDraftId(null);
    setActionError("");
  }

  async function hideDocument(documentId: string) {
    const confirmed = await confirmApp({
      title: "依頼書を一覧から外す",
      message: "この依頼書を一覧から外します。データは残し、管理者の削除済み案件一覧にだけ表示します。",
      confirmLabel: "一覧から外す",
    });
    if (!confirmed) return;
    setActionError("");
    try {
      await hideOrderRequest(documentId);
      if (detail?.document_id === documentId) closeCreateModal();
      setActionMessage("一覧から外しました。削除済み案件一覧で確認できます。");
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["order-requests-deleted"] });
    } catch (error) {
      setActionError(messageOf(error));
    }
  }

  async function startChange(versionId: string) {
    setChangeLoading(true);
    setActionError("");
    setActionMessage("");
    try {
      const version = await getOrderRequestVersion(versionId);
      const workerIds = version.deliveries.length > 0
        ? version.deliveries.map((row) => row.worker_id)
        : version.draft_worker_ids;
      loadedForRef.current = null;
      setCreating(true);
      setSelectedId(null);
      setSavedDraftId(null);
      setBasedOn({
        versionId: version.id,
        documentNumber: version.document_number,
        versionNo: version.version_no,
      });
      const nextForm = {
        ...formFromVersion(version),
        worker_ids: workerIds,
        phone_first: false,
        phone_note: "",
      };
      const stored = sectionsFromStored(version.request_conditions, version.body);
      // 古い形式（文章の稼働時間）の依頼書を基にするときは、確定できるよう日付・期間ごとの入力に切り替えて作る
      const legacyDates = stored.schedule ? null : parseWorkDateRange(version.work_date_label);
      const firstGroup = newWorkGroup();
      if (legacyDates?.from) {
        firstGroup.from = legacyDates.from;
        firstGroup.to = legacyDates.to || legacyDates.from;
        firstGroup.date_mode = legacyDates.to && legacyDates.to !== legacyDates.from ? "range" : "single";
      }
      const nextSections: OrderDocumentSections = stored.schedule
        ? stored
        : { ...stored, previousHours: stored.hours, previousFee: stored.fee, schedule: syncSchedule({ ...emptySchedule(), work_groups: [firstGroup] }) };
      formRef.current = nextForm;
      sectionsRef.current = nextSections;
      setForm(nextForm);
      setSections(nextSections);
      setReason("");
      setNote("");
      if (!stored.schedule) {
        setActionMessage("基にした依頼書は稼働時間が文章の入力でした。日付・期間ごとの入力に切り替えて作成しています。日付・時刻・単価を確認してください（元の文面は「切替前の勤務時間・単価（参考）」にあります）。");
      }
    } catch (error) {
      setActionError(messageOf(error));
    } finally {
      setChangeLoading(false);
    }
  }

  /**
   * 同じイベントを別日に行うときの複製。元の依頼書とは別の新しい依頼書（別の系列）として作る。
   * 「変更を作成」と違い、元の依頼書の受諾・稼働予定には影響しない。日付と日付に関わる入力は空にする。
   */
  async function startCopy(versionId: string) {
    setChangeLoading(true);
    setActionError("");
    setActionMessage("");
    try {
      const version = await getOrderRequestVersion(versionId);
      const workerIds = version.deliveries.length > 0
        ? version.deliveries.map((row) => row.worker_id)
        : version.draft_worker_ids;
      const stored = sectionsFromStored(version.request_conditions, version.body);
      const schedule = stored.schedule
        ? syncSchedule({
          ...stored.schedule,
          // 時刻・単価は残し、日付だけ空にする（単価は勤務グループのIDで対応を保つ）
          work_groups: stored.schedule.work_groups.map((group) => ({ ...group, from: "", to: "", excluded_dates: [] })),
          rate_groups: stored.schedule.rate_groups.map((rate) => ({ ...rate, from: "", to: "" })),
        })
        : syncSchedule({ ...emptySchedule(), work_groups: [newWorkGroup()] });
      const nextSections: OrderDocumentSections = {
        ...stored,
        workPeriod: { from: "", to: "" },
        workDateDetail: "",
        schedule,
        ...(stored.schedule ? {} : { previousHours: stored.hours, previousFee: stored.fee }),
      };
      const nextForm: OrderRequestWrite = {
        ...formFromVersion(version),
        work_date_label: "",
        worker_ids: workerIds,
        recipient_absences: {},
        phone_first: false,
        phone_note: "",
        follow_up_due_on: null,
      };
      loadedForRef.current = null;
      setCreating(true);
      setSelectedId(null);
      setSavedDraftId(null);
      setBasedOn(null);
      formRef.current = nextForm;
      sectionsRef.current = nextSections;
      setForm(nextForm);
      setSections(nextSections);
      setReason("");
      setNote("");
      setActionMessage(`${version.document_number} の内容を写した新しい依頼書です。稼働日・稼働時間の詳細の日付・期限の案内を入れてください。元の依頼書と受諾・予定は別々に扱います。`);
    } catch (error) {
      setActionError(messageOf(error));
    } finally {
      setChangeLoading(false);
    }
  }

  function loadFormFromDetail() {
    if (!detail) return;
    setForm(formFromVersion(detail));
    setSections(sectionsFromStored(detail.request_conditions, detail.body));
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (dueMissing()) throw new Error("期限の案内の日付を入れてください");
      const payload = draftPayload();
      if (creating) {
        return createOrderRequest(
          basedOn ? { ...payload, based_on_version_id: basedOn.versionId } : payload,
        );
      }
      if (!detail) throw new Error("版が選ばれていません");
      return updateOrderRequestVersion(detail.id, payload);
    },
    onSuccess: async (version) => {
      rememberSavedVersion(version);
      setCreating(false);
      setBasedOn(null);
      setSelectedId(version.id);
      setActionMessage(
        version.based_on_document_number
          ? `${version.based_on_document_number} を基にした下書きを保存しました。確定するまで送付は始まりません。`
          : "下書きを保存しました。確定するまで送付は始まりません。",
      );
      setActionError("");
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["order-request", version.id] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const confirmMutation = useMutation({
    mutationFn: (versionId: string) => confirmOrderRequest(versionId),
    onSuccess: async (version) => {
      setActionMessage("確定しました。紐付け済みの送付先へ送れます。本人紐付けは稼働者登録・一覧で行います。");
      setActionError("");
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["order-request", version.id] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const reviseMutation = useMutation({
    mutationFn: (versionId: string) => reviseOrderRequest(versionId, reason),
    onSuccess: async (version) => {
      setSelectedId(version.id);
      setReason("");
      setActionMessage("新しい下書き版を作りました。古い版の内容と受領予定はそのままです。");
      await refresh();
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const cancelMutation = useMutation({
    mutationFn: (versionId: string) => cancelOrderRequest(versionId, reason),
    onSuccess: async (version) => {
      setActionMessage("取消しました。未送信の送付は止めています。");
      setReason("");
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["order-request", version.id] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const noteMutation = useMutation({
    mutationFn: (versionId: string) => addOrderRequestNote(versionId, note),
    onSuccess: async (version) => {
      setNote("");
      setActionMessage("メモを残しました。送付済み・受領済みにはしていません。");
      await queryClient.invalidateQueries({ queryKey: ["order-request", version.id] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const layoutPending = listQuery.data ? !listQuery.data.template_layout_applied : true;
  const lineReady = Boolean(listQuery.data?.line_send_available || detail?.line_send_available);

  const sendLine = useMutation({
    mutationFn: (deliveryId: string) => sendOrderRequestLine(deliveryId),
    onSuccess: async (version) => {
      setActionMessage("送信を受け付けました。返事は本人が受諾するか、辞退理由を送ったときだけです。");
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["order-request", version.id] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const withdrawAcceptance = useMutation({
    mutationFn: (input: { documentId: string; workerId: string; reason: string }) =>
      withdrawOrderRequestAcceptance(input.documentId, input.workerId, input.reason),
    onSuccess: async (result) => {
      setActionMessage(
        result.removed_dates.length > 0
          ? `今後の参加を終了しました。取り消した日：${compactDateList(result.removed_dates)}${result.kept_dates.length > 0 ? `／残した日（勤務が始まっていた日）：${compactDateList(result.kept_dates)}` : ""}。公式LINEの予定にも反映されます。`
          : "取り消す日がないため、記録しませんでした（参加日はすべて勤務が始まっています）。",
      );
      await refresh();
      if (detail) await queryClient.invalidateQueries({ queryKey: ["order-request", detail.id] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  async function recordWithdrawal(row: OrderRequestDelivery) {
    if (!detail) return;
    const preview = row.end_preview;
    const removed = preview?.removed_dates ?? [];
    const kept = preview?.kept_dates ?? [];
    const lines = [
      `${row.worker_name_snapshot}さんの、この依頼書での今後の参加を終了します（受諾後の辞退の記録。ほかの送付先は変わりません）。`,
      removed.length > 0 ? `取り消す日：${compactDateList(removed)}` : "",
      preview?.today_removed_start ? `※本日 ${preview.today_removed_start} 開始の勤務も取り消されます。` : "",
      kept.length > 0 ? `残す日（記録の時点で勤務が始まっている日）：${compactDateList(kept)}` : "",
      "理由を入力してください。",
    ].filter(Boolean);
    const reason = await promptApp({
      title: "今後の参加を終了",
      message: lines.join("\n"),
      confirmLabel: "参加を終了",
    });
    const trimmed = (reason ?? "").trim();
    if (!trimmed) return;
    setActionError("");
    withdrawAcceptance.mutate({ documentId: detail.document_id, workerId: row.worker_id, reason: trimmed });
  }

  const detailSourceNote = detail
    ? basedOnNote(detail.document_number, detail.based_on_document_number, detail.based_on_version_no)
    : null;
  const detailLead = creating
    ? basedOn
      ? `${basedOn.documentNumber} 第${basedOn.versionNo}版を基に、新しい依頼書を作成します。確定するまで送付は始まりません。`
      : "案件依頼の項目で下書きします。確定するまで送付は始まりません。"
    : [detailSourceNote, detail ? STATUS_LABEL[detail.status] : "", detail?.created_by_name].filter(Boolean).join(" · ");

  const canSend = Boolean(
    detail
    && detail.status === "confirmed"
    && !detail.dispatch_stopped
    && detail.deliveries.length > 0,
  );

  async function sendToLinkedRecipients() {
    if (!detail) return;
    const targets = detail.deliveries.filter((row) => (
      row.line_linked
      && !row.view_revoked
      && row.ack_status === "unacked"
    ));
    if (targets.length === 0) {
      setActionError("送れる紐付け済みの送付先がありません。稼働者登録・一覧で本人紐付けをしてください。");
      return;
    }
    setSendingSelected(true);
    setActionError("");
    const failed: string[] = [];
    for (const row of targets) {
      try {
        await sendOrderRequestLine(row.id);
      } catch (error) {
        failed.push(`${row.worker_name_snapshot}: ${messageOf(error)}`);
      }
    }
    setSendingSelected(false);
    await refresh();
    await queryClient.invalidateQueries({ queryKey: ["order-request", detail.id] });
    if (failed.length > 0) {
      setActionError(failed.join(" / "));
      setActionMessage(`${targets.length - failed.length}人へ送信しました。`);
    } else {
      setActionMessage(`${targets.length}人へ送信しました。返事は本人が受諾するか、辞退理由を送ったときだけです。`);
      await offerCloseAfterSend(targets.length);
    }
  }

  function missingSendFields(): string[] {
    const missing: string[] = [];
    if (!sections.projectName.trim()) missing.push("案件名");
    if (sections.categories.length === 0) missing.push("カテゴリ");
    if (!withScheduleDateLabel(form, sections).work_date_label.trim()) missing.push("稼働日");
    if (!form.site_name.trim()) missing.push("稼働場所");
    if (!form.follow_up_due_on) missing.push("期限の案内");
    if (form.worker_ids.length === 0) missing.push("送付先");
    if (form.worker_ids.length > MAX_ORDER_RECIPIENTS) missing.push(`送付先は${MAX_ORDER_RECIPIENTS}人まで`);
    return missing;
  }

  async function persistCurrentDraft() {
    const payload = draftPayload();
    const existingId = savedDraftId ?? (!creating && detail ? detail.id : null);
    if (existingId) return updateOrderRequestVersion(existingId, payload);
    return createOrderRequest(
      basedOn ? { ...payload, based_on_version_id: basedOn.versionId } : payload,
    );
  }

  function dismissPdfReview(nextSelectedId: string | null) {
    setPdfReview((current) => {
      if (current?.url) URL.revokeObjectURL(current.url);
      return null;
    });
    setPdfReviewError("");
    setCreating(false);
    setBasedOn(null);
    setSavedDraftId(null);
    setSelectedId(nextSelectedId);
  }

  /** 日付・期間ごとの入力がない依頼書は、受諾しても稼働予定（公式LINEの予定・起床報告）が作られない（DEC-063）。 */
  async function acceptWithoutSchedule(): Promise<boolean> {
    if (sections.schedule) return true;
    // 文章の稼働時間では確定できない（DEC-069）。切り替えてもらう。
    const switchNow = await confirmApp({
      title: "日付・期間ごとの入力が必要です",
      message: "この依頼書は稼働時間を文章で入力しています。文章のままでは受諾しても公式LINEの予定・起床報告に載らないため、確定できません。「切り替える」を押すと日付・期間ごとの入力に切り替わります（今の文面は参考として残ります）。日付と時刻を確認してから、もう一度送付してください。",
      confirmLabel: "切り替える",
      cancelLabel: "閉じる",
    });
    if (switchNow) switchToSchedule();
    return false;
  }

  async function openPdfReview() {
    if (!(await acceptWithoutSchedule())) return;
    const missing = missingSendFields();
    if (missing.length > 0) {
      setActionError(`送付前に入力してください: ${missing.join("、")}`);
      return;
    }
    setActionError("");
    setPdfReviewError("");
    setPdfReview({ phase: "loading", versionId: null, url: null });
    try {
      const saved = await persistCurrentDraft();
      pinSavedVersion(saved);
      setSavedDraftId(saved.id);
      const blob = await fetchOrderRequestPdfPreview(saved.id);
      const pdfBlob = blob.type === "application/pdf" ? blob : new Blob([await blob.arrayBuffer()], { type: "application/pdf" });
      const url = URL.createObjectURL(pdfBlob);
      setPdfReview({ phase: "ready", versionId: saved.id, url });
      await refresh();
    } catch (error) {
      setPdfReview(null);
      setActionError(messageOf(error));
    }
  }

  function returnToEditing() {
    if (pdfReview?.url) URL.revokeObjectURL(pdfReview.url);
    setPdfReview(null);
    setPdfReviewError("");
    window.requestAnimationFrame(() => draftRef.current?.focus());
  }

  async function sendReviewedOrder() {
    if (!pdfReview?.versionId) return;
    setPdfSending(true);
    setPdfReviewError("");
    try {
      const links = await listLineLinks();
      if (!links.line_send_available) {
        setPdfReviewError("送信には、サーバーへのチャネル設定がまだ必要です。");
        return;
      }
      const linked = new Set(links.items.map((item) => item.worker_id));
      if (!form.worker_ids.some((id) => linked.has(id))) {
        setPdfReviewError("選んだ送付先に、公式LINEと紐付いた人がいません。稼働者登録・一覧で本人紐付けを確認してください。");
        return;
      }
      const confirmed = await confirmOrderRequest(pdfReview.versionId);
      const targets = confirmed.deliveries.filter((row) => (
        row.line_linked && !row.view_revoked && row.ack_status === "unacked"
      ));
      const failed: string[] = [];
      for (const row of targets) {
        try {
          await sendOrderRequestLine(row.id);
        } catch (error) {
          failed.push(`${row.worker_name_snapshot}: ${messageOf(error)}`);
        }
      }
      const sentCount = targets.length - failed.length;
      dismissPdfReview(confirmed.id);
      if (targets.length === 0) {
        setActionError("送れる紐付け済みの送付先がありません。稼働者登録・一覧で本人紐付けを確認してください。");
      } else if (failed.length > 0) {
        setActionError(failed.join(" / "));
        if (sentCount > 0) setActionMessage(`${sentCount}人へ送信しました。`);
      } else {
        setActionMessage(`${sentCount}人へ送信しました。返事は本人が受諾するか、辞退理由を送ったときだけです。`);
      }
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["order-request", confirmed.id] });
      if (targets.length > 0 && failed.length === 0) await offerCloseAfterSend(sentCount);
    } catch (error) {
      setPdfReviewError(messageOf(error));
    } finally {
      setPdfSending(false);
    }
  }

  return (
    <section>
      {templatesOpen ? <OrderRequestTemplatesDialog onClose={() => setTemplatesOpen(false)} onUse={useTemplate} canWrite={canWrite} /> : null}
      <FormDialog open={saveTemplateFor !== null} title="テンプレートとして保存" size="compact" busy={templateSaving} onClose={() => setSaveTemplateFor(null)}>
        <p>保存済みの依頼書「{saveTemplateFor?.label}」の内容を再利用できるようにします。日付・休業日・期限・送付先・送付状況は引き継ぎません。</p>
        <label className="order-field"><span className="order-field-label">テンプレート名</span>
          <input autoFocus value={templateName} maxLength={100} disabled={templateSaving} onChange={(event) => setTemplateName(event.target.value)} />
        </label>
        {templateError ? <p className="form-error" role="alert">{templateError}</p> : null}
        <button type="button" className="btn btn-primary create-button" disabled={templateSaving || !templateName.trim()} onClick={() => void saveTemplate()}>{templateSaving ? "保存しています…" : "テンプレートを保存"}</button>
      </FormDialog>
      <FormDialog
        open={participationFor !== null}
        title={participationFor ? `参加人数の確認：${participationFor.title}` : ""}
        size="compact"
        onClose={() => setParticipationFor(null)}
      >
        {participationFor ? <VersionParticipationSummary versionId={participationFor.versionId} /> : null}
      </FormDialog>
      <PageHeader
        eyebrow="発注依頼"
        title="発注依頼書"
        description="誰が、誰に、どの版を確定したかを担当者間で共有します。返事は本人の受諾か辞退だけです。"
        titleAction={(
          <div className="order-template-actions">
          <button type="button" className="btn btn-primary create-button" onClick={startNewDraft}>
            新規の依頼書を作成
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => setTemplatesOpen(true)}>保存済みテンプレート</button>
          </div>
        )}
      />
      <p className="card" style={{ padding: "0.9rem 1rem" }}>
        {layoutPending
          ? "弁護士確認済み書式のレイアウトは未適用です。いまのPDFは入力内容の保存です。"
          : "正式区分の書式を適用しています。"}
        {lineReady
          ? " 確定後、選んだ送付先のうち公式LINEと紐付いた人へ送れます。紐付けは稼働者登録・一覧で行います。"
          : " 送信には、サーバーへのチャネル設定がまだ必要です。紐付けは稼働者登録・一覧で行います。"}
      </p>

      {!createModal && actionError ? <ErrorState title="処理できませんでした" description={actionError} /> : null}
      {!createModal && actionMessage ? <p>{actionMessage}</p> : null}
      {listQuery.isLoading ? <LoadingOverlay /> : null}
      {listQuery.isError ? <ErrorState title="一覧を取得できませんでした" description={messageOf(listQuery.error)} /> : null}

      <section className="order-list-frame is-sent">
        <h3>送信した依頼</h3>
        <p className="order-list-lead">送付先ごとの返事です。日付は稼働日です。内容を変えるときは「変更を作成」（元の依頼書の受諾・予定を置き換えます）、同じイベントを別の日に行うときは「別日で新規作成」（元の依頼書には影響しません）を使います。</p>
        <div className="order-list-table">
          <table className="data-table">
            <thead>
              <tr>
                <th>文書番号</th>
                <th>案件名</th>
                <th>カテゴリ</th>
                <th>日付</th>
                <th>送付先</th>
                <th>返事</th>
                <th>変更</th>
              </tr>
            </thead>
            <tbody>
              {(repliesQuery.data?.items ?? []).map((row) => (
                <tr key={row.delivery_id}>
                  <td>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => showDetail(row.version_id)}>
                      {row.document_number}
                    </button>
                    {basedOnNote(row.document_number, row.based_on_document_number, row.based_on_version_no) ? (
                      <span className="order-change-note">
                        {basedOnNote(row.document_number, row.based_on_document_number, row.based_on_version_no)}
                      </span>
                    ) : null}
                  </td>
                  <td className="order-cell-multiline">{siteLabelForList(row.project_name)}</td>
                  <td className="order-cell-multiline">{categoryLabelForList(row.categories)}</td>
                  <td className="order-cell-multiline">{row.work_date_label}</td>
                  <td>{row.worker_name}</td>
                  <td>
                    {REPLY_LABEL[row.ack_status] ?? row.ack_status}
                    {row.decline_reason ? <div className="order-cell-multiline">{row.decline_reason}</div> : null}
                  </td>
                  <td>
                    <div className="order-row-actions">
                      {(row.change_documents ?? []).length > 0 ? null : (
                        <button
                          type="button"
                          className="btn btn-line-blue btn-sm"
                          disabled={changeLoading}
                          onClick={() => startChange(row.version_id)}
                        >
                          変更を作成
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn btn-line-green btn-sm"
                        disabled={changeLoading}
                        onClick={() => void startCopy(row.version_id)}
                      >
                        別日で新規作成
                      </button>
                      {(row.change_documents ?? []).map((change) => (
                        <button
                          key={change.version_id}
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => showDetail(change.version_id)}
                        >
                          {changeLinkLabel(row.document_number, change)}
                        </button>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {repliesQuery.data && repliesQuery.data.items.length === 0 ? (
            <EmptyState title="送信済みはありません" description="送付先へ送った依頼がここに出ます。" />
          ) : null}
        </div>
      </section>

      <section className="order-list-frame is-created">
        <h3>作成した依頼書</h3>
        <p className="order-list-lead">下書きと確定した版です。追跡は、返事を追う担当者の名前です。作成済みの依頼書から、「変更を作成」（元の依頼書を置き換える）か「別日で新規作成」（元の依頼書とは別に扱う）で、内容を写した新しい依頼書を作れます。</p>
        <div className="order-list-filters">
          <label>
            区分
            <select value={kind} onChange={(event) => setKind(event.target.value as OrderRequestKind | "all")}>
              <option value="formal">正式</option>
              <option value="test">テスト</option>
              <option value="all">すべて</option>
            </select>
          </label>
          <label>
            一覧
            <select value={queue} onChange={(event) => setQueue(event.target.value as OrderRequestQueue)}>
              <option value="all">最新版</option>
              <option value="unsent">未送付</option>
              <option value="unknown">結果不明</option>
              <option value="unacked">未受領</option>
              <option value="overdue">期限超過</option>
            </select>
          </label>
        </div>
        <div className="order-list-table">
        <table className="data-table order-created-table">
          <thead>
            <tr>
              <th>文書番号</th>
              <th>案件名</th>
              <th>版</th>
              <th>状態</th>
              <th>カテゴリ</th>
              <th>日付</th>
              <th>作成者</th>
              <th>送付先</th>
              <th>期限</th>
              <th>変更</th>
            </tr>
          </thead>
          <tbody>
            {(listQuery.data?.items ?? []).map((item) => (
              <tr key={item.version_id}>
                <td>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => showDetail(item.version_id)}>
                    {item.document_number}
                  </button>
                  {item.status !== "draft" ? (
                    <button
                      type="button"
                      className="btn btn-line-blue btn-sm order-participation-button"
                      onClick={() => setParticipationFor({ versionId: item.version_id, title: `${item.document_number}（${item.project_name || "案件"}）` })}
                    >
                      参加人数の確認
                    </button>
                  ) : null}
                  {basedOnNote(item.document_number, item.based_on_document_number, item.based_on_version_no) ? (
                    <span className="order-change-note">
                      {basedOnNote(item.document_number, item.based_on_document_number, item.based_on_version_no)}
                    </span>
                  ) : null}
                </td>
                <td className="order-cell-multiline">{siteLabelForList(item.project_name)}</td>
                <td>{item.version_no}</td>
                <td>
                  {STATUS_LABEL[item.status]}
                  {item.phone_first ? " / 電話先行" : ""}
                  {item.dispatch_stopped ? " / 送付停止" : ""}
                </td>
                <td className="order-cell-category">{categoryLabelForList(item.categories)}</td>
                <td className="order-cell-multiline">{item.work_date_label}</td>
                <td>{item.created_by_name}</td>
                <td>{item.recipient_count}</td>
                <td>{item.follow_up_due_on ? `${item.follow_up_due_on} ${item.follow_up_due_time || "21:00"}` : "—"}</td>
                <td>
                  <div className="order-row-actions">
                    {(item.change_documents ?? []).length > 0 ? null : (
                      <button
                        type="button"
                        className="btn btn-line-blue btn-sm"
                        disabled={changeLoading}
                        onClick={() => startChange(item.version_id)}
                      >
                        変更を作成
                      </button>
                    )}
                    {canWrite ? <button type="button" className="btn create-button btn-sm" onClick={() => openTemplateSave(item.version_id, item.project_name || item.document_number)}>テンプレートとして保存</button> : null}
                    <button
                      type="button"
                      className="btn btn-line-green btn-sm"
                      disabled={changeLoading}
                      onClick={() => void startCopy(item.version_id)}
                    >
                      別日で新規作成
                    </button>
                    {(item.change_documents ?? []).map((change) => (
                      <button
                        key={change.version_id}
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => showDetail(change.version_id)}
                      >
                        {changeLinkLabel(item.document_number, change)}
                      </button>
                    ))}
                    {isAdmin ? (
                      <button
                        type="button"
                        className="btn btn-line-red btn-sm"
                        onClick={() => {
                          void hideDocument(item.document_id);
                        }}
                      >
                        削除
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {listQuery.data && listQuery.data.items.length === 0 ? (
          <EmptyState title="該当なし" description="この条件の発注依頼書はありません" />
        ) : null}
        </div>
      </section>

      {detailQuery.isLoading ? <LoadingOverlay /> : null}

      {(creating || selectedId) && (
        <div className="order-create-backdrop">
        {creating || detail ? (
        <form
          ref={draftRef}
          className="order-draft is-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="order-draft-title"
          tabIndex={-1}
          onSubmit={(event) => {
            event.preventDefault();
            if (editable) {
              setActionError("");
              if (dueMissing()) return;
              saveMutation.mutate();
            }
          }}
        >
          <header className="order-draft-head">
            <div className="order-draft-head-lead">
              <p className="order-draft-kicker">
                {creating
                  ? (basedOn ? `${basedOn.documentNumber} の変更` : "発注依頼書")
                  : detail?.document_number}
              </p>
              <h3 id="order-draft-title">{creating ? (basedOn ? "変更の下書き" : "新規の下書き") : `第${detail?.version_no}版`}</h3>
              <p className="order-draft-lead">{detailLead}</p>
              {!creating && detail && detail.change_documents.length > 0 ? (
                <div className="order-row-actions">
                  {detail.change_documents.map((change) => (
                    <button
                      key={change.version_id}
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => showDetail(change.version_id)}
                    >
                      {changeLinkLabel(detail.document_number, change)}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="order-draft-head-side">
              {creating && !basedOn && !savedDraftId && canWrite ? <button type="button" className="btn btn-line-blue" onClick={() => setTemplatesOpen(true)}>テンプレートから呼び出す</button> : null}
              {createModal ? (
                <button type="button" className="btn btn-ghost" onClick={closeCreateModal}>
                  閉じる
                </button>
              ) : null}
              {canSend ? (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={sendingSelected || sendLine.isPending || !lineReady}
                  onClick={sendToLinkedRecipients}
                >
                  送付する
                </button>
              ) : null}
              {form.kind === "test" ? (
                <span className="order-draft-badge is-test">テスト · 正式な発注ではありません</span>
              ) : (
                <span className="order-draft-badge">正式</span>
              )}
              {!creating && detail ? (
                <button
                  type="button"
                  className="btn btn-line-blue btn-sm"
                  disabled={changeLoading}
                  onClick={() => startChange(detail.id)}
                >
                  変更を作成
                </button>
              ) : null}
              {!creating && detail ? (
                <button
                  type="button"
                  className="btn btn-line-green btn-sm"
                  disabled={changeLoading}
                  title="同じイベントを別の日に行うときに使います。元の依頼書には影響しません"
                  onClick={() => void startCopy(detail.id)}
                >
                  別日で新規作成
                </button>
              ) : null}
              {!creating && detail && detail.status !== "draft" ? (
                <button type="button" className="btn btn-ghost btn-sm" onClick={loadFormFromDetail}>
                  この版の内容をフォームに表示
                </button>
              ) : null}
            </div>
          </header>

          <div className="order-draft-body">
            {createModal && actionError ? <ErrorState title="処理できませんでした" description={actionError} /> : null}
            {createModal && actionMessage ? <p>{actionMessage}</p> : null}
            <section className="order-draft-section">
              <div className="order-draft-grid">
                <div className="order-field order-span-4">
                  <span className="order-field-label">区分</span>
                  <div className="order-segment" role="group" aria-label="区分">
                    <button
                      type="button"
                      className={form.kind === "formal" ? "is-active" : ""}
                      disabled={!editable}
                      onClick={() => setForm({ ...form, kind: "formal" })}
                    >
                      正式
                    </button>
                    <button
                      type="button"
                      className={form.kind === "test" ? "is-active is-test" : ""}
                      disabled={!editable}
                      onClick={() => setForm({ ...form, kind: "test" })}
                    >
                      テスト
                    </button>
                  </div>
                </div>
              </div>
            </section>

            <OrderInternalSourceEditor value={form.internal_source ?? null} disabled={!editable} onChange={(internal_source) => setForm({ ...form, internal_source })} />
            <section className="order-draft-section">
              <h4>案件依頼</h4>
              <div className="order-document">
                <p className="order-document-title">【案件依頼】</p>
                <div className="order-draft-grid">
                  <label className="order-field order-span-6">
                    <span className="order-field-label">案件名</span>
                    <textarea
                      className="is-short"
                      value={sections.projectName}
                      disabled={!editable}
                      placeholder={"【イベント名】\nhttps://example.com/event"}
                      onChange={(event) => setSections({ ...sections, projectName: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <fieldset className="order-field order-span-6 order-category-field">
                    <legend className="order-field-label">
                      カテゴリ
                      <span className="order-field-hint">1つ選びます。「研修」だけは、ほかの1つと一緒に選べます。PDFには載りません。</span>
                    </legend>
                    <div className="order-category-options">
                      {ORDER_CATEGORY_OPTIONS.map((item) => {
                        const checked = sections.categories.includes(item);
                        const blocked = !checked && item !== TRAINING_CATEGORY && sections.categories.some((value) => value !== TRAINING_CATEGORY);
                        return (
                          <label key={item} className={`order-check${blocked ? " is-blocked" : ""}`}>
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={!editable || blocked}
                              onChange={(event) => setSections({ ...sections, categories: toggleOrderCategory(sections.categories, item, event.target.checked) })}
                            />
                            {item}
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                  <label className="order-field order-span-6">
                    <span className="order-field-label">稼働場所</span>
                    <textarea
                      className="is-short is-site"
                      value={form.site_name}
                      disabled={!editable}
                      placeholder={"会場名\n（住所）"}
                      onChange={(event) => { setForm({ ...form, site_id: null, site_name: withFullwidthTilde(event.target.value) }); setSections({ ...sections, placeId: "", mapsUrl: "" }); }}
                    />
                  </label>
                  <label className="order-field order-span-6">
                    <span className="order-field-label">背景</span>
                    <textarea
                      className="is-short"
                      value={sections.background}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, background: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <OrderLocationEditor disabled={!editable} venueName={form.site_name} address={form.site_address ?? ""} placeId={sections.placeId ?? ""} savedMapsUrl={sections.mapsUrl ?? ""} onMapsUrl={(mapsUrl) => { setSections({ ...sections, mapsUrl, placeId: "" }); setForm({ ...form, site_id: null }); }} onAddress={(address) => setForm({ ...form, site_id: null, site_address: address || null })} onPlaceId={(placeId) => { setSections({ ...sections, placeId, mapsUrl: "" }); if (placeId) setForm({ ...form, site_id: null }); }} />
                  <label className="order-field order-span-6">
                    <span className="order-field-label">集合場所（任意）</span>
                    <textarea
                      className="is-short"
                      value={sections.meetingPlace}
                      disabled={!editable}
                      placeholder={"例：会場の正面入口前\n※未定の場合はその旨を記載"}
                      onChange={(event) => setSections({ ...sections, meetingPlace: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <label className="order-field order-span-4">
                    <span className="order-field-label">会場の最寄り駅（任意）</span>
                    <input
                      value={sections.siteStation}
                      disabled={!editable}
                      maxLength={100}
                      placeholder="例：新宿駅（南口）"
                      onChange={(event) => setSections({ ...sections, siteStation: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <label className="order-field order-span-2">
                    <span className="order-field-label">駅から徒歩（分）</span>
                    <input
                      type="number"
                      inputMode="numeric"
                      min={0}
                      max={120}
                      step={1}
                      value={sections.siteStationWalkMinutes}
                      disabled={!editable}
                      placeholder="例：5"
                      onChange={(event) => setSections({ ...sections, siteStationWalkMinutes: event.target.value.replace(/[^0-9]/g, "").slice(0, 3) })}
                    />
                  </label>
                  <div className="order-field order-span-6">
                    <span className="order-field-label">稼働日</span>
                    <div className="order-date-range">
                      <OrderDatePicker
                        label="稼働日の開始"
                        value={workDateFrom}
                        disabled={!editable}
                        onChange={(day) => setWorkDateBound("from", day)}
                      />
                      <span className="order-date-range-sep" aria-hidden="true">～</span>
                      <OrderDatePicker
                        label="稼働日の終了"
                        min={workDateFrom || undefined}
                        value={workDateTo}
                        disabled={!editable}
                        onChange={(day) => setWorkDateBound("to", day)}
                      />
                    </div>
                    {parsedWorkDates && form.work_date_label ? (
                      <span className="order-field-hint">{form.work_date_label}</span>
                    ) : null}
                    {legacyWorkDate ? (
                      <span className="order-field-hint order-date-legacy">
                        保存されている文面です。日付を入れると、こちらに置き換わります。
                        {"\n"}
                        {legacyWorkDate}
                      </span>
                    ) : null}
                  </div>
                  <div className="order-field order-span-6">
                    {sections.schedule ? (
                      <>
                        <HolidayPicker from={workDateFrom} to={workDateTo} dates={holidays} disabled={!editable} onChange={changeHolidays} />
                        {holidaySingleConflicts.length > 0 ? (
                          <span className="form-error">休業日に「1日ごと」の稼働日の詳細があります（{holidaySingleConflicts.map((d) => dateGroupLabel({ id: d, date_mode: "single", from: d, to: d })).join("、")}）。このままでは保存できません。</span>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <span className="order-field-label">休業日</span>
                        <span className="order-field-hint">日付・期間ごとの入力に切り替えると設定できます。</span>
                      </>
                    )}
                  </div>
                  <label className="order-field order-span-6">
                    <span className="order-field-label">稼働日の補足（全体）</span>
                    <textarea
                      className="is-short"
                      value={sections.workDateDetail}
                      disabled={!editable}
                      placeholder={"10/8(木)　前日準備\n10/9(金)～10/13(火)　実施日"}
                      onChange={(event) => setSections({ ...sections, workDateDetail: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  {sections.schedule ? (
                    <div className="order-field order-span-6 order-partial-accept">
                      <label className="order-check">
                        <input
                          type="checkbox"
                          checked={Boolean(form.allow_partial_accept)}
                          disabled={!editable}
                          onChange={(event) => setForm({ ...form, allow_partial_accept: event.target.checked })}
                        />
                        日付を選んで受諾できる（一部の日だけの参加を認める）
                      </label>
                      <div className="order-field-hint">オンにすると、公式LINEのボタンが「全日程で受諾します」「日付を選んで受諾する」「今回は辞退します」になり、本人がカレンダーで参加する日を選べます（稼働日が2日以上ある送付先だけ）。オフの依頼書は「全日程で受諾します」「今回は辞退します」の2つです。</div>
                    </div>
                  ) : null}
                  {!sections.schedule && <label className="order-field order-span-4">
                    <span className="order-field-label">稼働時間</span>
                    <textarea
                      className="is-tall"
                      value={sections.hours}
                      disabled={!editable}
                      placeholder={"10/9(金)　※初日30分前集合\n　8:30　集合・準備\n　10:00～18:00　実施\n　19:00　片付け・解散\n\n10/10(土)～10/13(火)\n　9:00　集合・準備\n　10:00～18:00　実施\n　19:00　片付け・解散"}
                      onChange={(event) => setSections({ ...sections, hours: withFullwidthTilde(event.target.value) })}
                    />
                  </label>}
                  {sections.schedule ? <OrderScheduleEditor schedule={sections.schedule} periodFrom={workDateFrom} periodTo={workDateTo} disabled={!editable} onChange={changeSchedule} /> : editable && <div className="order-span-12"><button type="button" className="btn btn-ghost" onClick={() => void enableSchedule()}>日付・期間ごとの入力に切り替える</button><div className="order-field-hint">文章の入力のままでは、受諾しても公式LINEの予定・起床報告に載りません。</div></div>}
                  {(sections.previousHours || sections.previousFee) && <details className="order-span-12"><summary>切替前の勤務時間・単価（参考）</summary><pre>{sections.previousHours}{"\n\n"}{sections.previousFee}</pre></details>}
                  <label className="order-field order-span-4">
                    <span className="order-field-label">内容</span>
                    <textarea
                      value={sections.content}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, content: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <label className="order-field order-span-4">
                    <span className="order-field-label">持ち物</span>
                    <textarea
                      value={sections.belongings}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, belongings: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  {!sections.schedule && <label className="order-field order-span-4">
                    <span className="order-field-label">単価</span>
                    <textarea
                      className="is-tall"
                      value={sections.fee}
                      disabled={!editable}
                      placeholder={"10/9(金)\n報酬：¥20,500(税抜)\n　(昼食代、交通費込み)\n\n10/10(土)～10/13(火)\n報酬：¥19,500(税抜)\n　(昼食代、交通費込み)"}
                      onChange={(event) => setSections({ ...sections, fee: withFullwidthTilde(event.target.value) })}
                    />
                  </label>}
                  <label className="order-field order-span-4">
                    <span className="order-field-label">インセンティブ</span>
                    <textarea
                      className="is-tall"
                      value={sections.incentive}
                      disabled={!editable}
                      placeholder={"※インセン無し\nまたは日ごとの金額"}
                      onChange={(event) => setSections({ ...sections, incentive: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <label className="order-field order-span-12">
                    <span className="order-field-label">備考</span>
                    <textarea
                      className="is-short"
                      value={sections.notes}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, notes: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                </div>
              </div>
            </section>

            <section className="order-draft-section">
              <h4>連絡先</h4>
              <div className="order-draft-grid">
                <label className="order-field order-field-top order-span-4">
                  <span className="order-field-label">運営側の連絡担当者</span>
                  <input
                    value={form.contact_name}
                    placeholder="いない場合は空欄（「なし」と表示）"
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, contact_name: withFullwidthTilde(event.target.value) })}
                  />
                </label>
                <label className="order-field order-span-8">
                  <span className="order-field-label order-inline-label">
                    取引相手メモ
                    <span className="order-field-hint">PDFには記載しません</span>
                  </span>
                  <textarea
                    className="is-short"
                    value={form.counterparty_note ?? ""}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, counterparty_note: withFullwidthTilde(event.target.value) })}
                  />
                </label>
              </div>
            </section>

            <section className="order-draft-section">
              <h4>送付と追跡</h4>
              <div className="order-draft-grid">
                <label className="order-field order-span-4">
                  <span className="order-field-label">
                    <span className="order-inline-label">期限の案内<span className="order-field-hint">（必須）</span></span>
                    <span className="order-field-hint">期限内に返事がない相手へ案内を送ります</span>
                  </span>
                  <input
                    type="date"
                    required
                    value={form.follow_up_due_on ?? ""}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, follow_up_due_on: event.target.value || null })}
                  />
                </label>
                <label className="order-field order-span-4">
                  <span className="order-field-label">案内の時刻</span>
                  <input
                    type="time"
                    required
                    value={form.follow_up_due_time || "21:00"}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, follow_up_due_time: event.target.value || "21:00" })}
                  />
                </label>
              </div>
              <div className="order-choice-row order-phone-row">
                <label className={`order-choice${form.phone_first ? " is-on" : ""}`}>
                  <input
                    type="checkbox"
                    checked={form.phone_first}
                    disabled={!editable}
                    onChange={(event) => {
                      const phoneFirst = event.target.checked;
                      setForm((current) => {
                        const next = { ...current, phone_first: phoneFirst };
                        formRef.current = next;
                        return next;
                      });
                    }}
                  />
                  <span>
                    <span className="order-choice-title">電話先行</span>
                    <span className="order-choice-hint">電話しただけでは、送付済み・受領済みにはしません。</span>
                  </span>
                </label>
                {form.phone_first ? <label className="order-field">
                  <span className="order-field-label">電話メモ</span>
                  <input
                    value={form.phone_note ?? ""}
                    disabled={!editable}
                    placeholder="電話した内容があれば"
                    onChange={(event) => {
                      const phoneNote = withFullwidthTilde(event.target.value);
                      setForm((current) => {
                        const next = { ...current, phone_note: phoneNote };
                        formRef.current = next;
                        return next;
                      });
                    }}
                  />
                </label> : null}
              </div>
              <p className="order-field-hint">依頼書の作成者と管理ロールを持つ担当者が、送付・回答状況を確認します。</p>
            </section>

            <section className="order-draft-section">
              <div className="order-recipients">
                <div className="order-recipients-head">
                  <div>
                    <h4>送付先</h4>
                    <p>最大{MAX_ORDER_RECIPIENTS}人まで選べます。</p>
                  </div>
                  <span className={`order-count${form.worker_ids.length > MAX_ORDER_RECIPIENTS ? " is-over" : ""}`}>
                    {form.worker_ids.length} / {MAX_ORDER_RECIPIENTS}
                  </span>
                </div>
                <div className="order-recipients-search">
                  <label className="order-field">氏名・付与ロールで検索
                  <input
                    placeholder="氏名・商業Dなどで絞り込み"
                    value={workerSearch}
                    disabled={!editable}
                    onChange={(event) => setWorkerSearch(event.target.value)}
                  />
                  </label>
                </div>
                <fieldset className="order-role-filters" disabled={!editable || workerRolesQuery.isLoading}>
                  <legend>付与ロールで絞り込み</legend>
                  <p className="order-field-hint">複数選択できます。選んだいずれかのロールを持つ人を表示します。未選択なら全員を表示します。</p>
                  <p className="order-field-hint">イベントDは対応できる最大規模です。小型を選ぶと小型・中型・大型、中型を選ぶと中型・大型、大型を選ぶと大型のロールを持つ人を表示します。</p>
                  <div className="order-role-options">
                    {workerRoles.map((role) => <label key={role.code} className={`order-role-option${workerRoleFilters.includes(role.code) ? " is-on" : ""}`}>
                      <input type="checkbox" checked={workerRoleFilters.includes(role.code)} onChange={(event) => setWorkerRoleFilters((current) => event.target.checked ? [...current, role.code] : current.filter((code) => code !== role.code))} />
                      {role.label}
                    </label>)}
                  </div>
                  {workerRoleFilters.length > 0 && <button type="button" className="btn btn-ghost" onClick={() => setWorkerRoleFilters([])}>ロールの絞り込みを解除</button>}
                </fieldset>
                {workerRolesQuery.isError && <p className="form-error">付与ロールを取得できませんでした。画面を開き直してください。</p>}
                {selectedWorkers.length > 0 ? (
                  <div className="order-recipient-picks">
                    {selectedWorkers.map((worker) => {
                      const absentCount = (form.recipient_absences?.[worker.id] ?? []).filter((day) => workDates.includes(day)).length;
                      return (
                        <span key={worker.id} className="order-pick">
                          {worker.name}
                          {workDates.length > 0 && (
                            <button
                              type="button"
                              className="btn btn-ghost btn-sm"
                              aria-expanded={absenceWorkerId === worker.id}
                              onClick={() => setAbsenceWorkerId(absenceWorkerId === worker.id ? null : worker.id)}
                            >
                              不参加日{absentCount > 0 ? `（${absentCount}日）` : ""}
                            </button>
                          )}
                        </span>
                      );
                    })}
                  </div>
                ) : (
                  <p className="order-recipient-empty">まだ送付先は選ばれていません。</p>
                )}
                {absenceWorker && workDates.length > 0 && (
                  <fieldset className="order-absence-panel" disabled={!editable}>
                    <legend>{absenceWorker.name}さんの不参加日</legend>
                    <p className="order-field-hint">この人だけが休む日を選びます。依頼書のPDFには載らず、本人へのLINEの案内にだけ使います。休業日は「稼働時間の詳細」で設定します。</p>
                    <div className="order-role-options">
                      {workDates.map((day) => {
                        const checked = (form.recipient_absences?.[absenceWorker.id] ?? []).includes(day);
                        return (
                          <label key={day} className={`order-role-option${checked ? " is-on" : ""}`}>
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(event) => {
                                const current = form.recipient_absences?.[absenceWorker.id] ?? [];
                                const nextDates = event.target.checked ? [...current, day].sort() : current.filter((d) => d !== day);
                                setForm({ ...form, recipient_absences: { ...(form.recipient_absences ?? {}), [absenceWorker.id]: nextDates } });
                              }}
                            />
                            {dateGroupLabel({ id: day, date_mode: "single", from: day, to: day })}
                          </label>
                        );
                      })}
                    </div>
                    {workDates.every((day) => (form.recipient_absences?.[absenceWorker.id] ?? []).includes(day)) && (
                      <p className="form-error">稼働日が0日になります。この人を送付先から外してください。</p>
                    )}
                    <button type="button" className="btn btn-ghost" onClick={() => setAbsenceWorkerId(null)}>閉じる</button>
                  </fieldset>
                )}
                <div className="order-recipient-list">
                  {visibleWorkers.map((worker) => (
                    <label
                      key={worker.id}
                      className={`order-recipient${form.worker_ids.includes(worker.id) ? " is-on" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={form.worker_ids.includes(worker.id)}
                        disabled={!editable || (!form.worker_ids.includes(worker.id) && form.worker_ids.length >= MAX_ORDER_RECIPIENTS)}
                        onChange={(event) => {
                          const next = event.target.checked
                            ? [...form.worker_ids, worker.id]
                            : form.worker_ids.filter((id) => id !== worker.id);
                          setForm({ ...form, worker_ids: next });
                        }}
                      />
                      <span>{worker.name}{(worker.tags ?? []).length > 0 && <small className="order-recipient-roles">{worker.tags!.map((code) => workerRoles.find((role) => role.code === code)?.label ?? code).join("・")}</small>}</span>
                    </label>
                  ))}
                  {visibleWorkers.length === 0 ? (
                    <p className="order-recipient-empty">該当する稼働者はいません。</p>
                  ) : null}
                </div>
              </div>
            </section>

            {detail && detail.deliveries.length > 0 ? (
              <section className="order-draft-section">
                <h4>送付状況</h4>
                {detail.status === "confirmed" && !detail.dispatch_stopped ? (
                  <div className="order-inline-actions">
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={sendingSelected || sendLine.isPending || !lineReady}
                      onClick={sendToLinkedRecipients}
                    >
                      送付する
                    </button>
                  </div>
                ) : null}
                <div className="order-draft-table">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>送付先</th>
                        <th>送信</th>
                        <th>返事</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.deliveries.map((row) => (
                        <tr key={row.id}>
                          <td>
                            {row.worker_name_snapshot}
                            {(detail.draft_recipient_absences?.[row.worker_id] ?? []).length > 0 && (
                              <div className="order-field-hint">
                                不参加日：{(detail.draft_recipient_absences?.[row.worker_id] ?? []).map((day) => dateGroupLabel({ id: day, date_mode: "single", from: day, to: day })).join("、")}
                              </div>
                            )}
                          </td>
                          <td>
                            {SEND_LABEL[row.send_status] ?? row.send_status}
                            {row.last_send_error ? `（${row.last_send_error}）` : ""}
                            {detail.status === "confirmed" && !detail.dispatch_stopped ? (
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                disabled={
                                  sendLine.isPending
                                  || sendingSelected
                                  || !lineReady
                                  || !row.line_linked
                                  || row.view_revoked
                                  || row.ack_status !== "unacked"
                                }
                                onClick={() => sendLine.mutate(row.id)}
                              >
                                この人に送る
                              </button>
                            ) : null}
                          </td>
                          <td>
                            {REPLY_LABEL[row.ack_status] ?? row.ack_status}
                            {row.decline_reason ? `（${row.decline_reason}）` : ""}
                            {row.applied && row.participation_dates.length > 0 ? (
                              <div className="order-field-hint">
                                稼働日：{compactDateList(row.participation_dates)}
                              </div>
                            ) : null}
                            {row.can_end_participation && (row.applied || row.ack_status !== "acked") ? (
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                disabled={withdrawAcceptance.isPending}
                                onClick={() => void recordWithdrawal(row)}
                              >
                                今後の参加を終了
                              </button>
                            ) : null}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {detail.status !== "draft" ? (
                  <>
                    <h4>日ごとの参加人数</h4>
                    <VersionParticipationSummary versionId={detail.id} />
                  </>
                ) : null}
              </section>
            ) : null}

            {detail ? (
              <section className="order-draft-section">
                <h4>対応</h4>
                <div className="order-draft-grid">
                  <div className="order-span-6">
                    <label className="order-field">
                      <span className="order-field-label">改訂・取消の理由</span>
                      <input value={reason} onChange={(event) => setReason(event.target.value)} />
                    </label>
                    <div className="order-inline-actions">
                      {detail.status !== "draft" ? (
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => reviseMutation.mutate(detail.id)}
                        >
                          理由を付けて改訂
                        </button>
                      ) : null}
                      {detail.status !== "cancelled" ? (
                        <button
                          type="button"
                          className="btn btn-ghost"
                          onClick={() => cancelMutation.mutate(detail.id)}
                        >
                          理由を付けて取消
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <div className="order-span-6">
                    <label className="order-field">
                      <span className="order-field-label">対応メモ</span>
                      <input value={note} onChange={(event) => setNote(event.target.value)} />
                    </label>
                    <div className="order-inline-actions">
                      <button type="button" className="btn btn-ghost" onClick={() => noteMutation.mutate(detail.id)}>
                        メモを追加
                      </button>
                    </div>
                    {detail.notes.length > 0 ? (
                      <ul className="order-note-list">
                        {detail.notes.map((item) => (
                          <li key={item.id}>
                            <span>{item.author_name}</span>
                            {item.body}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                </div>
              </section>
            ) : null}
          </div>

          {editable || detail?.status === "draft" || detail?.has_pdf || canSend ? (
            <>
            {createModal && actionError ? (
              <p className="form-error order-draft-foot-error" role="alert">{actionError}</p>
            ) : null}
            <footer className="order-draft-foot">
              <div className="order-draft-foot-start">
                {createModal ? (
                  <button type="button" className="btn btn-ghost order-draft-close" onClick={closeCreateModal}>
                    保存せずに閉じる
                  </button>
                ) : null}
                {detail?.has_pdf ? (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      const stored = sectionsFromStored(detail.request_conditions, detail.body);
                      downloadOrderRequestPdf(
                        detail.id,
                        orderRequestPdfFileName(detail.work_date_label, stored.projectName),
                      );
                    }}
                  >
                    PDFを取得
                  </button>
                ) : null}
              </div>
              <div className="order-draft-foot-end">
                <button type="button" className="btn btn-ghost" onClick={() => setLinePreviewOpen(true)}>
                  送付内容を確認
                </button>
                {canSend ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={sendingSelected || sendLine.isPending || !lineReady}
                    onClick={sendToLinkedRecipients}
                  >
                    送付する
                  </button>
                ) : null}
                {editable ? (
                  <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending || pdfReview?.phase === "loading"}>
                    下書きを保存
                  </button>
                ) : null}
                {editable ? (
                  <button
                    type="button"
                    className="btn btn-pdf"
                    disabled={saveMutation.isPending || pdfReview?.phase === "loading"}
                    onClick={() => {
                      void openPdfReview();
                    }}
                  >
                    {pdfReview?.phase === "loading" ? "PDFを作成しています" : "PDFを確認して送付する"}
                  </button>
                ) : null}
                {detail?.status === "draft" ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={confirmMutation.isPending || saveMutation.isPending}
                    onClick={async () => {
                      setActionError("");
                      if (dueMissing()) return;
                      if (!(await acceptWithoutSchedule())) return;
                      try {
                  const saved = await updateOrderRequestVersion(detail.id, draftPayload());
                        confirmMutation.mutate(saved.id);
                      } catch (error) {
                        setActionError(messageOf(error));
                      }
                    }}
                  >
                    確定してPDFを保存
                  </button>
                ) : null}
              </div>
            </footer>
            </>
          ) : null}
        </form>
        ) : (
          <div className="order-draft is-modal" role="dialog" aria-busy="true" aria-labelledby="order-draft-title">
            <p id="order-draft-title" className="order-pdf-review-wait">読み込んでいます</p>
          </div>
        )}
        </div>
      )}

      {pdfReview ? (
        <div className="order-create-backdrop is-front" role="dialog" aria-modal="true" aria-labelledby="order-pdf-review-title">
          <div className="order-draft is-modal order-pdf-review-card">
            <header className="order-draft-head">
              <div>
                <p className="order-draft-kicker">発注依頼書</p>
                <h3 id="order-pdf-review-title">PDFの確認</h3>
                <p className="order-draft-lead">内容を確認してから送付します。</p>
              </div>
            </header>
            <div className="order-pdf-review-frame">
              {pdfReview.phase === "ready" && pdfReview.url ? (
                <iframe title="発注依頼書のPDF" src={pdfReview.url} />
              ) : (
                <p className="order-pdf-review-wait">PDFを作成しています</p>
              )}
            </div>
            {pdfReviewError ? <ErrorState title="送付できませんでした" description={pdfReviewError} /> : null}
            {pdfReview.phase === "ready" ? (
              <footer className="order-draft-foot">
                <div className="order-draft-foot-start" />
                <div className="order-draft-foot-end">
                  <button
                    type="button"
                    className="btn btn-ghost"
                    disabled={pdfSending}
                    onClick={() => {
                      returnToEditing();
                    }}
                  >
                    修正する
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={pdfSending}
                    onClick={() => {
                      void sendReviewedOrder();
                    }}
                  >
                    {pdfSending ? "送付しています" : "この情報で送付する"}
                  </button>
                </div>
              </footer>
            ) : null}
          </div>
        </div>
      ) : null}

      {linePreviewOpen ? (
        <div className="order-line-backdrop" onClick={() => setLinePreviewOpen(false)}>
          <div
            className="order-line-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="order-line-preview-title"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="order-line-head">
              <h3 id="order-line-preview-title">送付内容の確認</h3>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setLinePreviewOpen(false)}>
                閉じる
              </button>
            </header>
            <p className="order-line-note">
              {form.kind === "test"
                ? "テスト区分で送る公式LINEの画面です。この確認では送信しません。"
                : "正式区分で送る公式LINEの画面です。この確認では送信しません。"}
            </p>
            <div className="order-line-chat" aria-label="LINEのトーク画面">
              <p className="order-line-who">公式LINE</p>
              <div className="order-line-bubble">{previewLineText}</div>
              <div className="order-line-template">
                <p>{LINE_BUTTON_TEXT}</p>
                <div className="order-line-actions">
                  <span className="is-accept">{LINE_ACCEPT_LABEL}</span>
                  <span className="is-decline">{LINE_DECLINE_LABEL}</span>
                </div>
              </div>
            </div>
            <p className="order-line-note">
              辞退を押すと「{LINE_DECLINE_PROMPT}」と出て、次に送った文章を辞退理由として記録します。受諾すると「受諾ありがとうございます。よろしくお願い致します」と返します。
            </p>
            {previewProjectCut || previewDateCut || previewSiteCut ? (
              <p className="order-line-note">案件名、稼働日、現場は、LINEの文面ではそれぞれ80文字までです。続きはPDFに入ります。</p>
            ) : null}
            <p className="order-line-note">
              通知に出る文面は「依頼の案件について、受諾または辞退を押してください。」です。PDFのリンクは送信時に文面へ付きます。保存前の文書番号は未採番です。
            </p>
            <section className="order-line-pdf" aria-label="PDFを開いたとき">
              <h4>PDFを開いたとき</h4>
              {form.kind === "test" ? <p className="order-line-banner">{LINE_TEST_BANNER}</p> : null}
              <div className="order-line-heading">
                <p className={`order-line-doctitle${pdfNotice === "cancel" ? " is-cancel" : ""}`}>{orderRequestDocumentTitle(form.work_date_label, sections.projectName, pdfNotice)}</p>
                <p className="order-line-docno">文書番号　{previewDocumentNumber}　第{previewVersionNo}版</p>
                <p className="order-line-created">
                  {pdfNotice === "change" ? <span className="order-line-change-note">＊赤文字が前回からの変更部分です</span> : null}
                  <span>作成日　{formatCreatedOn(creating ? null : detail?.created_at)}</span>
                </p>
              </div>
              <pre>{previewPdfBody}</pre>
              <dl>
                <div>
                  <dt>担当者</dt>
                  <dd>{form.contact_name || "—"}</dd>
                </div>
                <div>
                  <dt>取引相手メモ</dt>
                  <dd>{form.counterparty_note || "—"}</dd>
                </div>
              </dl>
              <p className="order-line-note">返事は本人の受諾か、辞退理由の送信で記録します。このPDFを開いたことは返事ではありません。</p>
            </section>
          </div>
        </div>
      ) : null}
    </section>
  );
}
