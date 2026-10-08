import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";

import {
  ApiError,
  getPublicRegistrationAccess,
  submitPublicIntroducerIdentityRegistration,
  submitPublicSupplierCorporationRegistration,
  submitPublicSupplierIndividualRegistration,
  submitPublicWorkerRegistration,
  uploadPublicRegistrationFile,
} from "../lib/api/client";
import type {
  PublicIntroducerIdentityRegistrationSubmitRequest,
  PublicRegistrationAccessResponse,
  PublicSupplierCorporationRegistrationSubmitRequest,
  PublicSupplierIndividualRegistrationSubmitRequest,
  PublicWorkerRegistrationSubmitRequest,
} from "../types/api";
import { formatDateTime } from "../lib/formatters";

type FormConfig = {
  title: string;
  description: string;
  submit: (payload:
    | PublicWorkerRegistrationSubmitRequest
    | PublicSupplierIndividualRegistrationSubmitRequest
    | PublicSupplierCorporationRegistrationSubmitRequest
    | PublicIntroducerIdentityRegistrationSubmitRequest) => Promise<unknown>;
  fields: Array<{ key: string; label: string; multiline?: boolean }>;
};

const FORM_CONFIGS: Record<string, FormConfig> = {
  worker: {
    title: "稼働者登録",
    description: "基本情報、緊急連絡先、口座、インボイス情報を入力します。",
    submit: (payload) => submitPublicWorkerRegistration(payload as PublicWorkerRegistrationSubmitRequest),
    fields: [
      { key: "last_name", label: "姓" },
      { key: "first_name", label: "名" },
      { key: "last_name_furigana", label: "姓ふりがな" },
      { key: "first_name_furigana", label: "名ふりがな" },
      { key: "sole_proprietor_name", label: "屋号" },
      { key: "gender", label: "性別" },
      { key: "route_group", label: "路線グループ" },
      { key: "introducer_supplier_name_raw", label: "紹介者名" },
      { key: "email", label: "メール" },
      { key: "phone", label: "電話番号" },
      { key: "zipcode", label: "郵便番号" },
      { key: "prefecture", label: "都道府県" },
      { key: "city_address", label: "住所1", multiline: true },
      { key: "building_address", label: "住所2", multiline: true },
      { key: "emergency_contact_name_kana", label: "緊急連絡先(カナ)" },
      { key: "emergency_contact_phone", label: "緊急連絡先電話" },
      { key: "bank_name", label: "銀行名" },
      { key: "bank_branch", label: "支店名" },
      { key: "bank_branch_number", label: "支店番号" },
      { key: "bank_account_type", label: "口座種別" },
      { key: "bank_account_number", label: "口座番号" },
      { key: "bank_account_holder", label: "口座名義(カナ)" },
      { key: "invoice_registration_status", label: "インボイス登録状況" },
      { key: "invoice_registration_number", label: "インボイス番号" },
      { key: "memo", label: "メモ", multiline: true },
    ],
  },
  "supplier-individual": {
    title: "個人下請け登録",
    description: "個人下請けの基本情報、口座、インボイス情報を入力します。",
    submit: (payload) => submitPublicSupplierIndividualRegistration(payload as PublicSupplierIndividualRegistrationSubmitRequest),
    fields: [
      { key: "supplier_type", label: "supplier_type" },
      { key: "name", label: "氏名" },
      { key: "name_furigana", label: "氏名ふりがな" },
      { key: "trade_name", label: "屋号" },
      { key: "email", label: "メール" },
      { key: "phone", label: "電話番号" },
      { key: "zipcode", label: "郵便番号" },
      { key: "prefecture", label: "都道府県" },
      { key: "city_address", label: "住所1", multiline: true },
      { key: "building_address", label: "住所2", multiline: true },
      { key: "bank_name", label: "銀行名" },
      { key: "bank_branch", label: "支店名" },
      { key: "bank_branch_number", label: "支店番号" },
      { key: "bank_account_type", label: "口座種別" },
      { key: "bank_account_number", label: "口座番号" },
      { key: "bank_account_holder_kana", label: "口座名義(カナ)" },
      { key: "invoice_registration_status", label: "インボイス登録状況" },
      { key: "invoice_registration_number", label: "インボイス番号" },
      { key: "memo", label: "メモ", multiline: true },
    ],
  },
  "supplier-corporation": {
    title: "法人下請け登録",
    description: "法人下請けの会社情報、担当者、口座、インボイス情報を入力します。",
    submit: (payload) => submitPublicSupplierCorporationRegistration(payload as PublicSupplierCorporationRegistrationSubmitRequest),
    fields: [
      { key: "supplier_type", label: "supplier_type" },
      { key: "company_name", label: "会社名" },
      { key: "company_name_furigana", label: "会社名ふりがな" },
      { key: "representative_name", label: "代表者名" },
      { key: "representative_name_furigana", label: "代表者名ふりがな" },
      { key: "email", label: "メール" },
      { key: "phone", label: "電話番号" },
      { key: "zipcode", label: "郵便番号" },
      { key: "prefecture", label: "都道府県" },
      { key: "city_address", label: "住所1", multiline: true },
      { key: "building_address", label: "住所2", multiline: true },
      { key: "bank_name", label: "銀行名" },
      { key: "bank_branch", label: "支店名" },
      { key: "bank_branch_number", label: "支店番号" },
      { key: "bank_account_type", label: "口座種別" },
      { key: "bank_account_number", label: "口座番号" },
      { key: "bank_account_holder_kana", label: "口座名義(カナ)" },
      { key: "invoice_registration_status", label: "インボイス登録状況" },
      { key: "invoice_registration_number", label: "インボイス番号" },
      { key: "memo", label: "メモ", multiline: true },
    ],
  },
  "introducer-identity": {
    title: "紹介者本人確認",
    description: "紹介者本人確認の対象情報と補足を入力します。",
    submit: (payload) => submitPublicIntroducerIdentityRegistration(payload as PublicIntroducerIdentityRegistrationSubmitRequest),
    fields: [
      { key: "related_worker_request_id", label: "関連 worker request ID" },
      { key: "related_supplier_request_id", label: "関連 supplier request ID" },
      { key: "subject_name", label: "対象者名" },
      { key: "subject_name_furigana", label: "対象者名ふりがな" },
      { key: "submission_reason", label: "提出理由", multiline: true },
      { key: "memo", label: "メモ", multiline: true },
    ],
  },
};

const DOCUMENT_TYPES = [
  { value: "driver_license", label: "運転免許証" },
  { value: "my_number_card", label: "マイナンバーカード" },
  { value: "residence_card", label: "在留カード" },
  { value: "passport", label: "パスポート" },
  { value: "other", label: "その他" },
];

export function PublicRegistrationPage() {
  const { formType = "worker" } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";
  const config = FORM_CONFIGS[formType];

  const [pin, setPin] = useState("");
  const [accessData, setAccessData] = useState<PublicRegistrationAccessResponse | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [documentType, setDocumentType] = useState("driver_license");
  const [documentPart, setDocumentPart] = useState("single");
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const initialFormValues = useMemo(() => {
    const next: Record<string, string> = {};
    for (const field of config?.fields || []) {
      next[field.key] = accessData?.detail_data?.[field.key] ? String(accessData.detail_data[field.key]) : "";
    }
    return next;
  }, [accessData?.detail_data, config?.fields]);

  useEffect(() => {
    setFormValues(initialFormValues);
  }, [initialFormValues]);

  const accessMutation = useMutation({
    mutationFn: () => getPublicRegistrationAccess(formType, token, pin),
    onSuccess: (result) => {
      setError("");
      setMessage("リンクを確認しました。入力を続けてください。");
      setAccessData(result);
    },
    onError: (fetchError) => {
      setMessage("");
      setError(fetchError instanceof ApiError ? fetchError.message : "公開リンクの確認に失敗しました。");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!uploadFile) {
        return Promise.reject(new Error("file required"));
      }
      return uploadPublicRegistrationFile({
        formType,
        token,
        pin,
        documentType,
        documentPart,
        file: uploadFile,
      });
    },
    onSuccess: (result) => {
      setError("");
      setMessage("添付ファイルをアップロードしました。");
      setUploadFile(null);
      setAccessData((current) => current ? { ...current, files: result.files } : current);
    },
    onError: (uploadError) => {
      setMessage("");
      setError(uploadError instanceof ApiError ? uploadError.message : "添付ファイルのアップロードに失敗しました。");
    },
  });

  const submitMutation = useMutation({
    mutationFn: () => {
      const normalizedValues = Object.fromEntries(
        Object.entries(formValues).map(([key, value]) => [key, value.trim() || null]),
      );
      const payload = { token, pin, ...normalizedValues } as
        | PublicWorkerRegistrationSubmitRequest
        | PublicSupplierIndividualRegistrationSubmitRequest
        | PublicSupplierCorporationRegistrationSubmitRequest
        | PublicIntroducerIdentityRegistrationSubmitRequest;
      return config.submit(payload);
    },
    onSuccess: () => {
      setError("");
      setMessage("登録申請を送信しました。確認が完了するまでお待ちください。");
      setAccessData((current) => current ? { ...current, status: "pending" } : current);
    },
    onError: (submitError) => {
      setMessage("");
      setError(submitError instanceof ApiError ? submitError.message : "登録申請の送信に失敗しました。");
    },
  });

  if (!config) {
    return <div className="page-stack"><section className="panel-card">未対応の公開フォームです。</section></div>;
  }

  return (
    <div className="page-stack" style={{ maxWidth: "960px", margin: "0 auto", padding: "2rem 1rem 4rem" }}>
      <section className="panel-card" style={{ display: "grid", gap: "1rem" }}>
        <p className="eyebrow">公開フォーム</p>
        <h1 style={{ margin: 0 }}>{config.title}</h1>
        <p style={{ margin: 0 }}>{config.description}</p>
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
          <label>
            token
            <input value={token} readOnly />
          </label>
          <label>
            PIN
            <input value={pin} onChange={(event) => setPin(event.target.value)} placeholder="6桁 PIN" />
          </label>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <button type="button" onClick={() => accessMutation.mutate()} disabled={!token || !pin || accessMutation.isPending}>
            {accessMutation.isPending ? "確認中..." : "リンク確認"}
          </button>
          {accessData ? <span>有効期限: {formatDateTime(accessData.expires_at)}</span> : null}
        </div>
        {message ? <p style={{ margin: 0, color: "var(--color-success, #027a48)" }}>{message}</p> : null}
        {error ? <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>{error}</p> : null}
      </section>

      {accessData ? (
        <>
          <section className="panel-card" style={{ display: "grid", gap: "1rem" }}>
            <h2 style={{ margin: 0 }}>本人確認ファイル</h2>
            <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
              <label>
                書類種別
                <select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
                  {DOCUMENT_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <label>
                面
                <select value={documentPart} onChange={(event) => setDocumentPart(event.target.value)}>
                  <option value="single">single</option>
                  <option value="front">front</option>
                  <option value="back">back</option>
                </select>
              </label>
              <label style={{ gridColumn: "1 / -1" }}>
                ファイル
                <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" onChange={(event) => setUploadFile(event.target.files?.[0] || null)} />
              </label>
            </div>
            <button type="button" onClick={() => uploadMutation.mutate()} disabled={!uploadFile || uploadMutation.isPending || accessData.status !== "link_issued"}>
              {uploadMutation.isPending ? "アップロード中..." : "添付を追加"}
            </button>
            <div style={{ display: "grid", gap: "0.5rem" }}>
              {accessData.files.length === 0 ? <p style={{ margin: 0 }}>添付ファイルはまだありません。</p> : accessData.files.map((file) => (
                <div key={file.id} style={{ padding: "0.75rem", border: "1px solid var(--color-border-subtle, #d0d5dd)", borderRadius: "0.5rem" }}>
                  {file.document_type} / {file.document_part} / {file.original_filename}
                </div>
              ))}
            </div>
          </section>

          <section className="panel-card" style={{ display: "grid", gap: "1rem" }}>
            <h2 style={{ margin: 0 }}>申請内容</h2>
            <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))" }}>
              {config.fields.map((field) => (
                <label key={field.key} style={field.multiline ? { gridColumn: "1 / -1" } : undefined}>
                  {field.label}
                  {field.multiline ? (
                    <textarea
                      rows={3}
                      value={formValues[field.key] || ""}
                      onChange={(event) => setFormValues((current) => ({ ...current, [field.key]: event.target.value }))}
                    />
                  ) : (
                    <input
                      value={formValues[field.key] || ""}
                      onChange={(event) => setFormValues((current) => ({ ...current, [field.key]: event.target.value }))}
                    />
                  )}
                </label>
              ))}
            </div>
            <button type="button" onClick={() => submitMutation.mutate()} disabled={submitMutation.isPending || accessData.status !== "link_issued"}>
              {submitMutation.isPending ? "送信中..." : accessData.status === "link_issued" ? "申請を送信" : "送信済み"}
            </button>
          </section>
        </>
      ) : null}
    </div>
  );
}