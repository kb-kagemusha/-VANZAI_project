import { Navigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import { ApiError, downloadInvoicePdf, generateInvoice, getClientStaff, getInvoices, getProjects, issueInvoice } from "../lib/api/client";
import { currentMonthInput, formatCurrency, formatDateTime, toPeriodKey } from "../lib/formatters";

const PAGE_SIZE = 20;

export function InvoicesPage() {
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [status, setStatus] = useState("");
  const [sortBy, setSortBy] = useState("issued_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [page, setPage] = useState(0);
  const [genProjectId, setGenProjectId] = useState("");
  const [genDocumentType, setGenDocumentType] = useState<"invoice" | "estimate">("invoice");
  const [genClientStaffId, setGenClientStaffId] = useState("");
  const [genSubject, setGenSubject] = useState("");
  const [genFixedOfficeFee, setGenFixedOfficeFee] = useState("");
  const [genError, setGenError] = useState("");
  const [actionError, setActionError] = useState("");
  const periodKey = toPeriodKey(monthValue);
  const queryClient = useQueryClient();

  const invoicesQuery = useQuery({
    queryKey: ["invoices", periodKey, status, sortBy, sortOrder, page],
    queryFn: () =>
      getInvoices({
        period_key: periodKey,
        status: status || undefined,
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

  const selectedProject = (projectsQuery.data?.items ?? []).find((project) => project.id === genProjectId) ?? null;
  const selectedClientId = selectedProject?.client_id ?? "";

  const clientStaffQuery = useQuery({
    queryKey: ["client-staff", selectedClientId],
    queryFn: () => getClientStaff(selectedClientId, { limit: 200, is_active: true }),
    enabled: Boolean(selectedClientId),
  });

  useEffect(() => {
    if (!selectedProject) {
      setGenSubject("");
      setGenClientStaffId("");
      return;
    }
    const year = Number(periodKey.slice(0, 4));
    const month = Number(periodKey.slice(4, 6));
    setGenSubject(`${year}年${month}月分_${selectedProject.name}`);
    setGenClientStaffId("");
  }, [genProjectId, periodKey, selectedProject?.name]);

  const generateMutation = useMutation({
    mutationFn: () => generateInvoice({
      projectId: genProjectId,
      periodKey,
      documentType: genDocumentType,
      clientStaffId: genClientStaffId || null,
      subject: genSubject.trim() || null,
      fixedOfficeFeeAmount: genFixedOfficeFee.trim() || null,
    }),
    onSuccess: () => {
      setGenError("");
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (err: unknown) => {
      setGenError(err instanceof ApiError ? err.message : "請求書の生成に失敗しました");
    },
  });

  const issueMutation = useMutation({
    mutationFn: (invoiceId: string) => issueInvoice(invoiceId),
    onSuccess: () => {
      setActionError("");
      void queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (err: unknown) => {
      setActionError(err instanceof ApiError ? err.message : "請求書発行に失敗しました");
    },
  });

  if (invoicesQuery.isLoading) {
    return <LoadingOverlay label="請求一覧を読み込み中..." />;
  }

  if (invoicesQuery.error instanceof ApiError && invoicesQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (invoicesQuery.isError || !invoicesQuery.data) {
    return <ErrorState title="請求一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="請求一覧" description="請求書の版、発行状態、金額、PDF 有無を参照します。" />

      {/* 請求書生成フォーム */}
      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.9rem" }}>
        <strong style={{ width: "100%" }}>請求書を生成</strong>
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label>
            案件
            <select value={genProjectId} onChange={(e) => setGenProjectId(e.target.value)}>
              <option value="">案件を選択</option>
              {(projectsQuery.data?.items ?? []).map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </label>
          <label>
            対象月
            <input type="month" value={monthValue} onChange={(e) => { setMonthValue(e.target.value); setPage(0); }} />
          </label>
          <label>
            帳票種別
            <select value={genDocumentType} onChange={(e) => setGenDocumentType(e.target.value as "invoice" | "estimate")}>
              <option value="invoice">請求書</option>
              <option value="estimate">見積書</option>
            </select>
          </label>
          <label>
            クライアント責任者
            <select value={genClientStaffId} onChange={(e) => setGenClientStaffId(e.target.value)} disabled={!selectedClientId || clientStaffQuery.isLoading}>
              <option value="">クライアントマスタ既定を使用</option>
              {(clientStaffQuery.data?.items ?? []).map((staff) => (
                <option key={staff.id} value={staff.id}>{staff.name}{staff.role ? ` (${staff.role})` : ""}</option>
              ))}
            </select>
          </label>
          <label style={{ gridColumn: "1 / -1" }}>
            件名
            <input value={genSubject} onChange={(e) => setGenSubject(e.target.value)} placeholder="例: 2026年1月分_案件名" />
          </label>
          <label>
            固定事務局費
            <input value={genFixedOfficeFee} onChange={(e) => setGenFixedOfficeFee(e.target.value)} inputMode="decimal" placeholder="未入力で加算なし" />
          </label>
        </div>
        {selectedProject ? (
          <p style={{ margin: 0, color: "var(--color-text-muted, #475467)", fontSize: "0.9rem" }}>
            請求先: {selectedProject.client_name}
          </p>
        ) : null}
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <button
            onClick={() => generateMutation.mutate()}
            disabled={!genProjectId || !genSubject.trim() || generateMutation.isPending}
          >
            {generateMutation.isPending ? "生成中..." : "請求書生成"}
          </button>
        </div>
        {genError && <span style={{ color: "var(--color-danger, red)", fontSize: "0.875rem" }}>{genError}</span>}
        {generateMutation.isSuccess && <span style={{ color: "green", fontSize: "0.875rem" }}>生成しました</span>}
      </section>

      {actionError ? <p style={{ margin: 0, color: "var(--color-danger, #b42318)" }}>{actionError}</p> : null}

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
            <option value="issued">発行済み</option>
            <option value="corrected">訂正済み</option>
          </select>
        </label>
        <label>
          ソート
          <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(0); }}>
            <option value="issued_at">発行日時</option>
            <option value="client_name">取引先名</option>
            <option value="project_name">案件名</option>
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
          { key: "number", header: "請求番号", render: (row) => row.invoice_number },
          { key: "documentType", header: "帳票種別", render: (row) => row.document_type === "estimate" ? "見積書" : "請求書" },
          { key: "client", header: "取引先", render: (row) => row.client_name },
          { key: "subject", header: "件名", render: (row) => row.subject || "-" },
          { key: "addressee", header: "宛名", render: (row) => row.addressee_name || row.addressee_company_name || "-" },
          { key: "project", header: "案件", render: (row) => row.project_name || "-" },
          { key: "period", header: "対象月", render: (row) => row.period_key },
          { key: "version", header: "版", render: (row) => row.version },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
          { key: "officeFee", header: "固定事務局費", render: (row) => row.fixed_office_fee_amount ? formatCurrency(row.fixed_office_fee_amount) : "-" },
          { key: "amount", header: "合計", render: (row) => formatCurrency(row.total_amount) },
          { key: "issued", header: "発行日時", render: (row) => formatDateTime(row.issued_at) },
          {
            key: "pdf",
            header: "PDF",
            render: (row) => (row.status === "preparing" ? "発行後に可" : row.has_pdf ? "保存済み" : "都度生成"),
          },
          {
            key: "storage",
            header: "保存先",
            render: (row) => (row.pdf_storage_key ? row.pdf_storage_key : row.status === "preparing" ? "未生成" : "都度生成のみ"),
          },
          {
            key: "actions",
            header: "操作",
            render: (row) => (
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                {row.status === "preparing" ? (
                  <button
                    onClick={() => issueMutation.mutate(row.id)}
                    disabled={issueMutation.isPending}
                    style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
                  >
                    発行
                  </button>
                ) : null}
                {row.status !== "preparing" ? (
                  <button
                    onClick={() => {
                      void downloadInvoicePdf(row.id).catch((err: unknown) => {
                        setActionError(err instanceof ApiError ? err.message : "請求書PDFのダウンロードに失敗しました");
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
        rows={invoicesQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="請求書はありません"
        emptyDescription="条件に一致する請求書は見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={invoicesQuery.data.total}
        limit={invoicesQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}