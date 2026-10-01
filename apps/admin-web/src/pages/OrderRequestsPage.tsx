/**
 * 発注依頼書の作成・確定・共有一覧。
 * 公式LINE送信は未接続。確定しても送付は始まらない。
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
  listOrderRequests,
  revokeOrderRequestView,
  reviseOrderRequest,
  updateOrderRequestVersion,
} from "../lib/api/client";
import type {
  OrderRequestKind,
  OrderRequestQueue,
  OrderRequestStatus,
  OrderRequestWrite,
} from "../types/orderRequest";

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
  const [workerSearch, setWorkerSearch] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const listQuery = useQuery({
    queryKey: ["order-requests", kind, queue],
    queryFn: () => listOrderRequests({ kind, queue, limit: 50, offset: 0 }),
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

  const detail = creating ? null : detailQuery.data;
  const editable = creating || detail?.status === "draft";

  useEffect(() => {
    if (!detail || creating) return;
    setForm({
      kind: detail.kind,
      work_date_label: detail.work_date_label,
      site_id: detail.site_id,
      site_name: detail.site_name,
      site_address: detail.site_address,
      request_conditions: detail.request_conditions,
      body: detail.body,
      contact_name: detail.contact_name,
      contact_desk: detail.contact_desk,
      counterparty_note: detail.counterparty_note ?? "",
      worker_ids: detail.draft_worker_ids,
      phone_first: detail.phone_first,
      phone_note: detail.phone_note ?? "",
      tracker_user_id: detail.tracker_user_id,
      follow_up_due_on: detail.follow_up_due_on,
      assign_tracker_self: Boolean(detail.tracker_user_id),
    });
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
    setForm({
      kind: detail.kind,
      work_date_label: detail.work_date_label,
      site_id: detail.site_id,
      site_name: detail.site_name,
      site_address: detail.site_address,
      request_conditions: detail.request_conditions,
      body: detail.body,
      contact_name: detail.contact_name,
      contact_desk: detail.contact_desk,
      counterparty_note: detail.counterparty_note ?? "",
      worker_ids: detail.draft_worker_ids,
      phone_first: detail.phone_first,
      phone_note: detail.phone_note ?? "",
      tracker_user_id: detail.tracker_user_id,
      follow_up_due_on: detail.follow_up_due_on,
      assign_tracker_self: Boolean(detail.tracker_user_id),
    });
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload: OrderRequestWrite = {
        ...form,
        counterparty_note: form.counterparty_note || null,
        phone_note: form.phone_note || null,
        site_address: form.site_address || null,
        follow_up_due_on: form.follow_up_due_on || null,
      };
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
      setActionMessage("確定しました。PDFと送付行を保存しました。公式LINEへの送信はまだ接続していません。");
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

  return (
    <section>
      <PageHeader
        eyebrow="発注依頼"
        title="発注依頼書"
        description="誰が、誰に、どの版を確定したかを担当者間で共有します。受領は本人の受け取り操作だけです。"
      />
      {layoutPending ? (
        <p className="card" style={{ padding: "0.9rem 1rem" }}>
          弁護士確認済み書式のレイアウトは未適用です。いまのPDFは入力内容の保存です。公式LINEへの送信もまだ接続していません。
        </p>
      ) : null}

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
          className="card"
          style={{ display: "grid", gap: "0.75rem", padding: "1rem" }}
          onSubmit={(event) => {
            event.preventDefault();
            if (editable) {
              setActionError("");
              saveMutation.mutate();
            }
          }}
        >
          <h3>{creating ? "新規の下書き" : `${detail?.document_number} 第${detail?.version_no}版`}</h3>
          {detail?.kind === "test" ? <strong>テスト・正式な発注ではありません</strong> : null}
          {!creating && detail && detail.status !== "draft" ? (
            <button type="button" className="btn btn-ghost btn-sm" onClick={loadFormFromDetail}>
              この版の内容をフォームに表示
            </button>
          ) : null}

          <label>
            区分
            <select
              value={form.kind}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, kind: event.target.value as OrderRequestKind })}
            >
              <option value="formal">正式</option>
              <option value="test">テスト</option>
            </select>
          </label>
          <label>
            日付
            <input
              value={form.work_date_label}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, work_date_label: event.target.value })}
            />
          </label>
          <label>
            現場
            <input
              value={form.site_name}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, site_name: event.target.value })}
            />
          </label>
          <label>
            依頼条件
            <textarea
              value={form.request_conditions}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, request_conditions: event.target.value })}
            />
          </label>
          <label>
            本文
            <textarea
              value={form.body}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, body: event.target.value })}
            />
          </label>
          <label>
            担当者
            <input
              value={form.contact_name}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, contact_name: event.target.value })}
            />
          </label>
          <label>
            業務用窓口
            <input
              value={form.contact_desk}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, contact_desk: event.target.value })}
            />
          </label>
          <label>
            取引相手メモ（下請の正式宛先。共通PDFの宛名差し込みではありません）
            <textarea
              value={form.counterparty_note ?? ""}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, counterparty_note: event.target.value })}
            />
          </label>
          <label>
            正式送付・受領の期限
            <input
              type="date"
              value={form.follow_up_due_on ?? ""}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, follow_up_due_on: event.target.value || null })}
            />
          </label>
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <input
              type="checkbox"
              checked={form.phone_first}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, phone_first: event.target.checked })}
            />
            電話先行（電話しただけでは送付済み・受領済みにしません）
          </label>
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <input
              type="checkbox"
              checked={form.assign_tracker_self}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, assign_tracker_self: event.target.checked })}
            />
            追跡担当は自分
          </label>
          <label>
            電話メモ
            <input
              value={form.phone_note ?? ""}
              disabled={!editable}
              onChange={(event) => setForm({ ...form, phone_note: event.target.value })}
            />
          </label>

          <fieldset disabled={!editable}>
            <legend>送付先（最大30人）</legend>
            <input
              placeholder="氏名で絞り込み"
              value={workerSearch}
              onChange={(event) => setWorkerSearch(event.target.value)}
            />
            <div style={{ maxHeight: "220px", overflow: "auto" }}>
              {visibleWorkers.map((worker) => (
                <label key={worker.id} style={{ display: "flex", gap: "0.4rem" }}>
                  <input
                    type="checkbox"
                    checked={form.worker_ids.includes(worker.id)}
                    onChange={(event) => {
                      const next = event.target.checked
                        ? [...form.worker_ids, worker.id]
                        : form.worker_ids.filter((id) => id !== worker.id);
                      setForm({ ...form, worker_ids: next });
                    }}
                  />
                  {worker.name}
                </label>
              ))}
            </div>
          </fieldset>

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
                  const saved = await updateOrderRequestVersion(detail.id, {
                    ...form,
                    counterparty_note: form.counterparty_note || null,
                    phone_note: form.phone_note || null,
                    site_address: form.site_address || null,
                    follow_up_due_on: form.follow_up_due_on || null,
                  });
                  confirmMutation.mutate(saved.id);
                } catch (error) {
                  setActionError(messageOf(error));
                }
              }}
            >
              確定してPDFを保存
            </button>
          ) : null}
          {detail?.has_pdf ? (
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => downloadOrderRequestPdf(detail.id, detail.document_number, detail.version_no)}
            >
              PDFを取得
            </button>
          ) : null}

          {detail && detail.deliveries.length > 0 ? (
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
                    <td>{row.send_status === "unsent" ? "未送信" : row.send_status}</td>
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
          ) : null}

          {detail ? (
            <>
              <label>
                改訂・取消の理由
                <input value={reason} onChange={(event) => setReason(event.target.value)} />
              </label>
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
              <label>
                対応メモ
                <input value={note} onChange={(event) => setNote(event.target.value)} />
              </label>
              <button type="button" className="btn btn-ghost" onClick={() => noteMutation.mutate(detail.id)}>
                メモを追加
              </button>
              {detail.notes.map((item) => (
                <p key={item.id}>
                  {item.author_name}: {item.body}
                </p>
              ))}
            </>
          ) : null}
        </form>
      )}
    </section>
  );
}
