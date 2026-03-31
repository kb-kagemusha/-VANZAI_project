import { Navigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import { SummaryCard } from "../components/SummaryCard";
import { ApiError, confirmPayout, deliverPayout, downloadPayoutPdf, generatePayout, getAssignments, getPayoutDeliveries, getPayouts, getProjects, markPayoutPaid } from "../lib/api/client";
import { currentMonthInput, formatCurrency, formatDateTime, formatPayeeType, formatStatus, toPeriodKey } from "../lib/formatters";
import type { PayoutListItem } from "../types/api";

const PAGE_SIZE = 20;

export function PayoutsPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [status, setStatus] = useState("");
  const [deliveryState, setDeliveryState] = useState("");
  const [missingDefaultRecipientOnly, setMissingDefaultRecipientOnly] = useState(false);
  const [sortBy, setSortBy] = useState("approved_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(0);
  const [genProjectId, setGenProjectId] = useState("");
  const [genWorkerId, setGenWorkerId] = useState("");
  const [genError, setGenError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [selectedDeliveryPayout, setSelectedDeliveryPayout] = useState<PayoutListItem | null>(null);
  const [deliveryRecipientEmail, setDeliveryRecipientEmail] = useState("");
  const [deliveryNote, setDeliveryNote] = useState("");
  const [deliveryInternalNote, setDeliveryInternalNote] = useState("");
  const periodKey = toPeriodKey(monthValue);
  const queryClient = useQueryClient();

  const payoutsQuery = useQuery({
    queryKey: ["payouts", periodKey, status, deliveryState, missingDefaultRecipientOnly, sortBy, sortOrder, page],
    queryFn: () =>
      getPayouts({
        period_key: periodKey,
        status: status || undefined,
        delivery_state: deliveryState || undefined,
        missing_default_recipient_only: missingDefaultRecipientOnly || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  const projectsQuery = useQuery({
    queryKey: ["projects-all"],
    queryFn: () => getProjects({ limit: 200 }),
  });

  const missingRecipientSummaryQuery = useQuery({
    queryKey: ["payouts-missing-default-recipient-summary", periodKey],
    queryFn: () =>
      getPayouts({
        period_key: periodKey,
        missing_default_recipient_only: true,
        offset: 0,
        limit: 1,
      }),
  });

  const payoutDeliveriesQuery = useQuery({
    queryKey: ["payout-deliveries", selectedDeliveryPayout?.id],
    enabled: Boolean(selectedDeliveryPayout?.id),
    queryFn: () => getPayoutDeliveries(selectedDeliveryPayout?.id ?? ""),
    select: (data) => ({
      items: data.items,
      recentRecipients: Array.from(
        new Set(data.items.map((item) => item.recipient_email.trim()).filter((value) => value.length > 0)),
      ),
    }),
  });

  const assignmentsQuery = useQuery({
    queryKey: ["assignments-gen", genProjectId],
    queryFn: () => getAssignments({ project_id: genProjectId, limit: 200 }),
    enabled: !!genProjectId,
  });

  const generateMutation = useMutation({
    mutationFn: () => generatePayout(genProjectId, genWorkerId, periodKey),
    onSuccess: () => {
      setGenError("");
      void queryClient.invalidateQueries({ queryKey: ["payouts"] });
    },
    onError: (err: unknown) => {
      setGenError(err instanceof ApiError ? err.message : "支払明細の生成に失敗しました");
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (payoutId: string) => confirmPayout(payoutId),
    onSuccess: () => {
      setActionError("");
      setActionMessage("");
      void queryClient.invalidateQueries({ queryKey: ["payouts"] });
    },
    onError: (err: unknown) => {
      setActionMessage("");
      setActionError(err instanceof ApiError ? err.message : "支払確定に失敗しました");
    },
  });

  const paidMutation = useMutation({
    mutationFn: (payoutId: string) => markPayoutPaid(payoutId),
    onSuccess: () => {
      setActionError("");
      setActionMessage("");
      void queryClient.invalidateQueries({ queryKey: ["payouts"] });
    },
    onError: (err: unknown) => {
      setActionMessage("");
      setActionError(err instanceof ApiError ? err.message : "支払済み更新に失敗しました");
    },
  });

  const deliverMutation = useMutation({
    mutationFn: ({
      payoutId,
      recipientEmail,
      note,
      internalNote,
    }: {
      payoutId: string;
      recipientEmail?: string;
      note?: string;
      internalNote?: string;
    }) =>
      deliverPayout(payoutId, {
        recipientEmail,
        deliveryNote: note,
        internalNote,
      }),
    onSuccess: (delivery) => {
      setActionError("");
      setActionMessage(`${delivery.recipient_email} へ支払明細を送信しました`);
      setDeliveryRecipientEmail("");
      setDeliveryNote("");
      setDeliveryInternalNote("");
      void queryClient.invalidateQueries({ queryKey: ["payouts"] });
      void queryClient.invalidateQueries({ queryKey: ["payout-deliveries"] });
    },
    onError: (err: unknown) => {
      setActionMessage("");
      setActionError(err instanceof ApiError ? err.message : "支払明細送信に失敗しました");
    },
  });

  // 稼働者のユニーク一覧
  const workerOptions = Array.from(
    new Map((assignmentsQuery.data?.items ?? []).map((a) => [a.worker_id, a.worker_name])).entries(),
  );

  const toggleDeliveryHistory = (row: PayoutListItem) => {
    setSelectedDeliveryPayout((current) => {
      const next = current?.id === row.id ? null : row;
      setDeliveryRecipientEmail("");
      setDeliveryNote("");
      setDeliveryInternalNote("");
      return next;
    });
  };

  const sendPayoutDelivery = (payoutId: string, recipientEmail?: string) => {
    setActionError("");
    setActionMessage("");
    deliverMutation.mutate({
      payoutId,
      recipientEmail: recipientEmail?.trim() || undefined,
      note: deliveryNote.trim() || undefined,
      internalNote: deliveryInternalNote.trim() || undefined,
    });
  };

  const defaultRecipientLabel = selectedDeliveryPayout
    ? selectedDeliveryPayout.payee_type === "worker"
      ? "稼働者メール"
      : selectedDeliveryPayout.payee_type === "supplier"
        ? "取引先メール"
        : "既定メール"
    : "既定メール";

  const deliveryRecipientCandidates = selectedDeliveryPayout
    ? [
        ...(selectedDeliveryPayout.default_recipient_email
          ? [
              {
                email: selectedDeliveryPayout.default_recipient_email,
                sourceLabel: defaultRecipientLabel,
                sourceType: "default",
              },
            ]
          : []),
        ...((payoutDeliveriesQuery.data?.recentRecipients ?? [])
          .filter((email) => email !== selectedDeliveryPayout.default_recipient_email)
          .map((email) => ({
            email,
            sourceLabel: "履歴送信先",
            sourceType: "history",
          }))),
      ]
    : [];

  if (payoutsQuery.isLoading) {
    return <LoadingOverlay label="支払一覧を読み込み中..." />;
  }

  if (payoutsQuery.error instanceof ApiError && payoutsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (payoutsQuery.isError || !payoutsQuery.data) {
    return <ErrorState title="支払一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="支払一覧" description="支払明細の相手先、版、承認・支払日時を参照します。" />

      {/* 支払明細生成フォーム */}
      <section className="card" style={{ padding: "1rem", display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "flex-end" }}>
        <strong style={{ width: "100%" }}>支払明細を生成</strong>
        <label>
          案件
          <select value={genProjectId} onChange={(e) => { setGenProjectId(e.target.value); setGenWorkerId(""); }}>
            <option value="">案件を選択</option>
            {(projectsQuery.data?.items ?? []).map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
        <label>
          稼働者
          <select value={genWorkerId} onChange={(e) => setGenWorkerId(e.target.value)} disabled={!genProjectId}>
            <option value="">稼働者を選択</option>
            {workerOptions.map(([id, name]) => (
              <option key={id} value={id}>{name}</option>
            ))}
          </select>
        </label>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(e) => { setMonthValue(e.target.value); setPage(0); }} />
        </label>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={!genProjectId || !genWorkerId || generateMutation.isPending}
        >
          {generateMutation.isPending ? "生成中..." : "支払明細生成"}
        </button>
        {genError && <span style={{ color: "var(--color-danger, red)", fontSize: "0.875rem" }}>{genError}</span>}
        {generateMutation.isSuccess && <span style={{ color: "green", fontSize: "0.875rem" }}>生成しました</span>}
      </section>

      {actionError ? <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>{actionError}</p> : null}
      {actionMessage ? <p style={{ margin: 0, color: "var(--color-success, #067647)" }}>{actionMessage}</p> : null}

      <section className="summary-grid">
        <SummaryCard label="対象月の支払件数" value={payoutsQuery.data.total} accent="#2a6f97" />
        <SummaryCard
          label="送信先未設定支払"
          value={missingRecipientSummaryQuery.data?.total ?? 0}
          accent="#b42318"
        />
      </section>

      <FilterBar>
        <label>
          対象月
          <input type="month" value={monthValue} onChange={(event) => { setMonthValue(event.target.value); setPage(0); }} />
        </label>
        <label>
          ステータス
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="preparing">準備中</option>
            <option value="approved">承認済み</option>
            <option value="paid">支払済み</option>
          </select>
        </label>
        <label>
          送信状態
          <select value={deliveryState} onChange={(event) => { setDeliveryState(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="unsent">未送信</option>
            <option value="failed">送信失敗のみ</option>
          </select>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input
            type="checkbox"
            checked={missingDefaultRecipientOnly}
            onChange={(event) => {
              setMissingDefaultRecipientOnly(event.target.checked);
              setPage(0);
            }}
          />
          既定送信先未設定のみ
        </label>
        <label>
          ソート
          <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(0); }}>
            <option value="approved_at">承認日時</option>
            <option value="paid_at">支払日時</option>
            <option value="payee_name">支払先名</option>
            <option value="total_amount">合計金額</option>
            <option value="version">版</option>
          </select>
        </label>
        <label>
          順序
          <select value={sortOrder} onChange={(event) => { setSortOrder(event.target.value); setPage(0); }}>
            <option value="desc">降順</option>
            <option value="asc">昇順</option>
          </select>
        </label>
      </FilterBar>

      <DataTable
        columns={[
          { key: "number", header: "支払番号", render: (row) => row.payout_number },
          { key: "payee", header: "支払先", render: (row) => row.payee_name },
          { key: "type", header: "種別", render: (row) => formatPayeeType(row.payee_type) },
          { key: "project", header: "案件", render: (row) => row.project_name || "-" },
          { key: "period", header: "対象月", render: (row) => row.period_key },
          { key: "version", header: "版", render: (row) => row.version },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
          { key: "amount", header: "合計", render: (row) => formatCurrency(row.total_amount) },
          {
            key: "pdf_storage",
            header: "PDF保存先",
            render: (row) => (row.pdf_storage_key ? row.pdf_storage_key : row.status === "preparing" ? "未生成" : "未保存"),
          },
          {
            key: "delivery_status",
            header: "最終送信",
            render: (row) => row.last_delivery_status ? `${formatStatus(row.last_delivery_status)} / ${formatDateTime(row.last_delivered_at)} / ${row.last_delivery_recipient || "-"}` : "-",
          },
          {
            key: "default_recipient",
            header: "既定送信先",
            render: (row) => row.default_recipient_email ? row.default_recipient_email : <span style={{ color: "var(--color-danger, #b42318)", fontWeight: 600 }}>未設定</span>,
          },
          { key: "approved", header: "承認日時", render: (row) => formatDateTime(row.approved_at) },
          { key: "paid", header: "支払日時", render: (row) => formatDateTime(row.paid_at) },
          {
            key: "actions",
            header: "操作",
            render: (row) => (
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {row.status === "preparing" ? (
                  <button
                    onClick={() => {
                      setActionError("");
                      setActionMessage("");
                      confirmMutation.mutate(row.id);
                    }}
                    disabled={confirmMutation.isPending || paidMutation.isPending}
                    style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                  >
                    確定
                  </button>
                ) : null}
                {row.status === "approved" ? (
                  <button
                    onClick={() => {
                      setActionError("");
                      setActionMessage("");
                      paidMutation.mutate(row.id);
                    }}
                    disabled={confirmMutation.isPending || paidMutation.isPending}
                    style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                  >
                    支払済み
                  </button>
                ) : null}
                {row.status !== "preparing" ? (
                  <button
                    onClick={() => toggleDeliveryHistory(row)}
                    style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                  >
                    {selectedDeliveryPayout?.id === row.id ? "履歴を閉じる" : "履歴"}
                  </button>
                ) : null}
                {row.status !== "preparing" ? (
                  <button
                    onClick={() => {
                      sendPayoutDelivery(row.id);
                    }}
                    disabled={confirmMutation.isPending || paidMutation.isPending || deliverMutation.isPending}
                    style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                  >
                    既定送信
                  </button>
                ) : null}
                {row.status !== "preparing" ? (
                  <button
                    onClick={() => {
                      void downloadPayoutPdf(row.id).catch((err: unknown) => {
                        setActionError(err instanceof ApiError ? err.message : "支払明細PDFのダウンロードに失敗しました");
                      });
                    }}
                    style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                  >
                    PDF
                  </button>
                ) : null}
              </div>
            ),
          },
        ]}
        rows={payoutsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="支払明細はありません"
        emptyDescription="条件に一致する支払明細は見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={payoutsQuery.data.total}
        limit={payoutsQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />

      {selectedDeliveryPayout ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
            <div style={{ display: "grid", gap: "0.2rem" }}>
              <strong>送信履歴</strong>
              <span style={{ color: "var(--color-text-subtle, #667085)", fontSize: "0.9rem" }}>
                {selectedDeliveryPayout.payout_number} / {selectedDeliveryPayout.payee_name} / {selectedDeliveryPayout.period_key}
              </span>
            </div>
            <button
              onClick={() => {
                setSelectedDeliveryPayout(null);
                setDeliveryRecipientEmail("");
              }}
              style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
            >
              閉じる
            </button>
          </div>

          <div style={{ display: "grid", gap: "0.5rem", padding: "0.75rem", border: "1px solid var(--color-border-muted, #d0d5dd)", borderRadius: "0.75rem" }}>
            <strong>宛先上書き送信</strong>
            <div style={{ display: "grid", gap: "0.25rem" }}>
              <span style={{ color: "var(--color-text-subtle, #667085)", fontSize: "0.9rem" }}>既定送信先</span>
              <span>
                {selectedDeliveryPayout.default_recipient_email
                  ? `${selectedDeliveryPayout.payee_name} / ${defaultRecipientLabel} / ${selectedDeliveryPayout.default_recipient_email}`
                  : `${selectedDeliveryPayout.payee_name} の既定メールは未設定です`}
              </span>
            </div>
            <div style={{ display: "grid", gap: "0.4rem" }}>
              <span style={{ color: "var(--color-text-subtle, #667085)", fontSize: "0.9rem" }}>送信候補</span>
              {deliveryRecipientCandidates.length > 0 ? (
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  {deliveryRecipientCandidates.map((candidate) => (
                    <button
                      key={`${candidate.sourceType}:${candidate.email}`}
                      type="button"
                      onClick={() => setDeliveryRecipientEmail(candidate.email)}
                      style={{
                        fontSize: "0.8rem",
                        padding: "0.35rem 0.6rem",
                        borderRadius: "999px",
                        border: "1px solid var(--color-border-muted, #d0d5dd)",
                        background: deliveryRecipientEmail === candidate.email ? "var(--color-surface-muted, #eff8ff)" : "transparent",
                      }}
                    >
                      {candidate.sourceLabel}: {candidate.email}
                    </button>
                  ))}
                </div>
              ) : (
                <span style={{ color: "var(--color-text-subtle, #667085)", fontSize: "0.9rem" }}>
                  既定送信先または過去送信先の候補はまだありません。
                </span>
              )}
            </div>
            <label style={{ display: "grid", gap: "0.25rem" }}>
              送信先メールアドレス
              <input
                type="email"
                value={deliveryRecipientEmail}
                onChange={(event) => setDeliveryRecipientEmail(event.target.value)}
                placeholder="空欄なら既定宛先へ送信"
              />
            </label>
            <label style={{ display: "grid", gap: "0.25rem" }}>
              送信理由メモ
              <textarea
                value={deliveryNote}
                onChange={(event) => setDeliveryNote(event.target.value)}
                placeholder="再送理由や伝達メモを残す場合に入力"
                rows={2}
              />
            </label>
            <label style={{ display: "grid", gap: "0.25rem" }}>
              内部メモ
              <textarea
                value={deliveryInternalNote}
                onChange={(event) => setDeliveryInternalNote(event.target.value)}
                placeholder="社内向けの判断メモを履歴に残す場合に入力"
                rows={2}
              />
            </label>
            <span style={{ color: "var(--color-text-subtle, #667085)", fontSize: "0.9rem" }}>
              空欄の場合は上記の既定送信先を使用します。
            </span>
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <button
                onClick={() => sendPayoutDelivery(selectedDeliveryPayout.id, deliveryRecipientEmail)}
                disabled={deliverMutation.isPending}
                style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
              >
                {deliverMutation.isPending ? "送信中..." : "この宛先で送信"}
              </button>
              <button
                onClick={() => sendPayoutDelivery(selectedDeliveryPayout.id)}
                disabled={deliverMutation.isPending || !selectedDeliveryPayout.default_recipient_email}
                style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
              >
                既定送信先へ送信
              </button>
              <button
                onClick={() => setDeliveryRecipientEmail("")}
                disabled={deliverMutation.isPending || !deliveryRecipientEmail}
                style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
              >
                入力をクリア
              </button>
            </div>
          </div>

          {payoutDeliveriesQuery.isLoading ? <p style={{ margin: 0 }}>送信履歴を読み込み中...</p> : null}
          {payoutDeliveriesQuery.isError ? <p className="form-error">送信履歴の取得に失敗しました</p> : null}
          {!payoutDeliveriesQuery.isLoading && !payoutDeliveriesQuery.isError && (payoutDeliveriesQuery.data?.items.length ?? 0) === 0 ? (
            <p style={{ margin: 0, color: "var(--color-text-subtle, #667085)" }}>送信履歴はまだありません。</p>
          ) : null}
          {!payoutDeliveriesQuery.isLoading && !payoutDeliveriesQuery.isError && (payoutDeliveriesQuery.data?.items.length ?? 0) > 0 ? (
            <DataTable
              columns={[
                { key: "status", header: "状態", render: (row) => formatStatus(row.status) },
                { key: "recipient", header: "送信先", render: (row) => row.recipient_email },
                { key: "provider", header: "プロバイダ", render: (row) => row.provider || "-" },
                { key: "sent_at", header: "送信日時", render: (row) => formatDateTime(row.sent_at) },
                { key: "operator", header: "実行者", render: (row) => row.delivered_by || "-" },
                { key: "pdf", header: "PDF保存先", render: (row) => row.pdf_storage_key || "-" },
                { key: "note", header: "送信理由メモ", render: (row) => row.delivery_note || "-" },
                { key: "internal_note", header: "内部メモ", render: (row) => row.internal_note || "-" },
                { key: "error", header: "エラー", render: (row) => row.error_message || "-" },
              ]}
              rows={payoutDeliveriesQuery.data?.items ?? []}
              getRowKey={(row) => row.id}
              emptyTitle="送信履歴はありません"
              emptyDescription="この支払明細の送信履歴はまだありません。"
            />
          ) : null}
        </section>
      ) : null}
    </div>
  );
}