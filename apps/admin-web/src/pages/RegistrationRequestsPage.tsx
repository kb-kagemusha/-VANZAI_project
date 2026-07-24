import { Navigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import {
  ApiError,
  approveRegistrationRequest,
  createRegistrationLink,
  downloadRegistrationRequestFile,
  getRegistrationRequest,
  getRegistrationRequests,
  reissueRegistrationLink,
  rejectRegistrationRequest,
  resetRegistrationLinkPinLock,
} from "../lib/api/client";
import type { RegistrationLinkCreateRequest, RegistrationRequestDetailResponse } from "../types/api";
import { formatDateTime } from "../lib/formatters";

const PAGE_SIZE = 20;

const REQUEST_TYPE_LABELS: Record<string, string> = {
  worker: "稼働者",
  supplier_individual: "個人下請け",
  supplier_corporation: "法人下請け",
  introducer_identity: "紹介者本人確認",
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  public_form: "公開フォーム",
  admin_proxy: "管理代行",
  api_import: "API取込",
  internal_create: "内部作成",
};

function formatRequestType(value: string) {
  return REQUEST_TYPE_LABELS[value] || value;
}

function formatSourceType(value: string) {
  return SOURCE_TYPE_LABELS[value] || value;
}

function formatDetailValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "boolean") {
    return value ? "はい" : "いいえ";
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return String(value);
}

export function RegistrationRequestsPage() {
  const [page, setPage] = useState(0);
  const [requestType, setRequestType] = useState("");
  const [status, setStatus] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [search, setSearch] = useState("");
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [approvalNotes, setApprovalNotes] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [rejectNotes, setRejectNotes] = useState("");
  const [dedupeResolution, setDedupeResolution] = useState<"" | "create_new" | "merge_existing">("");
  const [approvedTargetId, setApprovedTargetId] = useState("");
  const [linkRequestType, setLinkRequestType] = useState<RegistrationLinkCreateRequest["request_type"]>("worker");
  const [linkExpiresInDays, setLinkExpiresInDays] = useState("7");
  const [linkNotes, setLinkNotes] = useState("");
  const [fileDownloadReason, setFileDownloadReason] = useState("");
  const [lastIssuedLink, setLastIssuedLink] = useState<{ url: string; pin: string; requestId: string } | null>(null);
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ["registration-requests", requestType, status, sourceType, search, page],
    queryFn: () =>
      getRegistrationRequests({
        request_type: requestType || undefined,
        status: status || undefined,
        source_type: sourceType || undefined,
        search: search || undefined,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
        sort_by: "created_at",
        sort_order: "desc",
      }),
  });

  useEffect(() => {
    const items = listQuery.data?.items || [];
    if (items.length === 0) {
      setSelectedRequestId(null);
      return;
    }
    if (!selectedRequestId || !items.some((item) => item.id === selectedRequestId)) {
      setSelectedRequestId(items[0].id);
    }
  }, [listQuery.data, selectedRequestId]);

  const detailQuery = useQuery({
    queryKey: ["registration-request", selectedRequestId],
    queryFn: () => getRegistrationRequest(selectedRequestId || ""),
    enabled: Boolean(selectedRequestId),
  });

  useEffect(() => {
    const detail = detailQuery.data;
    if (!detail) {
      return;
    }
    setApprovalNotes("");
    setRejectReason("");
    setRejectNotes("");
    if (detail.dedupe_candidates.length === 0) {
      setDedupeResolution("create_new");
      setApprovedTargetId("");
    } else {
      setDedupeResolution("");
      setApprovedTargetId("");
    }
  }, [detailQuery.data?.id]);

  const createLinkMutation = useMutation({
    mutationFn: (body: RegistrationLinkCreateRequest) => createRegistrationLink(body),
    onSuccess: async (result) => {
      setActionError("");
      setActionMessage("公開登録リンクを作成しました。");
      setLastIssuedLink({ url: result.public_form_url, pin: result.access_pin, requestId: result.request_id });
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
    },
    onError: (error) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "公開登録リンク作成に失敗しました。");
    },
  });

  const approveMutation = useMutation({
    mutationFn: (detail: RegistrationRequestDetailResponse) =>
      approveRegistrationRequest(detail.id, {
        approved_target_id: dedupeResolution === "merge_existing" ? approvedTargetId || null : null,
        dedupe_resolution: dedupeResolution || null,
        notes: approvalNotes.trim() || null,
      }),
    onSuccess: async () => {
      setActionError("");
      setActionMessage("登録申請を承認しました。");
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["registration-request", selectedRequestId] });
    },
    onError: (error) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "登録申請承認に失敗しました。");
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (detail: RegistrationRequestDetailResponse) =>
      rejectRegistrationRequest(detail.id, {
        reason: rejectReason.trim(),
        notes: rejectNotes.trim() || null,
      }),
    onSuccess: async () => {
      setActionError("");
      setActionMessage("登録申請を却下しました。");
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["registration-request", selectedRequestId] });
    },
    onError: (error) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "登録申請却下に失敗しました。");
    },
  });

  const resetPinLockMutation = useMutation({
    mutationFn: (requestId: string) => resetRegistrationLinkPinLock(requestId),
    onSuccess: async () => {
      setActionError("");
      setActionMessage("PIN ロックを解除しました。");
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["registration-request", selectedRequestId] });
    },
    onError: (error) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "PIN ロック解除に失敗しました。");
    },
  });

  const reissueMutation = useMutation({
    mutationFn: (detail: RegistrationRequestDetailResponse) =>
      reissueRegistrationLink(detail.id, {
        request_type: detail.request_type as RegistrationLinkCreateRequest["request_type"],
        expires_in_days: Number(linkExpiresInDays) || 7,
        notes: linkNotes.trim() || null,
      }),
    onSuccess: async (result) => {
      setActionError("");
      setActionMessage("公開登録リンクを再発行しました。");
      setLastIssuedLink({ url: result.public_form_url, pin: result.access_pin, requestId: result.request_id });
      await queryClient.invalidateQueries({ queryKey: ["registration-requests"] });
      await queryClient.invalidateQueries({ queryKey: ["registration-request", selectedRequestId] });
    },
    onError: (error) => {
      setActionMessage("");
      setActionError(error instanceof ApiError ? error.message : "公開登録リンク再発行に失敗しました。");
    },
  });

  if (listQuery.isLoading) {
    return <LoadingOverlay label="登録申請を読み込み中..." />;
  }

  if (listQuery.error instanceof ApiError && listQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (listQuery.isError || !listQuery.data) {
    return <ErrorState title="登録申請の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  const selectedDetail = detailQuery.data;
  const approvalDisabled = !selectedDetail
    || selectedDetail.status !== "pending"
    || approveMutation.isPending
    || (selectedDetail.dedupe_candidates.length > 0 && (!dedupeResolution || (dedupeResolution === "merge_existing" && !approvedTargetId)));
  const rejectDisabled = !selectedDetail || selectedDetail.status !== "pending" || rejectMutation.isPending || rejectReason.trim().length === 0;
  const selectedCandidate = selectedDetail?.dedupe_candidates.find((candidate) => candidate.target_id === approvedTargetId) || null;

  return (
    <div className="page-stack">
      <PageHeader title="登録申請" description="公開リンク発行、未審査 request の差分確認、承認・却下を管理します。" eyebrow="承認フロー" />
      {actionError ? <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>{actionError}</p> : null}
      {actionMessage ? <p style={{ margin: 0, color: "var(--color-success, #027a48)" }}>{actionMessage}</p> : null}

      <section className="upload-card registration-link-card" style={{ display: "grid", gap: "1rem" }}>
        <h3 style={{ margin: 0 }}>公開登録リンク発行</h3>
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label>
            申請種別
            <select
              value={linkRequestType}
              onChange={(event) => setLinkRequestType(event.target.value as RegistrationLinkCreateRequest["request_type"])}
              style={{ minWidth: 0, width: "100%" }}
            >
              <option value="worker">稼働者</option>
              <option value="supplier_individual">個人下請け</option>
              <option value="supplier_corporation">法人下請け</option>
              <option value="introducer_identity">紹介者本人確認</option>
            </select>
          </label>
          <label>
            有効日数
            <input
              type="number"
              min={1}
              max={30}
              value={linkExpiresInDays}
              onChange={(event) => setLinkExpiresInDays(event.target.value)}
              style={{ minWidth: 0, width: "100%" }}
            />
          </label>
          <label style={{ gridColumn: "1 / -1" }}>
            メモ
            <input
              value={linkNotes}
              onChange={(event) => setLinkNotes(event.target.value)}
              placeholder="送付先や用途メモ"
              style={{ minWidth: 0, width: "100%" }}
            />
          </label>
        </div>
        <div className="registration-action-row">
          <button
            type="button"
            className="btn btn-primary registration-action-button"
            onClick={() => createLinkMutation.mutate({ request_type: linkRequestType, expires_in_days: Number(linkExpiresInDays) || 7, notes: linkNotes.trim() || null })}
            disabled={createLinkMutation.isPending}
          >
            リンク発行
          </button>
          {lastIssuedLink ? (
            <button
              type="button"
              className="btn btn-ghost registration-action-button"
              onClick={() => {
                void navigator.clipboard.writeText(`${window.location.origin}${lastIssuedLink.url}\nPIN: ${lastIssuedLink.pin}`)
                  .then(() => setActionMessage("リンクと PIN をクリップボードにコピーしました。"))
                  .catch(() => setActionError("クリップボードへのコピーに失敗しました。"));
              }}
            >
              直近リンクをコピー
            </button>
          ) : null}
        </div>
        {lastIssuedLink ? (
          <div style={{ display: "grid", gap: "0.35rem", fontSize: "0.95rem" }}>
            <div style={{ wordBreak: "break-all" }}>URL: {window.location.origin}{lastIssuedLink.url}</div>
            <div>PIN: {lastIssuedLink.pin}</div>
            <div>request_id: {lastIssuedLink.requestId}</div>
          </div>
        ) : null}
      </section>

      <FilterBar>
        <label>
          申請種別
          <select value={requestType} onChange={(event) => { setRequestType(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="worker">稼働者</option>
            <option value="supplier_individual">個人下請け</option>
            <option value="supplier_corporation">法人下請け</option>
            <option value="introducer_identity">紹介者本人確認</option>
          </select>
        </label>
        <label>
          状態
          <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="link_issued">リンク発行済み</option>
            <option value="pending">未審査</option>
            <option value="approved">承認済み</option>
            <option value="rejected">却下</option>
          </select>
        </label>
        <label>
          受付経路
          <select value={sourceType} onChange={(event) => { setSourceType(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="public_form">公開フォーム</option>
            <option value="admin_proxy">管理代行</option>
            <option value="api_import">API取込</option>
            <option value="internal_create">内部作成</option>
          </select>
        </label>
        <label>
          検索
          <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="dedupe key / notes" />
        </label>
      </FilterBar>

      <DataTable
        columns={[
          {
            key: "select",
            header: "表示",
            render: (row) => (
              <button
                type="button"
                className={`btn ${selectedRequestId === row.id ? "btn-primary" : "btn-ghost"} btn-sm`}
                onClick={() => setSelectedRequestId(row.id)}
              >
                {selectedRequestId === row.id ? "選択中" : "表示"}
              </button>
            ),
          },
          { key: "summary", header: "申請名", render: (row) => row.summary_name || "-" },
          { key: "type", header: "種別", render: (row) => formatRequestType(row.request_type) },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
          { key: "source", header: "経路", render: (row) => formatSourceType(row.source_type) },
          { key: "submitted", header: "送信日時", render: (row) => formatDateTime(row.submitted_at) },
          { key: "expires", header: "期限", render: (row) => formatDateTime(row.expires_at) },
          { key: "dedupe", header: "dedupe", render: (row) => row.dedupe_key || "-" },
        ]}
        rows={listQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="登録申請はありません"
        emptyDescription="条件に一致する登録申請は見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={listQuery.data.total}
        limit={listQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />

      {detailQuery.isLoading ? <LoadingOverlay label="申請詳細を読み込み中..." /> : null}
      {selectedDetail ? (
        <section className="table-card registration-request-detail" style={{ display: "grid", gap: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
            <div>
              <h3 style={{ margin: 0 }}>{selectedDetail.summary_name || "申請詳細"}</h3>
              <p style={{ margin: "0.25rem 0 0", color: "var(--color-text-muted, #475467)" }}>
                {formatRequestType(selectedDetail.request_type)} / {formatSourceType(selectedDetail.source_type)}
              </p>
            </div>
            <StatusBadge value={selectedDetail.status} />
          </div>

          <div style={{ display: "grid", gap: "0.5rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
            <div>送信日時: {formatDateTime(selectedDetail.submitted_at)}</div>
            <div>審査日時: {formatDateTime(selectedDetail.reviewed_at)}</div>
            <div>審査者: {selectedDetail.reviewed_by_name || selectedDetail.reviewed_by || "-"}</div>
            <div>期限: {formatDateTime(selectedDetail.expires_at)}</div>
            <div>failed_attempts: {selectedDetail.failed_attempts}</div>
            <div>approved_target: {selectedDetail.approved_target_type && selectedDetail.approved_target_id ? `${selectedDetail.approved_target_type}:${selectedDetail.approved_target_id}` : "-"}</div>
          </div>

          <div>
            <h4 style={{ margin: "0 0 0.5rem" }}>申請データ</h4>
            <div style={{ display: "grid", gap: "0.35rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
              {Object.entries(selectedDetail.detail_data || {}).map(([key, value]) => (
                <div key={key} style={{ padding: "0.5rem 0.75rem", border: "1px solid var(--color-border-subtle, #d0d5dd)", borderRadius: "0.5rem" }}>
                  <strong style={{ display: "block", marginBottom: "0.25rem" }}>{key}</strong>
                  <span>{formatDetailValue(value)}</span>
                </div>
              ))}
            </div>
          </div>

          <div>
            <h4 style={{ margin: "0 0 0.5rem" }}>重複候補</h4>
            {selectedDetail.dedupe_candidates.length === 0 ? (
              <p style={{ margin: 0 }}>重複候補はありません。</p>
            ) : (
              <div style={{ display: "grid", gap: "0.75rem" }}>
                <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input type="radio" checked={dedupeResolution === "create_new"} onChange={() => { setDedupeResolution("create_new"); setApprovedTargetId(""); }} />
                  新規 master として承認
                </label>
                {selectedDetail.dedupe_candidates.map((candidate) => (
                  <label key={candidate.target_id} style={{ display: "grid", gap: "0.25rem", padding: "0.75rem", border: "1px solid var(--color-border-subtle, #d0d5dd)", borderRadius: "0.5rem" }}>
                    <span style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                      <input
                        type="radio"
                        checked={dedupeResolution === "merge_existing" && approvedTargetId === candidate.target_id}
                        onChange={() => { setDedupeResolution("merge_existing"); setApprovedTargetId(candidate.target_id); }}
                      />
                      {candidate.display_name} ({candidate.target_type})
                    </span>
                    <span>一致理由: {candidate.match_reasons.join(" / ")}</span>
                    <span>電話: {candidate.phone || "-"} / Email: {candidate.email || "-"}</span>
                    <span>備考: {candidate.notes || "-"}</span>
                  </label>
                ))}
                {selectedCandidate ? (
                  <div style={{ display: "grid", gap: "0.5rem", marginTop: "0.5rem" }}>
                    <h5 style={{ margin: 0 }}>差分比較</h5>
                    {selectedCandidate.field_differences.map((difference) => (
                      <div
                        key={difference.field_name}
                        style={{
                          display: "grid",
                          gap: "0.25rem",
                          padding: "0.75rem",
                          border: "1px solid var(--color-border-subtle, #d0d5dd)",
                          borderRadius: "0.5rem",
                          background: difference.is_match ? "rgba(18, 183, 106, 0.06)" : "rgba(217, 45, 32, 0.06)",
                        }}
                      >
                        <strong>{difference.field_label}</strong>
                        <span>申請値: {difference.request_value || "-"}</span>
                        <span>既存値: {difference.existing_value || "-"}</span>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            )}
          </div>

          <div style={{ display: "grid", gap: "0.75rem" }}>
            <h4 style={{ margin: 0 }}>添付ファイル</h4>
            <label>
              閲覧理由
              <input value={fileDownloadReason} onChange={(event) => setFileDownloadReason(event.target.value)} placeholder="確認理由を入力" />
            </label>
            {selectedDetail.files.length === 0 ? (
              <p style={{ margin: 0 }}>添付ファイルはありません。</p>
            ) : (
              <div style={{ display: "grid", gap: "0.5rem" }}>
                {selectedDetail.files.map((file) => (
                  <div key={file.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.75rem", padding: "0.75rem", border: "1px solid var(--color-border-subtle, #d0d5dd)", borderRadius: "0.5rem" }}>
                    <div style={{ display: "grid", gap: "0.2rem" }}>
                      <strong>{file.document_type} / {file.document_part}</strong>
                      <span>{file.original_filename}</span>
                      <span>{formatDateTime(file.uploaded_at)}</span>
                    </div>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={!fileDownloadReason.trim()}
                      onClick={() => {
                        setActionError("");
                        void downloadRegistrationRequestFile(selectedDetail.id, file.id, fileDownloadReason.trim()).catch((downloadError: unknown) => {
                          setActionMessage("");
                          setActionError(downloadError instanceof ApiError ? downloadError.message : "添付ファイルのダウンロードに失敗しました。");
                        });
                      }}
                    >
                      ダウンロード
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
            <div style={{ display: "grid", gap: "0.5rem" }}>
              <h4 style={{ margin: 0 }}>承認</h4>
              <textarea rows={4} value={approvalNotes} onChange={(event) => setApprovalNotes(event.target.value)} placeholder="承認メモ" />
              <button className="btn btn-primary registration-action-button" type="button" onClick={() => selectedDetail && approveMutation.mutate(selectedDetail)} disabled={approvalDisabled}>
                承認
              </button>
            </div>

            <div style={{ display: "grid", gap: "0.5rem" }}>
              <h4 style={{ margin: 0 }}>却下</h4>
              <input value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} placeholder="却下理由" />
              <textarea rows={3} value={rejectNotes} onChange={(event) => setRejectNotes(event.target.value)} placeholder="補足メモ" />
              <button className="btn btn-danger registration-action-button" type="button" onClick={() => selectedDetail && rejectMutation.mutate(selectedDetail)} disabled={rejectDisabled}>
                却下
              </button>
            </div>
          </div>

          {selectedDetail.source_type === "public_form" ? (
            <div style={{ display: "grid", gap: "0.75rem" }}>
              <h4 style={{ margin: 0 }}>公開リンク運用</h4>
              <div className="registration-action-row">
                <button className="btn btn-ghost registration-action-button" type="button" onClick={() => resetPinLockMutation.mutate(selectedDetail.id)} disabled={resetPinLockMutation.isPending}>
                  PINロック解除
                </button>
                <button className="btn btn-ghost registration-action-button" type="button" onClick={() => reissueMutation.mutate(selectedDetail)} disabled={reissueMutation.isPending || selectedDetail.status !== "link_issued"}>
                  リンク再発行
                </button>
              </div>
            </div>
          ) : null}

          {selectedDetail.notes ? (
            <div>
              <h4 style={{ margin: "0 0 0.5rem" }}>notes</h4>
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{selectedDetail.notes}</pre>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}