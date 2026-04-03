/**
 * スタッフ向け通知一覧ページ
 *
 * 管理者から送られたシフト確定・案件変更・一般お知らせを閲覧する。
 * - タップで詳細ドロワーを開く（自動既読はしない）
 * - 「了解しました」ボタンで既読 + unread_count 減少
 * - shift_confirm / project_change では「OK、わかりました」「NGです」で返答可能
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getWorkerNotices, markNoticeRead, respondToNotice } from "../lib/api/client";
import { formatDateTime } from "../lib/formatters";
import type { NoticeType, WorkerNoticeItem } from "../types/api";

const NOTICE_TYPE_LABELS: Record<NoticeType, string> = {
  shift_confirm: "シフト確定",
  project_change: "案件変更",
  general: "お知らせ",
};

const NOTICE_TYPE_COLORS: Record<NoticeType, string> = {
  shift_confirm: "#1565c0",
  project_change: "#e65100",
  general: "#2e7d32",
};

/** 返答ボタンを表示する通知タイプ */
const RESPONDABLE_TYPES: NoticeType[] = ["shift_confirm", "project_change"];

function ResponseBadge({ response }: { response: "ok" | "ng" | null }) {
  if (!response) return null;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "0.1em 0.55em",
        borderRadius: "4px",
        fontSize: "0.72em",
        fontWeight: 700,
        background: response === "ok" ? "#e8f5e9" : "#fce4ec",
        color: response === "ok" ? "#2e7d32" : "#c62828",
        border: `1px solid ${response === "ok" ? "#a5d6a7" : "#ef9a9a"}`,
        marginLeft: "0.4em",
        verticalAlign: "middle",
      }}
    >
      {response === "ok" ? "✓ OK" : "✗ NG"}
    </span>
  );
}

export function NoticesPage() {
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [selected, setSelected] = useState<WorkerNoticeItem | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["worker-notices", unreadOnly],
    queryFn: () => getWorkerNotices({ unread_only: unreadOnly }),
    staleTime: 30_000,
  });

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["worker-notices"] });
    queryClient.invalidateQueries({ queryKey: ["worker-notices-unread"] });
  }

  const readMutation = useMutation({
    mutationFn: (noticeId: string) => markNoticeRead(noticeId),
    onSuccess: () => {
      invalidate();
      setSelected(null);
    },
  });

  const respondMutation = useMutation({
    mutationFn: ({ noticeId, response }: { noticeId: string; response: "ok" | "ng" }) =>
      respondToNotice(noticeId, response),
    onSuccess: () => {
      invalidate();
      setSelected(null);
    },
  });

  const isBusy = readMutation.isPending || respondMutation.isPending;

  function handleOpen(item: WorkerNoticeItem) {
    setSelected(item);
    // 既読はボタン操作時に記録する（ここでは自動既読しない）
  }

  function handleAcknowledge() {
    if (!selected) return;
    if (selected.response) {
      // すでに返答済みなら既読だけ更新して閉じる
      if (!selected.is_read) readMutation.mutate(selected.id);
      else setSelected(null);
    } else {
      readMutation.mutate(selected.id);
    }
  }

  function handleRespond(response: "ok" | "ng") {
    if (!selected) return;
    respondMutation.mutate({ noticeId: selected.id, response });
  }

  const isRespondable =
    selected !== null && RESPONDABLE_TYPES.includes(selected.notice_type as NoticeType);

  return (
    <div className="page-container">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <h2 style={{ margin: 0 }}>
          通知
          {(data?.unread_count ?? 0) > 0 && (
            <span
              style={{
                marginLeft: "0.5rem",
                background: "#d32f2f",
                color: "#fff",
                borderRadius: "9999px",
                padding: "0.1em 0.55em",
                fontSize: "0.75em",
                verticalAlign: "middle",
              }}
            >
              {data!.unread_count}
            </span>
          )}
        </h2>
        <label style={{ display: "flex", gap: "0.4rem", alignItems: "center", fontSize: "0.875rem" }}>
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
          />
          未読のみ
        </label>
      </div>

      {isLoading && <p style={{ color: "#888", textAlign: "center" }}>読み込み中...</p>}
      {isError && <p style={{ color: "#d32f2f", textAlign: "center" }}>通知の取得に失敗しました。</p>}

      {data && data.items.length === 0 && !isLoading && (
        <p style={{ color: "#888", textAlign: "center", padding: "2rem 0" }}>
          {unreadOnly ? "未読の通知はありません。" : "通知はありません。"}
        </p>
      )}

      {/* 通知カード一覧 */}
      {data && data.items.length > 0 && (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.75rem" }}>
          {data.items.map((item) => (
            <li
              key={item.id}
              style={{
                background: item.is_read ? "#f5f5f5" : "#fff",
                border: `1.5px solid ${item.is_read ? "#ddd" : item.priority === "urgent" ? "#d32f2f" : "#1976d2"}`,
                borderRadius: "8px",
                padding: "0.875rem 1rem",
                cursor: "pointer",
                boxShadow: item.is_read ? "none" : "0 1px 4px rgba(0,0,0,0.12)",
              }}
              onClick={() => handleOpen(item)}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.5rem" }}>
                <div style={{ flex: 1 }}>
                  {item.priority === "urgent" && (
                    <span style={{ color: "#d32f2f", fontWeight: 700, fontSize: "0.8em", marginRight: "0.25rem" }}>
                      【緊急】
                    </span>
                  )}
                  <span style={{ fontWeight: item.is_read ? 400 : 700 }}>{item.title}</span>
                  <ResponseBadge response={item.response} />
                </div>
                <span
                  style={{
                    background: NOTICE_TYPE_COLORS[item.notice_type as NoticeType] ?? "#666",
                    color: "#fff",
                    borderRadius: "4px",
                    padding: "0.15em 0.5em",
                    fontSize: "0.72em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {NOTICE_TYPE_LABELS[item.notice_type as NoticeType] ?? item.notice_type}
                </span>
              </div>
              {item.target_project_name && (
                <p style={{ margin: "0.25rem 0 0", fontSize: "0.8em", color: "#555" }}>
                  案件: {item.target_project_name}
                </p>
              )}
              <p style={{ margin: "0.25rem 0 0", fontSize: "0.75em", color: "#888" }}>
                {formatDateTime(item.created_at)}
                {item.is_read && item.read_at && ` · 既読 ${formatDateTime(item.read_at)}`}
                {!item.is_read && <span style={{ color: "#1976d2", marginLeft: "0.5em", fontWeight: 600 }}>● 未読</span>}
              </p>
            </li>
          ))}
        </ul>
      )}

      {/* 詳細ドロワー */}
      {selected && (
        <div
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", zIndex: 1000,
            display: "flex", alignItems: "flex-end",
          }}
          onClick={() => setSelected(null)}
        >
          <div
            style={{
              background: "#fff", borderRadius: "16px 16px 0 0", padding: "1.5rem",
              width: "100%", maxHeight: "80vh", overflow: "auto",
              display: "flex", flexDirection: "column", gap: "0.75rem",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* ヘッダー行 */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span
                style={{
                  background: NOTICE_TYPE_COLORS[selected.notice_type as NoticeType] ?? "#666",
                  color: "#fff",
                  borderRadius: "4px",
                  padding: "0.15em 0.6em",
                  fontSize: "0.8em",
                }}
              >
                {NOTICE_TYPE_LABELS[selected.notice_type as NoticeType] ?? selected.notice_type}
              </span>
              <button
                onClick={() => setSelected(null)}
                style={{ background: "none", border: "none", fontSize: "1.4rem", cursor: "pointer" }}
                aria-label="閉じる"
              >
                ×
              </button>
            </div>

            {selected.priority === "urgent" && (
              <p style={{ color: "#d32f2f", fontWeight: 700, margin: 0 }}>【緊急】</p>
            )}

            <h3 style={{ margin: 0 }}>{selected.title}</h3>

            {selected.target_project_name && (
              <p style={{ margin: 0, fontSize: "0.85em", color: "#555" }}>
                案件: {selected.target_project_name}
              </p>
            )}

            {/* 本文 */}
            <pre
              style={{
                whiteSpace: "pre-wrap", wordBreak: "break-word",
                fontSize: "0.9em", lineHeight: 1.7, margin: 0,
                background: "#f8f8f8", borderRadius: "8px", padding: "0.75rem",
              }}
            >
              {selected.body}
            </pre>

            <p style={{ margin: 0, fontSize: "0.75em", color: "#888" }}>
              {formatDateTime(selected.created_at)}
            </p>

            {/* 既返答済みバッジ */}
            {selected.response && (
              <div
                style={{
                  padding: "0.6rem 0.75rem",
                  borderRadius: "8px",
                  background: selected.response === "ok" ? "#e8f5e9" : "#fce4ec",
                  color: selected.response === "ok" ? "#2e7d32" : "#c62828",
                  fontWeight: 600,
                  fontSize: "0.9em",
                  textAlign: "center",
                }}
              >
                {selected.response === "ok" ? "✓ OK と返答済みです" : "✗ NG と返答済みです"}
                {selected.responded_at && (
                  <span style={{ fontWeight: 400, fontSize: "0.85em", marginLeft: "0.5em" }}>
                    （{formatDateTime(selected.responded_at)}）
                  </span>
                )}
              </div>
            )}

            {/* アクションボタン群 */}
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginTop: "0.25rem" }}>
              {isRespondable && !selected.response ? (
                // 返答型通知: OK / NG 両ボタン
                <>
                  <button
                    disabled={isBusy}
                    onClick={() => handleRespond("ok")}
                    style={{
                      padding: "0.85rem",
                      borderRadius: "10px",
                      border: "none",
                      background: isBusy ? "#ccc" : "#2e7d32",
                      color: "#fff",
                      fontSize: "1rem",
                      fontWeight: 700,
                      cursor: isBusy ? "not-allowed" : "pointer",
                    }}
                  >
                    {isBusy ? "送信中..." : "✓ OK、わかりました"}
                  </button>
                  <button
                    disabled={isBusy}
                    onClick={() => handleRespond("ng")}
                    style={{
                      padding: "0.85rem",
                      borderRadius: "10px",
                      border: "2px solid #c62828",
                      background: "#fff",
                      color: "#c62828",
                      fontSize: "1rem",
                      fontWeight: 700,
                      cursor: isBusy ? "not-allowed" : "pointer",
                    }}
                  >
                    {isBusy ? "送信中..." : "✗ NGです"}
                  </button>
                </>
              ) : (
                // 一般通知 / 返答済み: 了解ボタン（未読なら既読にする）
                !selected.is_read && (
                  <button
                    disabled={isBusy}
                    onClick={handleAcknowledge}
                    style={{
                      padding: "0.85rem",
                      borderRadius: "10px",
                      border: "none",
                      background: isBusy ? "#ccc" : "#1976d2",
                      color: "#fff",
                      fontSize: "1rem",
                      fontWeight: 700,
                      cursor: isBusy ? "not-allowed" : "pointer",
                    }}
                  >
                    {isBusy ? "処理中..." : "了解しました"}
                  </button>
                )
              )}
              <button
                onClick={() => setSelected(null)}
                style={{
                  padding: "0.7rem",
                  borderRadius: "10px",
                  border: "1px solid #ccc",
                  background: "#f5f5f5",
                  color: "#555",
                  fontSize: "0.9rem",
                  cursor: "pointer",
                }}
              >
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
