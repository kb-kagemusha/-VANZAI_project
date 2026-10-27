import { apiFetch } from "./api/client";

/** 請求書に保存した発行元（作成時点の会社情報）。0.49.8 より前の請求書には電話番号などがない。 */
export type BillingIssuer = { revision: number; name: string; postal_code: string; address: string; registration_number: string; bank_details: string; payment_terms: string;
  phone?: string; email?: string; representative?: string };
/** 会社情報（0.49.8、DEC-082）。サイドメニュー「会社情報」で編集する。 */
export type CompanyProfile = { revision: number; name: string; postal_code: string; address: string; phone: string; email: string; representative: string;
  registration_number: string; bank_details: string; payment_terms: string };
export const getCompanyProfile = () => apiFetch<CompanyProfile>("/api/company-profile");
export const saveCompanyProfile = ({ revision, ...values }: CompanyProfile) => apiFetch<CompanyProfile>("/api/company-profile", { method: "PUT", body: JSON.stringify({ ...values, expected_revision: revision }) });

export type BillingOrder = { pricing_mode?: "legacy_total"|"person_day"; pricing_stale?: boolean; is_test?: boolean; version_id: string; series_id: string; document_number: string; version_no: number; project_name: string;
  work_date_label: string; categories: string[]; client_id: string | null; client_name: string; revision: number; amount_id: string | null; amount: string | null;
  billing_month: string | null; invoice_id: string | null; status: string; incentive_enabled: boolean; incentive_note: string;
  incentive_amount: string | null; total_amount: string | null; billing_ready: boolean; client_mismatch: boolean };
export type BillingInvoice = { id: string; document_number: string; client_id: string; client_name: string; billing_month: string; billing_date: string;
  version: number; parent_invoice_id: string | null; status: "draft" | "issued" | "cancelled"; subtotal: string; tax_amount: string; total_amount: string;
  issuer_snapshot: BillingIssuer;
  lines?: { id: string; description: string; document_number: string; work_date_label: string; amount: string; incentive_amount: string | null; incentive_note: string | null; pricing_snapshot?: { mode: string; days: {date:string;quantity:number;unit_price:string;subtotal:string;adjustment:string;adjustment_reason:string}[] } | null }[] };
export type BillingHistory = { revision: number; client_name: string; amount: string; incentive_enabled: boolean; incentive_note: string; incentive_amount: string | null; billing_month: string; reason: string; created_at: string };
type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export const getOrderBillingSummary = (include_test = false) => apiFetch<{ missing_count: number; total: number }>("/api/order-billing/summary", undefined, { include_test });
export const getBillingClients = () => apiFetch<{ items: { id: string; name: string }[] }>("/api/order-billing/clients");
export const getBillingOrders = (params: { include_test?: boolean; status: string; q: string; offset: number; limit: number }) => apiFetch<Page<BillingOrder>>("/api/order-billing/orders", undefined, params);
export const saveBillingAmount = (id: string, body: { billing_month: string; amount: string; incentive_amount: string | null; expected_revision: number; reason: string }) => apiFetch(`/api/order-billing/orders/${id}/confirm`, { method: "POST", body: JSON.stringify(body) });
export const getBillingHistory = (id: string) => apiFetch<{ items: BillingHistory[] }>(`/api/order-billing/orders/${id}/history`);
export const getBillingInvoices = (month: string, offset: number) => apiFetch<Page<BillingInvoice>>("/api/order-billing/invoices", undefined, { billing_month: month, limit: 30, offset });
export const createBillingInvoice = (body: { client_id: string; billing_month: string; billing_date: string }) => apiFetch<BillingInvoice>("/api/order-billing/invoices", { method: "POST", body: JSON.stringify(body) });
export const getBillingInvoice = (id: string) => apiFetch<BillingInvoice>(`/api/order-billing/invoices/${id}`);
export const issueBillingInvoice = (id: string) => apiFetch<BillingInvoice>(`/api/order-billing/invoices/${id}/issue`, { method: "POST" });
export const cancelBillingInvoice = (id: string, reason: string) => apiFetch(`/api/order-billing/invoices/${id}/cancel-draft`, { method: "POST", body: JSON.stringify({ reason }) });
