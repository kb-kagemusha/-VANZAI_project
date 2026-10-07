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
import {
  ApiError,
  addOrderRequestNote,
  cancelOrderRequest,
  confirmOrderRequest,
  createOrderRequest,
  downloadOrderRequestPdf,
  fetchOrderRequestPdfPreview,
  getOrderRequestVersion,
  getWorkers,
  listLineLinks,
  listOrderRequestReplies,
  listOrderRequests,
  revokeOrderRequestView,
  reviseOrderRequest,
  sendOrderRequestLine,
  updateOrderRequestVersion,
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
  sectionsFromStored,
  serializeOrderSections,
  siteLabelForList,
  withFullwidthTilde,
  type OrderDocumentSections,
} from "../lib/orderRequestFormat";
import type {
  OrderRequestChangeLink,
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

const EMPTY_FORM: OrderRequestWrite = {
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
  phone_first: false,
  phone_note: "",
  tracker_user_id: null,
  follow_up_due_on: null,
  follow_up_due_time: "21:00",
  assign_tracker_self: false,
};

function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "処理に失敗しました";
}

export function OrderRequestsPage() {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<OrderRequestKind | "all">("formal");
  const [queue, setQueue] = useState<OrderRequestQueue>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<OrderRequestWrite>(EMPTY_FORM);
  const [sections, setSections] = useState<OrderDocumentSections>(EMPTY_ORDER_SECTIONS);
  const [workerSearch, setWorkerSearch] = useState("");
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
  const draftRef = useRef<HTMLFormElement>(null);

  const listQuery = useQuery({
    queryKey: ["order-requests", kind, queue],
    queryFn: () => listOrderRequests({ kind, queue, limit: 50, offset: 0 }),
  });
  const repliesQuery = useQuery({
    queryKey: ["order-request-replies"],
    queryFn: listOrderRequestReplies,
  });
  const workersQuery = useQuery({
    queryKey: ["order-request-workers"],
    queryFn: () => getWorkers({ limit: 200, is_active: true, sort_by: "name", sort_order: "asc" }),
  });
  const detailQuery = useQuery({
    queryKey: ["order-request", selectedId],
    queryFn: () => getOrderRequestVersion(selectedId as string),
    enabled: Boolean(selectedId) && !creating,
  });

  const workers = workersQuery.data?.items ?? [];
  const visibleWorkers = useMemo(() => {
    const query = workerSearch.trim();
    if (!query) return workers;
    return workers.filter((worker) => worker.name.includes(query) || (worker.furigana ?? "").includes(query));
  }, [workerSearch, workers]);
  const selectedWorkers = workers.filter((worker) => form.worker_ids.includes(worker.id));

  const detail = creating ? null : detailQuery.data;
  const editable = creating || detail?.status === "draft";

  function formFromVersion(version: OrderRequestVersion): OrderRequestWrite {
    return {
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
      phone_first: version.phone_first,
      phone_note: version.phone_note ?? "",
      tracker_user_id: version.tracker_user_id,
      follow_up_due_on: version.follow_up_due_on,
      follow_up_due_time: version.follow_up_due_time || "21:00",
      assign_tracker_self: Boolean(version.tracker_user_id),
    };
  }

  function draftPayload(): OrderRequestWrite {
    return {
      ...form,
      request_conditions: serializeOrderSections(sections),
      body: composeOrderDocument(sections, form.work_date_label, form.site_name),
      contact_desk: "",
      counterparty_note: form.counterparty_note || null,
      phone_note: form.phone_note || null,
      site_address: form.site_address || null,
      follow_up_due_on: form.follow_up_due_on || null,
      follow_up_due_time: form.follow_up_due_time || "21:00",
    };
  }

  function dueMissing(): boolean {
    if (form.follow_up_due_on) return false;
    setActionError("期限の案内の日付を入れてください");
    return true;
  }

  useEffect(() => {
    if (!detail || creating) return;
    setForm(formFromVersion(detail));
    setSections(sectionsFromStored(detail.request_conditions, detail.body));
  }, [creating, detail]);

  useEffect(() => {
    if (!linePreviewOpen) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setLinePreviewOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [linePreviewOpen]);

  const createModal = creating;

  useEffect(() => {
    if (!createModal) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const frame = window.requestAnimationFrame(() => {
      draftRef.current?.focus();
    });
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape" || linePreviewOpenRef.current || pdfReviewRef.current) return;
      setCreating(false);
      setBasedOn(null);
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
  const previewDocument = composeOrderDocument(sections, form.work_date_label, form.site_name);
  const pdfNotice = !creating && detail?.status === "cancelled"
    ? "cancel"
    : (basedOn || detail?.based_on_document_number)
      ? "change"
      : "new";
  const parsedWorkDates = parseWorkDateRange(form.work_date_label);
  const workDateFrom = parsedWorkDates?.from ?? "";
  const workDateTo = parsedWorkDates?.to ?? "";
  const legacyWorkDate = parsedWorkDates || !form.work_date_label.trim() ? "" : form.work_date_label;

  function setWorkDateBound(bound: "from" | "to", value: string) {
    const from = bound === "from" ? value : workDateFrom;
    const to = bound === "to" ? value : workDateTo;
    setForm({ ...form, work_date_label: formatWorkDateRange(from, to) });
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
    setCreating(true);
    setBasedOn(null);
    setSelectedId(null);
    setForm(EMPTY_FORM);
    setSections(EMPTY_ORDER_SECTIONS);
    setWorkerSearch("");
    setActionError("");
    setActionMessage("");
    setReason("");
    setNote("");
    setSavedDraftId(null);
  }

  function closeCreateModal() {
    setCreating(false);
    setBasedOn(null);
    setActionError("");
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
      setCreating(true);
      setSelectedId(null);
      setSavedDraftId(null);
      setBasedOn({
        versionId: version.id,
        documentNumber: version.document_number,
        versionNo: version.version_no,
      });
      setForm({
        ...formFromVersion(version),
        worker_ids: workerIds,
        phone_first: false,
        phone_note: "",
      });
      setSections(sectionsFromStored(version.request_conditions, version.body));
      setReason("");
      setNote("");
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

  const detailSourceNote = detail
    ? basedOnNote(detail.document_number, detail.based_on_document_number, detail.based_on_version_no)
    : null;
  const detailLead = creating
    ? basedOn
      ? `${basedOn.documentNumber} 第${basedOn.versionNo}版を基に、新しい依頼書を作成します。確定するまで送付は始まりません。`
      : "追加案件依頼の項目で下書きします。確定するまで送付は始まりません。"
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
    }
  }

  function missingSendFields(): string[] {
    const missing: string[] = [];
    if (!sections.projectName.trim()) missing.push("案件名");
    if (!form.work_date_label.trim()) missing.push("稼働日");
    if (!form.site_name.trim()) missing.push("稼働場所");
    if (!form.contact_name.trim()) missing.push("担当者");
    if (!form.follow_up_due_on) missing.push("期限の案内");
    if (form.worker_ids.length === 0) missing.push("送付先");
    if (form.worker_ids.length > 30) missing.push("送付先は30人まで");
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

  async function openPdfReview() {
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

  async function saveDraftAndCloseReview() {
    if (!pdfReview?.versionId) return;
    setPdfSending(true);
    setPdfReviewError("");
    try {
      await persistCurrentDraft();
      dismissPdfReview(null);
      setActionMessage("下書きを保存しました。確定するまで送付は始まりません。");
      await refresh();
    } catch (error) {
      setPdfReviewError(messageOf(error));
    } finally {
      setPdfSending(false);
    }
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
    } catch (error) {
      setPdfReviewError(messageOf(error));
    } finally {
      setPdfSending(false);
    }
  }

  return (
    <section>
      <PageHeader
        eyebrow="発注依頼"
        title="発注依頼書"
        description="誰が、誰に、どの版を確定したかを担当者間で共有します。返事は本人の受諾か辞退だけです。"
        titleAction={(
          <button type="button" className="btn btn-primary" onClick={startNewDraft}>
            新規の依頼書を作成
          </button>
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
        <p className="order-list-lead">送付先ごとの返事です。日付は稼働日です。内容を変えるときは「変更を作成」で、この依頼を基にした新しい依頼書を作れます。</p>
        <div className="order-list-table">
          <table className="data-table">
            <thead>
              <tr>
                <th>文書番号</th>
                <th>案件名</th>
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
                  <td className="order-cell-multiline">{row.work_date_label}</td>
                  <td>{row.worker_name}</td>
                  <td>
                    {REPLY_LABEL[row.ack_status] ?? row.ack_status}
                    {row.decline_reason ? <div className="order-cell-multiline">{row.decline_reason}</div> : null}
                  </td>
                  <td>
                    <div className="order-row-actions">
                      <button
                        type="button"
                        className="btn btn-change btn-sm"
                        disabled={changeLoading}
                        onClick={() => startChange(row.version_id)}
                      >
                        変更を作成
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
        <p className="order-list-lead">下書きと確定した版です。追跡は、返事を追う担当者の名前です。作成済みの依頼書から「変更を作成」で、内容を写した新しい依頼書を作れます。</p>
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
        <table className="data-table">
          <thead>
            <tr>
              <th>文書番号</th>
              <th>案件名</th>
              <th>版</th>
              <th>区分</th>
              <th>状態</th>
              <th>現場</th>
              <th>日付</th>
              <th>作成者</th>
              <th>追跡</th>
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
                  {basedOnNote(item.document_number, item.based_on_document_number, item.based_on_version_no) ? (
                    <span className="order-change-note">
                      {basedOnNote(item.document_number, item.based_on_document_number, item.based_on_version_no)}
                    </span>
                  ) : null}
                </td>
                <td className="order-cell-multiline">{siteLabelForList(item.project_name)}</td>
                <td>{item.version_no}</td>
                <td>{item.kind === "test" ? "テスト" : "正式"}</td>
                <td>
                  {STATUS_LABEL[item.status]}
                  {item.phone_first ? " / 電話先行" : ""}
                  {item.dispatch_stopped ? " / 送付停止" : ""}
                </td>
                <td className="order-cell-multiline">{siteLabelForList(item.site_name)}</td>
                <td className="order-cell-multiline">{item.work_date_label}</td>
                <td>{item.created_by_name}</td>
                <td>{item.tracker_name ?? "—"}</td>
                <td>{item.recipient_count}</td>
                <td>{item.follow_up_due_on ? `${item.follow_up_due_on} ${item.follow_up_due_time || "21:00"}` : "—"}</td>
                <td>
                  <div className="order-row-actions">
                    <button
                      type="button"
                      className="btn btn-change btn-sm"
                      disabled={changeLoading}
                      onClick={() => startChange(item.version_id)}
                    >
                      変更を作成
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

      {(creating || detail) && (
        <div className={createModal ? "order-create-backdrop" : undefined}>
        <form
          ref={draftRef}
          className={createModal ? "order-draft is-modal" : "order-draft"}
          role={createModal ? "dialog" : undefined}
          aria-modal={createModal ? true : undefined}
          aria-labelledby="order-draft-title"
          tabIndex={createModal ? -1 : undefined}
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
            <div>
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
                  className="btn btn-change btn-sm"
                  disabled={changeLoading}
                  onClick={() => startChange(detail.id)}
                >
                  変更を作成
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

            <section className="order-draft-section">
              <h4>追加案件依頼</h4>
              <div className="order-document">
                <p className="order-document-title">【追加案件依頼】</p>
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
                  <label className="order-field order-span-6">
                    <span className="order-field-label">背景</span>
                    <textarea
                      className="is-short"
                      value={sections.background}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, background: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <label className="order-field order-span-4">
                    <span className="order-field-label">稼働場所</span>
                    <textarea
                      className="is-short is-site"
                      value={form.site_name}
                      disabled={!editable}
                      placeholder={"会場名\n（住所）\n※集合場所が後から決まるときはその旨"}
                      onChange={(event) => setForm({ ...form, site_name: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <div className="order-field order-span-4">
                    <span className="order-field-label">稼働日</span>
                    <div className="order-date-range">
                      <input
                        type="date"
                        aria-label="稼働日の開始"
                        value={workDateFrom}
                        disabled={!editable}
                        onChange={(event) => setWorkDateBound("from", event.target.value)}
                      />
                      <span className="order-date-range-sep" aria-hidden="true">～</span>
                      <input
                        type="date"
                        aria-label="稼働日の終了"
                        value={workDateTo}
                        disabled={!editable}
                        onChange={(event) => setWorkDateBound("to", event.target.value)}
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
                  <label className="order-field order-span-4">
                    <span className="order-field-label">稼働日の詳細</span>
                    <textarea
                      className="is-short"
                      value={sections.workDateDetail}
                      disabled={!editable}
                      placeholder={"10/8(木)　前日準備\n10/9(金)～10/13(火)　実施日"}
                      onChange={(event) => setSections({ ...sections, workDateDetail: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
                  <label className="order-field order-span-4">
                    <span className="order-field-label">稼働時間</span>
                    <textarea
                      className="is-tall"
                      value={sections.hours}
                      disabled={!editable}
                      placeholder={"10/9(金)　※初日30分前集合\n　8:30　集合・準備\n　10:00～18:00　実施\n　19:00　片付け・解散\n\n10/10(土)～10/13(火)\n　9:00　集合・準備\n　10:00～18:00　実施\n　19:00　片付け・解散"}
                      onChange={(event) => setSections({ ...sections, hours: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
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
                  <label className="order-field order-span-4">
                    <span className="order-field-label">単価</span>
                    <textarea
                      className="is-tall"
                      value={sections.fee}
                      disabled={!editable}
                      placeholder={"10/9(金)\n報酬：¥20,500(税抜)\n　(昼食代、交通費込み)\n\n10/10(土)～10/13(火)\n報酬：¥19,500(税抜)\n　(昼食代、交通費込み)"}
                      onChange={(event) => setSections({ ...sections, fee: withFullwidthTilde(event.target.value) })}
                    />
                  </label>
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
                  <span className="order-field-label">担当者</span>
                  <input
                    value={form.contact_name}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, contact_name: withFullwidthTilde(event.target.value) })}
                  />
                </label>
                <label className="order-field order-span-4">
                  <span className="order-field-label">
                    取引相手メモ
                    <span className="order-field-hint">下請の正式宛先です。共通PDFの宛名には差し込みません。</span>
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
                    期限の案内
                    <span className="order-field-hint">必須です。この日時を過ぎて返事が無い相手へ、案内を1回送ります。</span>
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
                <label className="order-field order-span-4">
                  <span className="order-field-label">電話メモ</span>
                  <input
                    value={form.phone_note ?? ""}
                    disabled={!editable}
                    placeholder="電話した内容があれば"
                    onChange={(event) => setForm({ ...form, phone_note: withFullwidthTilde(event.target.value) })}
                  />
                </label>
              </div>
              <div className="order-choice-row">
                <label className={`order-choice${form.phone_first ? " is-on" : ""}`}>
                  <input
                    type="checkbox"
                    checked={form.phone_first}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, phone_first: event.target.checked })}
                  />
                  <span>
                    <span className="order-choice-title">電話先行</span>
                    <span className="order-choice-hint">電話しただけでは、送付済み・受領済みにはしません。</span>
                  </span>
                </label>
                <label className={`order-choice${form.assign_tracker_self ? " is-on" : ""}`}>
                  <input
                    type="checkbox"
                    checked={form.assign_tracker_self}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, assign_tracker_self: event.target.checked })}
                  />
                  <span>
                    <span className="order-choice-title">追跡担当は自分</span>
                    <span className="order-choice-hint">保存すると、追跡担当が自分になります。</span>
                  </span>
                </label>
              </div>
            </section>

            <section className="order-draft-section">
              <div className="order-recipients">
                <div className="order-recipients-head">
                  <div>
                    <h4>送付先</h4>
                    <p>最大30人まで選べます。</p>
                  </div>
                  <span className={`order-count${form.worker_ids.length > 30 ? " is-over" : ""}`}>
                    {form.worker_ids.length} / 30
                  </span>
                </div>
                <div className="order-recipients-search">
                  <input
                    placeholder="氏名で絞り込み"
                    value={workerSearch}
                    disabled={!editable}
                    onChange={(event) => setWorkerSearch(event.target.value)}
                  />
                </div>
                {selectedWorkers.length > 0 ? (
                  <div className="order-recipient-picks">
                    {selectedWorkers.map((worker) => (
                      <span key={worker.id} className="order-pick">{worker.name}</span>
                    ))}
                  </div>
                ) : (
                  <p className="order-recipient-empty">まだ送付先は選ばれていません。</p>
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
                        disabled={!editable}
                        onChange={(event) => {
                          const next = event.target.checked
                            ? [...form.worker_ids, worker.id]
                            : form.worker_ids.filter((id) => id !== worker.id);
                          setForm({ ...form, worker_ids: next });
                        }}
                      />
                      <span>{worker.name}</span>
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
                        <th>閲覧</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.deliveries.map((row) => (
                        <tr key={row.id}>
                          <td>{row.worker_name_snapshot}</td>
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
                          </td>
                          <td>
                            {row.view_revoked ? (
                              "停止"
                            ) : (
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => revokeOrderRequestView(row.id).then(() => {
                                  queryClient.invalidateQueries({ queryKey: ["order-request", detail.id] });
                                })}
                              >
                                閲覧を停止
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
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
            <footer className="order-draft-foot">
              <div className="order-draft-foot-start">
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
          ) : null}
        </form>
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
                      void saveDraftAndCloseReview();
                    }}
                  >
                    下書きを保存して閉じる
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
