import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { createOcrUploadLink, listOcrUploadLinks, revokeOcrUploadLink } from "../../lib/api/client";
import { PublicOcrUploadLimitNote } from "../../lib/ocr/publicUploadLimits";
import type { OcrUploadLinkCreateRequest } from "../../types/api";

type ExpiryMode = "days" | "date";

function todayDateInputValue() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function OcrUploadLinkPanel() {
  const queryClient = useQueryClient();
  const [createdUrl, setCreatedUrl] = useState<string | null>(null);
  const [expiryMode, setExpiryMode] = useState<ExpiryMode>("days");
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState<OcrUploadLinkCreateRequest>({
    label: "",
    expires_in_days: 30,
    expires_at_date: null,
    public_memo: null,
    internal_memo: null,
    default_source_type: "required",
    period_key: null,
    max_upload_count: null,
  });

  const minExpiryDate = useMemo(() => todayDateInputValue(), []);

  const linksQuery = useQuery({
    queryKey: ["ocr-upload-links"],
    queryFn: () => listOcrUploadLinks(),
  });

  const buildCreatePayload = (): OcrUploadLinkCreateRequest | null => {
    const base: OcrUploadLinkCreateRequest = {
      label: form.label || null,
      public_memo: form.public_memo,
      internal_memo: form.internal_memo,
      default_source_type: "required",
      period_key: form.period_key,
      max_upload_count: form.max_upload_count,
    };

    if (expiryMode === "days") {
      const days = form.expires_in_days ?? 30;
      if (days < 1 || days > 365) {
        setFormError("有効期限（日）は1〜365の範囲で指定してください。");
        return null;
      }
      return { ...base, expires_in_days: days, expires_at_date: null };
    }

    if (!form.expires_at_date) {
      setFormError("期限日を選択してください。");
      return null;
    }
    return { ...base, expires_in_days: null, expires_at_date: form.expires_at_date };
  };

  const createMutation = useMutation({
    mutationFn: (payload: OcrUploadLinkCreateRequest) => createOcrUploadLink(payload),
    onSuccess: (data) => {
      setCreatedUrl(`${window.location.origin}${data.public_upload_url}`);
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: ["ocr-upload-links"] });
    },
    onError: () => {
      setFormError("リンクの発行に失敗しました。入力内容を確認してください。");
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
    <section className="panel-card page-stack ocr-upload-link-panel">
      <h2 className="ocr-upload-link-title">外部アップロードリンク</h2>
      <p className="muted-text ocr-upload-link-intro">
        現場向けの共有URLを発行します。発行直後のみURLをコピーできます。
        <br />
        <span className="ocr-limit-accent">管理画面からの直接アップロードに枚数上限はありません。</span>
      </p>
      <PublicOcrUploadLimitNote className="public-form-limit-note ocr-upload-link-limit-note" variant="admin-context" />

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
          <label className="form-field ocr-upload-link-expiry-mode">
            <span>有効期限の指定</span>
            <select
              value={expiryMode}
              onChange={(e) => {
                setFormError(null);
                setExpiryMode(e.target.value as ExpiryMode);
              }}
            >
              <option value="days">日数</option>
              <option value="date">期限日</option>
            </select>
          </label>
          {expiryMode === "days" ? (
            <label className="form-field ocr-upload-link-form-expiry">
              <span>有効期限（日）</span>
              <input
                type="number"
                min={1}
                max={365}
                value={form.expires_in_days ?? 30}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, expires_in_days: Number(e.target.value), expires_at_date: null }))
                }
              />
            </label>
          ) : (
            <label className="form-field ocr-upload-link-form-expiry">
              <span>期限日</span>
              <input
                type="date"
                min={minExpiryDate}
                value={form.expires_at_date ?? ""}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    expires_at_date: e.target.value || null,
                    expires_in_days: null,
                  }))
                }
              />
            </label>
          )}
          <button
            type="button"
            className="primary-button registration-action-button"
            disabled={createMutation.isPending}
            onClick={() => {
              const payload = buildCreatePayload();
              if (!payload) {
                return;
              }
              setFormError(null);
              createMutation.mutate(payload);
            }}
          >
            {createMutation.isPending ? "発行中..." : "リンクを発行"}
          </button>
        </div>
      </div>

      {formError ? <p className="form-error">{formError}</p> : null}

      {createdUrl ? (
        <div className="registration-link-card">
          <p>発行URL（この画面を閉じると再表示できません）:</p>
          <PublicOcrUploadLimitNote className="public-form-limit-note" variant="admin-context" />
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
        <div className="ocr-upload-link-links-table-wrap">
          <table className="data-table ocr-upload-link-table">
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
        </div>
      ) : null}
    </section>
  );
}
