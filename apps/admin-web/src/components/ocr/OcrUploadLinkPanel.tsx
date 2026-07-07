import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { createOcrUploadLink, listOcrUploadLinks, revokeOcrUploadLink } from "../../lib/api/client";
import { PublicOcrUploadLimitNote } from "../../lib/ocr/publicUploadLimits";
import type { OcrUploadLinkCreateRequest } from "../../types/api";

export function OcrUploadLinkPanel() {
  const queryClient = useQueryClient();
  const [createdUrl, setCreatedUrl] = useState<string | null>(null);
  const [form, setForm] = useState<OcrUploadLinkCreateRequest>({
    label: "",
    expires_in_days: 30,
    public_memo: null,
    internal_memo: null,
    default_source_type: "required",
    period_key: null,
    max_upload_count: null,
  });

  const linksQuery = useQuery({
    queryKey: ["ocr-upload-links"],
    queryFn: () => listOcrUploadLinks(),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createOcrUploadLink({
        ...form,
        label: form.label || null,
        default_source_type: "required",
      }),
    onSuccess: (data) => {
      setCreatedUrl(`${window.location.origin}${data.public_upload_url}`);
      void queryClient.invalidateQueries({ queryKey: ["ocr-upload-links"] });
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (linkId: string) => revokeOcrUploadLink(linkId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["ocr-upload-links"] });
    },
  });

  const items = linksQuery.data?.items ?? [];

  return (
    <section className="panel-card page-stack">
      <h2>外部アップロードリンク</h2>
      <p className="muted-text">現場向けの共有URLを発行します。発行直後のみURLをコピーできます。</p>
      <PublicOcrUploadLimitNote className="public-form-limit-note ocr-upload-link-limit-note" />

      <div className="ocr-upload-link-form">
        <label className="form-field">
          <span>ラベル</span>
          <input
            value={form.label ?? ""}
            onChange={(e) => setForm((prev) => ({ ...prev, label: e.target.value }))}
            placeholder="例: 2026年7月 現場アップロード"
          />
        </label>
        <label className="form-field">
          <span>外部向けメモ</span>
          <input
            value={form.public_memo ?? ""}
            onChange={(e) => setForm((prev) => ({ ...prev, public_memo: e.target.value || null }))}
          />
        </label>
        <div className="ocr-upload-link-form-actions">
          <label className="form-field ocr-upload-link-form-expiry">
            <span>有効期限（日）</span>
            <input
              type="number"
              min={1}
              max={365}
              value={form.expires_in_days}
              onChange={(e) => setForm((prev) => ({ ...prev, expires_in_days: Number(e.target.value) }))}
            />
          </label>
          <button
            type="button"
            className="primary-button registration-action-button"
            disabled={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? "発行中..." : "リンクを発行"}
          </button>
        </div>
      </div>

      {createdUrl ? (
        <div className="registration-link-card">
          <p>発行URL（この画面を閉じると再表示できません）:</p>
          <PublicOcrUploadLimitNote className="public-form-limit-note" />
          <code>{createdUrl}</code>
          <div className="registration-action-row">
            <button type="button" className="secondary-button registration-action-button" onClick={() => navigator.clipboard.writeText(createdUrl)}>
              コピー
            </button>
          </div>
        </div>
      ) : null}

      <div className="upload-actions">
        <button type="button" className="ghost-button" onClick={() => linksQuery.refetch()}>
          一覧を更新
        </button>
      </div>

      {items.length ? (
        <table className="data-table">
          <thead>
            <tr>
              <th>ラベル</th>
              <th>suffix</th>
              <th>件数</th>
              <th>1h</th>
              <th>期限</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((link) => (
              <tr key={link.id}>
                <td>{link.label || "-"}</td>
                <td>{link.token_suffix}</td>
                <td>{link.upload_count}</td>
                <td>{link.recent_hour_attempt_count}</td>
                <td>{new Date(link.expires_at).toLocaleString()}</td>
                <td>
                  {link.status === "active" ? (
                    <button type="button" className="ghost-button" onClick={() => revokeMutation.mutate(link.id)}>
                      失効
                    </button>
                  ) : (
                    link.status
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
