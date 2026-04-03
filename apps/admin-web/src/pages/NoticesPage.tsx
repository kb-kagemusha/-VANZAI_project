/**
 * スタッフ通知管理ページ
 *
 * 管理者・OPS が以下の通知をスタッフへ送信できる
 * - シフト確定通知
 * - 案件変更通知
 * - 一般お知らせ
 *
 * 送信対象:
 * - 全稼働者
 * - 指定案件のアサイン済み稼働者
 * - 個別稼働者（複数ID指定）
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import {
  ApiError,
  createNotice,
  deleteNotice,
  getWorkers,
  listNotices,
} from "../lib/api/client";
import type {
  NoticeCreateRequest,
  NoticeTargetType,
  NoticeType,
  WorkerListItem,
} from "../types/api";
import { formatDateTime } from "../lib/formatters";

const NOTICE_TYPE_LABELS: Record<NoticeType, string> = {
  shift_confirm: "シフト確定",
  project_change: "案件変更",
  general: "一般お知らせ",
};

const TARGET_TYPE_LABELS: Record<NoticeTargetType, string> = {
  all: "全稼働者",
  project: "指定案件",
  worker: "個別指定",
};

const PAGE_SIZE = 20;

const INITIAL_FORM: NoticeCreateRequest = {
  title: "",
  body: "",
  notice_type: "general",
  priority: "normal",
  target_type: "all",
  target_project_id: null,
  target_worker_ids: null,
  send_email: false,
};

export function NoticesPage() {
  const queryClient = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [filterType, setFilterType] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<NoticeCreateRequest>(INITIAL_FORM);
  const [selectedWorkerIds, setSelectedWorkerIds] = useState<string[]>([]);
  const [workerSearch, setWorkerSearch] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  // 全稼働者（アクティブのみ）を50音順で取得
  // フォームが開いた時点でpre-fetch（target_type切り替え前に準備完了させる）
  const { data: workersData, isPending: workersPending, isError: workersError } = useQuery({
    queryKey: ["workers-for-notice"],
    queryFn: () => getWorkers({ is_active: true, limit: 2000 }),
    enabled: showForm,
    staleTime: 60_000,
  });

  const sortedWorkers: WorkerListItem[] = (workersData?.items ?? [])
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name, "ja"));

  const filteredWorkers = workerSearch.trim()
    ? sortedWorkers.filter((w) =>
        w.name.includes(workerSearch.trim())
      )
    : sortedWorkers;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["notices", filterType, offset],
    queryFn: () =>
      listNotices({
        notice_type: filterType || undefined,
        offset,
        limit: PAGE_SIZE,
      }),
  });

  const createMutation = useMutation({
    mutationFn: (req: NoticeCreateRequest) => createNotice(req),
    onSuccess: () => {
      setActionMessage("通知を送信しました。");
      setActionError("");
      setShowForm(false);
      setForm(INITIAL_FORM);
      setSelectedWorkerIds([]);
      setWorkerSearch("");
      queryClient.invalidateQueries({ queryKey: ["notices"] });
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : "送信に失敗しました。");
      setActionMessage("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (noticeId: string) => deleteNotice(noticeId),
    onSuccess: () => {
      setActionMessage("通知を削除しました。");
      setActionError("");
      queryClient.invalidateQueries({ queryKey: ["notices"] });
    },
    onError: (err) => {
      setActionError(err instanceof ApiError ? err.message : "削除に失敗しました。");
      setActionMessage("");
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setActionError("");
    setActionMessage("");

    const req: NoticeCreateRequest = {
      ...form,
      target_worker_ids:
        form.target_type === "worker" && selectedWorkerIds.length > 0
          ? selectedWorkerIds
          : null,
      target_project_id:
        form.target_type === "project" ? form.target_project_id : null,
    };

    createMutation.mutate(req);
  }

  const total = data?.total ?? 0;
  const pages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE);

  return (
    <div className="page-stack" style={{ maxWidth: "1100px", margin: "0 auto" }}>
      <PageHeader
        title="スタッフ通知"
        description="シフト確定・案件変更などをスタッフへ通知します"
      />

      {actionError && (
        <div className="alert alert-error" role="alert">
          {actionError}
        </div>
      )}
      {actionMessage && (
        <div className="alert alert-success" role="status">
          {actionMessage}
        </div>
      )}

      {/* ========== フィルタと新規作成ボタン ========== */}
      <div className="filter-bar" style={{ display: "flex", gap: "1rem", marginBottom: "1rem", alignItems: "center" }}>
        <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          通知種別
          <select
            value={filterType}
            onChange={(e) => { setFilterType(e.target.value); setOffset(0); }}
          >
            <option value="">すべて</option>
            <option value="shift_confirm">シフト確定</option>
            <option value="project_change">案件変更</option>
            <option value="general">一般お知らせ</option>
          </select>
        </label>
        <button
          className="btn btn-primary"
          onClick={() => {
            if (showForm) {
              setSelectedWorkerIds([]);
              setWorkerSearch("");
              setForm(INITIAL_FORM);
            }
            setShowForm((v) => !v);
            setActionError("");
            setActionMessage("");
          }}
        >
          {showForm ? "キャンセル" : "＋ 通知を作成"}
        </button>
      </div>

      {/* ========== 作成フォーム ========== */}
      {showForm && (
        <form
          className="card"
          style={{ marginBottom: "1.5rem", padding: "1.5rem", display: "grid", gap: "1rem" }}
          onSubmit={handleSubmit}
        >
          <h3 style={{ margin: 0 }}>新規通知を作成</h3>

          <label style={{ display: "grid", gap: "0.25rem" }}>
            <span>タイトル <span style={{ color: "red" }}>*</span></span>
            <input
              type="text"
              required
              maxLength={200}
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              placeholder="例: 7月第2週のシフトが確定しました"
            />
          </label>

          <label style={{ display: "grid", gap: "0.25rem" }}>
            <span>本文 <span style={{ color: "red" }}>*</span></span>
            <textarea
              required
              rows={5}
              maxLength={4000}
              value={form.body}
              onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
              placeholder="通知の内容を入力してください"
            />
          </label>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1.4fr", gap: "1rem" }}>
            <label style={{ display: "grid", gap: "0.25rem" }}>
              <span>通知種別</span>
              <select
                value={form.notice_type}
                onChange={(e) => setForm((f) => ({ ...f, notice_type: e.target.value as NoticeType }))}
              >
                <option value="general">一般お知らせ</option>
                <option value="shift_confirm">シフト確定</option>
                <option value="project_change">案件変更</option>
              </select>
            </label>

            <label style={{ display: "grid", gap: "0.25rem" }}>
              <span>優先度</span>
              <select
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value as "normal" | "urgent" }))}
              >
                <option value="normal">通常</option>
                <option value="urgent">緊急</option>
              </select>
            </label>

            <label style={{ display: "grid", gap: "0.25rem" }}>
              <span>送信対象</span>
              <select
                value={form.target_type}
                onChange={(e) => setForm((f) => ({ ...f, target_type: e.target.value as NoticeTargetType }))}
              >
                <option value="all">全稼働者</option>
                <option value="project">指定案件のアサイン済み稼働者</option>
                <option value="worker">個別稼働者指定</option>
              </select>
            </label>
          </div>

          {form.target_type === "project" && (
            <label style={{ display: "grid", gap: "0.25rem" }}>
              <span>案件ID <span style={{ color: "red" }}>*</span></span>
              <input
                type="text"
                value={form.target_project_id ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, target_project_id: e.target.value || null }))}
                placeholder="案件ID を貼り付けてください"
                required={form.target_type === "project"}
              />
            </label>
          )}

          {form.target_type === "worker" && (
            <div style={{ display: "grid", gap: "0.5rem" }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
                <span style={{ fontWeight: 500 }}>
                  稼働者を選択 <span style={{ color: "red" }}>*</span>
                </span>
                {selectedWorkerIds.length > 0 && (
                  <span style={{ fontSize: "0.8em", color: "var(--color-primary, #1565c0)" }}>
                    {selectedWorkerIds.length}名選択中
                  </span>
                )}
                {selectedWorkerIds.length > 0 && (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    style={{ fontSize: "0.75em", padding: "0 0.4rem" }}
                    onClick={() => setSelectedWorkerIds([])}
                  >
                    選択解除
                  </button>
                )}
              </div>
              <input
                type="text"
                placeholder="名前で絞り込み..."
                value={workerSearch}
                onChange={(e) => setWorkerSearch(e.target.value)}
                style={{ width: "100%" }}
              />
              <div
                style={{
                  border: "1px solid #ccc",
                  borderRadius: "4px",
                  maxHeight: "240px",
                  overflowY: "auto",
                  padding: "0.25rem 0",
                }}
              >
                {workersPending && (
                  <div style={{ padding: "0.75rem 1rem", color: "#888" }}>読み込み中...</div>
                )}
                {workersError && (
                  <div style={{ padding: "0.75rem 1rem", color: "var(--color-error, #d32f2f)" }}>
                    稼働者の取得に失敗しました。ページを再読み込みしてください。
                  </div>
                )}
                {!workersPending && !workersError && filteredWorkers.length === 0 && (
                  <div style={{ padding: "0.75rem 1rem", color: "#888" }}>
                    {workerSearch ? "一致する稼働者はいません" : "稼働者がいません"}
                  </div>
                )}
                {filteredWorkers.map((w) => {
                  const checked = selectedWorkerIds.includes(w.id);
                  return (
                    <label
                      key={w.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.6rem",
                        padding: "0.45rem 0.75rem",
                        cursor: "pointer",
                        background: checked ? "var(--color-primary-subtle, #e3f2fd)" : undefined,
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() =>
                          setSelectedWorkerIds((ids) =>
                            checked
                              ? ids.filter((id) => id !== w.id)
                              : [...ids, w.id]
                          )
                        }
                      />
                      <span style={{ flex: 1 }}>{w.name}</span>
                      {w.email && (
                        <span style={{ fontSize: "0.78em", color: "#666" }}>{w.email}</span>
                      )}
                    </label>
                  );
                })}
              </div>
              {form.target_type === "worker" && selectedWorkerIds.length === 0 && (
                <span style={{ fontSize: "0.8em", color: "var(--color-error, #d32f2f)" }}>
                  1名以上選択してください
                </span>
              )}
            </div>
          )}

          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={form.send_email}
              onChange={(e) => setForm((f) => ({ ...f, send_email: e.target.checked }))}
            />
            <span>メールでも送信する</span>
          </label>

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={
                createMutation.isPending ||
                (form.target_type === "worker" && selectedWorkerIds.length === 0)
              }
            >
              {createMutation.isPending ? "送信中..." : "送信"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                setShowForm(false);
                setForm(INITIAL_FORM);
                setSelectedWorkerIds([]);
                setWorkerSearch("");
              }}
            >
              キャンセル
            </button>
          </div>
        </form>
      )}

      {/* ========== 通知一覧 ========== */}
      {isLoading && <LoadingOverlay />}
      {isError && <ErrorState title="エラー" description="通知一覧の取得に失敗しました。" />}

      {data && data.items.length === 0 && !isLoading && (
        <EmptyState title="通知なし" description="通知がありません。" />
      )}

      {data && data.items.length > 0 && (
        <div className="card" style={{ overflow: "auto" }}>
          <table className="data-table" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th>タイトル</th>
                <th>種別</th>
                <th>優先度</th>
                <th>対象</th>
                <th>メール</th>
                <th>既読数</th>
                <th>作成者</th>
                <th>作成日時</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((n) => (
                <tr key={n.id} style={{ opacity: n.deleted_at ? 0.45 : 1 }}>
                  <td>
                    {n.priority === "urgent" && (
                      <span style={{ color: "var(--color-error, #d32f2f)", fontWeight: 700, marginRight: "0.25rem" }}>
                        【緊急】
                      </span>
                    )}
                    {n.title}
                  </td>
                  <td>{NOTICE_TYPE_LABELS[n.notice_type as NoticeType] ?? n.notice_type}</td>
                  <td>{n.priority === "urgent" ? "緊急" : "通常"}</td>
                  <td>
                    {TARGET_TYPE_LABELS[n.target_type as NoticeTargetType] ?? n.target_type}
                    {n.target_project_name && (
                      <span style={{ marginLeft: "0.25rem", fontSize: "0.8em", color: "#555" }}>
                        ({n.target_project_name})
                      </span>
                    )}
                  </td>
                  <td>{n.send_email ? (n.sent_at ? `送信済 ${formatDateTime(n.sent_at)}` : "予定あり") : "—"}</td>
                  <td>{n.read_count}</td>
                  <td>{n.created_by_name ?? "—"}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{formatDateTime(n.created_at)}</td>
                  <td>
                    {!n.deleted_at && (
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ color: "var(--color-error, #d32f2f)" }}
                        onClick={() => {
                          if (confirm(`「${n.title}」を削除しますか？`)) {
                            deleteMutation.mutate(n.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        削除
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ========== ページング ========== */}
      {pages > 1 && (
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "1rem", justifyContent: "center" }}>
          <button
            className="btn btn-ghost btn-sm"
            disabled={currentPage === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            前へ
          </button>
          <span style={{ lineHeight: "2" }}>
            {currentPage + 1} / {pages}ページ（全{total}件）
          </span>
          <button
            className="btn btn-ghost btn-sm"
            disabled={currentPage >= pages - 1}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            次へ
          </button>
        </div>
      )}
    </div>
  );
}
