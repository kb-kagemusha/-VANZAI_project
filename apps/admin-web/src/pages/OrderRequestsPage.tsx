/**
 * 発注依頼書の作成・確定・共有一覧。
 * テスト区分だけ、紐付け済みの1人へ公式LINE送信できる。正式区分は送らない。
 */
import { useEffect, useMemo, useState } from "react";
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
  getOrderRequestVersion,
  getWorkers,
  issueLineLinkCode,
  listLineLinks,
  listOrderRequests,
  revokeLineLink,
  revokeOrderRequestView,
  reviseOrderRequest,
  sendOrderRequestLine,
  updateOrderRequestVersion,
} from "../lib/api/client";
import {
  composeOrderDocument,
  EMPTY_ORDER_SECTIONS,
  sectionsFromStored,
  serializeOrderSections,
  type OrderDocumentSections,
} from "../lib/orderRequestFormat";
import type {
  LineLinkCode,
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

const STATUS_LABEL: Record<OrderRequestStatus, string> = {
  draft: "下書き",
  confirmed: "確定",
  cancelled: "取消",
};

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
  const [linkWorkerId, setLinkWorkerId] = useState("");
  const [issuedCode, setIssuedCode] = useState<LineLinkCode | null>(null);
  const [unlinkReason, setUnlinkReason] = useState("");

  const listQuery = useQuery({
    queryKey: ["order-requests", kind, queue],
    queryFn: () => listOrderRequests({ kind, queue, limit: 50, offset: 0 }),
  });
  const linksQuery = useQuery({
    queryKey: ["line-links"],
    queryFn: listLineLinks,
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
      contact_name: version.contact_name,
      contact_desk: version.contact_desk,
      counterparty_note: version.counterparty_note ?? "",
      worker_ids: version.draft_worker_ids,
      phone_first: version.phone_first,
      phone_note: version.phone_note ?? "",
      tracker_user_id: version.tracker_user_id,
      follow_up_due_on: version.follow_up_due_on,
      assign_tracker_self: Boolean(version.tracker_user_id),
    };
  }

  function draftPayload(): OrderRequestWrite {
    return {
      ...form,
      request_conditions: serializeOrderSections(sections),
      body: composeOrderDocument(sections, form.work_date_label, form.site_name),
      counterparty_note: form.counterparty_note || null,
      phone_note: form.phone_note || null,
      site_address: form.site_address || null,
      follow_up_due_on: form.follow_up_due_on || null,
    };
  }

  useEffect(() => {
    if (!detail || creating) return;
    setForm(formFromVersion(detail));
    setSections(sectionsFromStored(detail.request_conditions, detail.body));
  }, [creating, detail]);

  function refresh() {
    return queryClient.invalidateQueries({ queryKey: ["order-requests"] });
  }

  function showDetail(versionId: string) {
    setCreating(false);
    setSelectedId(versionId);
    setActionError("");
    setActionMessage("");
    setReason("");
    setNote("");
  }

  function loadFormFromDetail() {
    if (!detail) return;
    setForm(formFromVersion(detail));
    setSections(sectionsFromStored(detail.request_conditions, detail.body));
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = draftPayload();
      if (creating) return createOrderRequest(payload);
      if (!detail) throw new Error("版が選ばれていません");
      return updateOrderRequestVersion(detail.id, payload);
    },
    onSuccess: async (version) => {
      setCreating(false);
      setSelectedId(version.id);
      setActionMessage("下書きを保存しました。確定するまで送付は始まりません。");
      setActionError("");
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["order-request", version.id] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const confirmMutation = useMutation({
    mutationFn: (versionId: string) => confirmOrderRequest(versionId),
    onSuccess: async (version) => {
      setActionMessage(
        version.kind === "test"
          ? "確定しました。テスト区分は、紐付け済みの相手へ1人ずつ送れます。"
          : "確定しました。正式区分は書式が未適用のため、公式LINEへは送りません。",
      );
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
  const lineReady = Boolean(linksQuery.data?.line_send_available);
  const linkedIds = new Set((linksQuery.data?.items ?? []).map((item) => item.worker_id));

  const issueLink = useMutation({
    mutationFn: () => issueLineLinkCode(linkWorkerId),
    onSuccess: async (issued) => {
      setIssuedCode(issued);
      setActionError("");
      setActionMessage("コードを発行しました。公式LINEへこのコードだけを送ってください。");
      await queryClient.invalidateQueries({ queryKey: ["line-links"] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const revokeLink = useMutation({
    mutationFn: (workerId: string) => revokeLineLink(workerId, unlinkReason),
    onSuccess: async () => {
      setUnlinkReason("");
      setActionMessage("紐付けを解除しました。解除した相手への公式LINE送信は止まります。");
      await queryClient.invalidateQueries({ queryKey: ["line-links"] });
      if (selectedId) await queryClient.invalidateQueries({ queryKey: ["order-request", selectedId] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  const sendLine = useMutation({
    mutationFn: (deliveryId: string) => sendOrderRequestLine(deliveryId),
    onSuccess: async (version) => {
      setActionMessage("テスト送信を受け付けました。受領は本人が「受け取りました」を押したときだけです。");
      await refresh();
      await queryClient.invalidateQueries({ queryKey: ["order-request", version.id] });
    },
    onError: (error) => setActionError(messageOf(error)),
  });

  return (
    <section>
      <PageHeader
        eyebrow="発注依頼"
        title="発注依頼書"
        description="誰が、誰に、どの版を確定したかを担当者間で共有します。受領は本人の受け取り操作だけです。"
      />
      <p className="card" style={{ padding: "0.9rem 1rem" }}>
        {layoutPending
          ? "弁護士確認済み書式のレイアウトは未適用です。いまのPDFは入力内容の保存です。正式区分は公式LINEへ送りません。"
          : "正式区分の書式を適用しています。"}
        {lineReady
          ? " テスト区分は、紐付け済みの1人ずつ送れます。"
          : " テスト送信には、サーバーへのチャネル設定がまだ必要です。"}
      </p>

      <section className="card" style={{ padding: "0.9rem 1rem", marginBottom: "1rem" }}>
        <h2 style={{ marginTop: 0 }}>公式LINEの本人紐付け</h2>
        <p>{linksQuery.data?.purpose ?? "発注依頼書のテスト送信と受領の記録に使います。"}</p>
        <p>{linksQuery.data?.unlink_notice ?? "解除後は公式LINE送信を止めます。"}</p>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "end", flexWrap: "wrap" }}>
          <label>
            稼働者
            <select value={linkWorkerId} onChange={(event) => setLinkWorkerId(event.target.value)}>
              <option value="">選択</option>
              {workers.map((worker) => (
                <option key={worker.id} value={worker.id}>
                  {worker.name}
                  {linkedIds.has(worker.id) ? "（紐付け済）" : ""}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!linkWorkerId || issueLink.isPending}
            onClick={() => issueLink.mutate()}
          >
            紐付けコードを発行
          </button>
        </div>
        {issuedCode ? (
          <p>
            {issuedCode.worker_name} のコード: <strong>{issuedCode.code}</strong>
            <br />
            {issuedCode.instruction}
          </p>
        ) : null}
        {(linksQuery.data?.items ?? []).length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>稼働者</th>
                <th>LINE表示名</th>
                <th>紐付け日時</th>
              </tr>
            </thead>
            <tbody>
              {linksQuery.data?.items.map((item) => (
                <tr key={item.worker_id}>
                  <td>{item.worker_name}</td>
                  <td>{item.line_display_name || "表示名なし"}</td>
                  <td>{new Date(item.linked_at).toLocaleString("ja-JP")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>紐付け済みの稼働者はいません。</p>
        )}
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "end", flexWrap: "wrap" }}>
          <label>
            解除理由
            <input value={unlinkReason} onChange={(event) => setUnlinkReason(event.target.value)} />
          </label>
          <button
            type="button"
            className="btn btn-ghost"
            disabled={!linkWorkerId || !unlinkReason.trim() || revokeLink.isPending}
            onClick={() => revokeLink.mutate(linkWorkerId)}
          >
            選択した稼働者の紐付けを解除
          </button>
        </div>
      </section>

      <div style={{ display: "flex", gap: "0.75rem", alignItems: "end", margin: "1rem 0" }}>
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
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            setCreating(true);
            setSelectedId(null);
            setForm(EMPTY_FORM);
            setSections(EMPTY_ORDER_SECTIONS);
            setActionError("");
            setActionMessage("");
          }}
        >
          新規の下書き
        </button>
      </div>

      {actionError ? <ErrorState title="処理できませんでした" description={actionError} /> : null}
      {actionMessage ? <p>{actionMessage}</p> : null}
      {listQuery.isLoading ? <LoadingOverlay /> : null}
      {listQuery.isError ? <ErrorState title="一覧を取得できませんでした" description={messageOf(listQuery.error)} /> : null}

      <div className="card" style={{ overflow: "auto", marginBottom: "1rem" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>文書番号</th>
              <th>版</th>
              <th>区分</th>
              <th>状態</th>
              <th>現場</th>
              <th>日付</th>
              <th>作成者</th>
              <th>追跡</th>
              <th>送付先</th>
              <th>期限</th>
            </tr>
          </thead>
          <tbody>
            {(listQuery.data?.items ?? []).map((item) => (
              <tr key={item.version_id}>
                <td>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => showDetail(item.version_id)}>
                    {item.document_number}
                  </button>
                </td>
                <td>{item.version_no}</td>
                <td>{item.kind === "test" ? "テスト" : "正式"}</td>
                <td>
                  {STATUS_LABEL[item.status]}
                  {item.phone_first ? " / 電話先行" : ""}
                  {item.dispatch_stopped ? " / 送付停止" : ""}
                </td>
                <td>{item.site_name}</td>
                <td>{item.work_date_label}</td>
                <td>{item.created_by_name}</td>
                <td>{item.tracker_name ?? "—"}</td>
                <td>{item.recipient_count}</td>
                <td>{item.follow_up_due_on ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {listQuery.data && listQuery.data.items.length === 0 ? (
          <EmptyState title="該当なし" description="この条件の発注依頼書はありません" />
        ) : null}
      </div>

      {detailQuery.isLoading ? <LoadingOverlay /> : null}

      {(creating || detail) && (
        <form
          className="order-draft"
          onSubmit={(event) => {
            event.preventDefault();
            if (editable) {
              setActionError("");
              saveMutation.mutate();
            }
          }}
        >
          <header className="order-draft-head">
            <div>
              <p className="order-draft-kicker">{creating ? "発注依頼書" : detail?.document_number}</p>
              <h3>{creating ? "新規の下書き" : `第${detail?.version_no}版`}</h3>
              <p className="order-draft-lead">
                {creating
                  ? "追加案件依頼の項目で下書きします。確定するまで送付は始まりません。"
                  : `${detail ? STATUS_LABEL[detail.status] : ""}${detail?.created_by_name ? ` · ${detail.created_by_name}` : ""}`}
              </p>
            </div>
            <div className="order-draft-head-side">
              {form.kind === "test" ? (
                <span className="order-draft-badge is-test">テスト · 正式な発注ではありません</span>
              ) : (
                <span className="order-draft-badge">正式</span>
              )}
              {!creating && detail && detail.status !== "draft" ? (
                <button type="button" className="btn btn-ghost btn-sm" onClick={loadFormFromDetail}>
                  この版の内容をフォームに表示
                </button>
              ) : null}
            </div>
          </header>

          <div className="order-draft-body">
            <section className="order-draft-section">
              <h4>追加案件依頼</h4>
              <div className="order-document">
                <p className="order-document-title">【追加案件依頼】</p>
                <div className="order-draft-grid">
                  <label className="order-field order-span-12">
                    <span className="order-field-label">案件名</span>
                    <input
                      value={sections.projectName}
                      disabled={!editable}
                      placeholder="例: 〇〇施策_〇〇"
                      onChange={(event) => setSections({ ...sections, projectName: event.target.value })}
                    />
                  </label>
                  <label className="order-field order-span-12">
                    <span className="order-field-label">背景</span>
                    <textarea
                      className="is-short"
                      value={sections.background}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, background: event.target.value })}
                    />
                  </label>
                  <label className="order-field order-span-6">
                    <span className="order-field-label">稼働場所</span>
                    <input
                      value={form.site_name}
                      disabled={!editable}
                      onChange={(event) => setForm({ ...form, site_name: event.target.value })}
                    />
                  </label>
                  <label className="order-field order-span-6">
                    <span className="order-field-label">稼働日</span>
                    <input
                      value={form.work_date_label}
                      disabled={!editable}
                      placeholder="例: 10月6日"
                      onChange={(event) => setForm({ ...form, work_date_label: event.target.value })}
                    />
                  </label>
                  <div className="order-field order-span-12">
                    <span className="order-field-label">稼働時間</span>
                    <div className="order-draft-grid">
                      <label className="order-field order-span-4">
                        <span className="order-field-hint">集合時間</span>
                        <input
                          value={sections.gatherTime}
                          disabled={!editable}
                          placeholder="例: 9:00"
                          onChange={(event) => setSections({ ...sections, gatherTime: event.target.value })}
                        />
                      </label>
                      <label className="order-field order-span-4">
                        <span className="order-field-hint">実施時間</span>
                        <input
                          value={sections.workTime}
                          disabled={!editable}
                          placeholder="10:00-17:00"
                          onChange={(event) => setSections({ ...sections, workTime: event.target.value })}
                        />
                      </label>
                      <label className="order-field order-span-4">
                        <span className="order-field-hint">解散時間</span>
                        <input
                          value={sections.dismissTime}
                          disabled={!editable}
                          placeholder="例: 17:30"
                          onChange={(event) => setSections({ ...sections, dismissTime: event.target.value })}
                        />
                      </label>
                    </div>
                  </div>
                  <label className="order-field order-span-6">
                    <span className="order-field-label">内容</span>
                    <textarea
                      value={sections.content}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, content: event.target.value })}
                    />
                  </label>
                  <label className="order-field order-span-6">
                    <span className="order-field-label">持ち物</span>
                    <textarea
                      value={sections.belongings}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, belongings: event.target.value })}
                    />
                  </label>
                  <div className="order-field order-span-12">
                    <span className="order-field-label">単価</span>
                    <div className="order-draft-grid">
                      <label className="order-field order-span-6">
                        <span className="order-field-hint">ベース</span>
                        <input
                          value={sections.baseFee}
                          disabled={!editable}
                          placeholder="例: 12000"
                          onChange={(event) => setSections({ ...sections, baseFee: event.target.value })}
                        />
                      </label>
                      <label className="order-field order-span-6">
                        <span className="order-field-hint">インセンティブ</span>
                        <input
                          value={sections.incentive}
                          disabled={!editable}
                          onChange={(event) => setSections({ ...sections, incentive: event.target.value })}
                        />
                      </label>
                    </div>
                  </div>
                  <label className="order-field order-span-12">
                    <span className="order-field-label">備考</span>
                    <textarea
                      className="is-short"
                      value={sections.notes}
                      disabled={!editable}
                      onChange={(event) => setSections({ ...sections, notes: event.target.value })}
                    />
                  </label>
                </div>
              </div>
            </section>

            <section className="order-draft-section">
              <h4>連絡先</h4>
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
                <label className="order-field order-span-4">
                  <span className="order-field-label">担当者</span>
                  <input
                    value={form.contact_name}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, contact_name: event.target.value })}
                  />
                </label>
                <label className="order-field order-span-4">
                  <span className="order-field-label">業務用窓口</span>
                  <input
                    value={form.contact_desk}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, contact_desk: event.target.value })}
                  />
                </label>
                <label className="order-field order-span-12">
                  <span className="order-field-label">
                    取引相手メモ
                    <span className="order-field-hint">下請の正式宛先です。共通PDFの宛名には差し込みません。</span>
                  </span>
                  <textarea
                    className="is-short"
                    value={form.counterparty_note ?? ""}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, counterparty_note: event.target.value })}
                  />
                </label>
              </div>
            </section>

            <section className="order-draft-section">
              <h4>送付と追跡</h4>
              <div className="order-draft-grid">
                <label className="order-field order-span-4">
                  <span className="order-field-label">正式送付・受領の期限</span>
                  <input
                    type="date"
                    value={form.follow_up_due_on ?? ""}
                    disabled={!editable}
                    onChange={(event) => setForm({ ...form, follow_up_due_on: event.target.value || null })}
                  />
                </label>
                <label className="order-field order-span-8">
                  <span className="order-field-label">電話メモ</span>
                  <input
                    value={form.phone_note ?? ""}
                    disabled={!editable}
                    placeholder="電話した内容があれば"
                    onChange={(event) => setForm({ ...form, phone_note: event.target.value })}
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
                <div className="order-draft-table">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>送付先</th>
                        <th>送信</th>
                        <th>受領</th>
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
                            {detail.kind === "test" && detail.status === "confirmed" && !detail.dispatch_stopped ? (
                              <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                disabled={
                                  sendLine.isPending
                                  || !lineReady
                                  || !row.line_linked
                                  || row.view_revoked
                                  || row.ack_status === "acked"
                                }
                                onClick={() => sendLine.mutate(row.id)}
                              >
                                この1人にテスト送信
                              </button>
                            ) : null}
                          </td>
                          <td>{row.ack_status === "acked" ? "受領済" : "未受領"}</td>
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
                  <label className="order-field order-span-12">
                    <span className="order-field-label">改訂・取消の理由</span>
                    <input value={reason} onChange={(event) => setReason(event.target.value)} />
                  </label>
                </div>
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
                <div className="order-draft-grid">
                  <label className="order-field order-span-12">
                    <span className="order-field-label">対応メモ</span>
                    <input value={note} onChange={(event) => setNote(event.target.value)} />
                  </label>
                </div>
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
              </section>
            ) : null}
          </div>

          {editable || detail?.status === "draft" || detail?.has_pdf ? (
            <footer className="order-draft-foot">
              <div className="order-draft-foot-start">
                {detail?.has_pdf ? (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => downloadOrderRequestPdf(detail.id, detail.document_number, detail.version_no)}
                  >
                    PDFを取得
                  </button>
                ) : null}
              </div>
              <div className="order-draft-foot-end">
                {editable ? (
                  <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending}>
                    下書きを保存
                  </button>
                ) : null}
                {detail?.status === "draft" ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={confirmMutation.isPending || saveMutation.isPending}
                    onClick={async () => {
                      setActionError("");
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
      )}
    </section>
  );
}
