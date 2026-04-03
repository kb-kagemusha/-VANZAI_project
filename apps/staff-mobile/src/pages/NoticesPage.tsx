/**
 * スタッフ向け通知一覧ページ
 *
 * 管理者から送られたシフト確定・案件変更・一般お知らせを閲覧し、
 * タップで既読にする
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getWorkerNotices, markNoticeRead } from "../lib/api/client";
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

export function NoticesPage() {
  const queryClient = useQueryClient();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [selected, setSelected] = useState<WorkerNoticeItem | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["worker-notices", unreadOnly],
    queryFn: () => getWorkerNotices({ unread_only: unreadOnly }),
    staleTime: 30_000,
  });

  const readMutation = useMutation({
    mutationFn: (noticeId: string) => markNoticeRead(noticeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["worker-notices"] });
      queryClient.invalidateQueries({ queryKey: ["worker-notices-unread"] });
    },
  });

  function handleOpen(item: WorkerNoticeItem) {
    setSelected(item);
    if (!item.is_read) {
      readMutation.mutate(item.id);
    }
  }

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
              width: "100%", maxHeight: "70vh", overflow: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
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
              <p style={{ color: "#d32f2f", fontWeight: 700, margin: "0 0 0.5rem" }}>【緊急】</p>
            )}
            <h3 style={{ margin: "0 0 0.5rem" }}>{selected.title}</h3>
            {selected.target_project_name && (
              <p style={{ margin: "0 0 0.75rem", fontSize: "0.85em", color: "#555" }}>
                案件: {selected.target_project_name}
              </p>
            )}
            <pre
              style={{
                whiteSpace: "pre-wrap", wordBreak: "break-word",
                fontSize: "0.9em", lineHeight: 1.7, margin: 0,
              }}
            >
              {selected.body}
            </pre>
            <p style={{ marginTop: "1rem", fontSize: "0.75em", color: "#888" }}>
              {formatDateTime(selected.created_at)}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
