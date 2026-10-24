import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate } from "react-router-dom";
import { FormDialog } from "../components/FormDialog";
import { BillingAmountInput } from "../components/BillingAmountInput";
import { isValidBillingAmount } from "../lib/billingAmountFormat";
import { TestBadge } from "../components/TestBadge";
import { PageHeader } from "../components/PageHeader";
import { OrderRequestDetailDialog } from "../components/OrderRequestDetailDialog";
import { todayInTokyo } from "../components/MonthCalendar";
import { useAuth } from "../lib/auth/auth-context";
import { confirmApp, promptApp } from "../lib/appDialog";
import { fetchOrderBillingPdf } from "../lib/api/client";
import { getBillingClients, getBillingOrders, getOrderBillingSummary, saveBillingAmount, getBillingHistory, getBillingInvoices,
  createBillingInvoice, getBillingInvoice, issueBillingInvoice, cancelBillingInvoice, type BillingOrder, type BillingHistory } from "../lib/orderBillingApi";

const yen = (value: string) => new Intl.NumberFormat("ja-JP", { style: "currency", currency: "JPY", maximumFractionDigits: 2 }).format(Number(value));
const monthLabel = (month: string) => `${month.slice(0, 4)}年${Number(month.slice(4))}月`;
const message = (error: unknown) => error instanceof Error ? error.message : "処理できませんでした。一覧を更新して確認してください。";
const invoiceStatus = { draft: "下書き", issued: "発行済み", cancelled: "下書き取消" };

export function OrderBillingPage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const allowed = user?.role === "admin";
  const [includeTest, setIncludeTest] = useState(false);
  const [status, setStatus] = useState("missing");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [invoicePage, setInvoicePage] = useState(0);
  const [invoiceMonth, setInvoiceMonth] = useState(todayInTokyo().slice(0, 7));
  const [edit, setEdit] = useState<BillingOrder | null>(null);
  const [editMonth, setEditMonth] = useState("");
  const [editAmount, setEditAmount] = useState("");
  const [editIncentive, setEditIncentive] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [dialogError, setDialogError] = useState("");
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState<string | null>(null);
  const [history, setHistory] = useState<{ title: string; items: BillingHistory[] } | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createClient, setCreateClient] = useState("");
  const [createDate, setCreateDate] = useState(todayInTokyo());
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const summary = useQuery({ queryKey: ["order-billing", "summary", includeTest], queryFn: () => getOrderBillingSummary(includeTest), enabled: allowed, refetchOnWindowFocus: true });
  const clients = useQuery({ queryKey: ["order-billing", "clients"], queryFn: getBillingClients, enabled: allowed });
  const orders = useQuery({ queryKey: ["order-billing", "orders", status, search, page, includeTest], queryFn: () => getBillingOrders({ include_test: includeTest, status, q: search, offset: page * 30, limit: 30 }), enabled: allowed, refetchOnWindowFocus: true });
  const invoices = useQuery({ queryKey: ["order-billing", "invoices", invoiceMonth, invoicePage], queryFn: () => getBillingInvoices(invoiceMonth.replace("-", ""), invoicePage * 30), enabled: allowed, refetchOnWindowFocus: true });
  const invoice = useQuery({ queryKey: ["order-billing", "invoice", invoiceId], queryFn: () => getBillingInvoice(invoiceId!), enabled: allowed && !!invoiceId });
  useEffect(() => () => { if (pdfUrl) URL.revokeObjectURL(pdfUrl); }, [pdfUrl]);
  if (!allowed) return <Navigate to="/403" replace />;

  async function refresh() { await client.invalidateQueries({ queryKey: ["order-billing"] }); }
  function openEdit(row: BillingOrder) {
    setEdit(row); setEditMonth(row.billing_month ? `${row.billing_month.slice(0, 4)}-${row.billing_month.slice(4)}` : "");
    setEditIncentive((row.incentive_amount ?? "").replace(/\.0+$/, ""));
    setEditAmount((row.amount ?? "").replace(/\.0+$/, "")); setReason(""); setDialogError("");
  }
  async function save() {
    if (!edit || busy) return;
    setBusy(true); setDialogError("");
    try {
      await saveBillingAmount(edit.version_id, { billing_month: editMonth.replace("-", ""), amount: editAmount, incentive_amount: edit.incentive_enabled && editIncentive !== "" ? editIncentive : null, expected_revision: edit.revision, reason });
      setEdit(null); await refresh();
    } catch (err) { setDialogError(message(err)); }
    finally { setBusy(false); }
  }
  async function create() {
    setBusy(true); setDialogError("");
    try {
      const row = await createBillingInvoice({ client_id: createClient, billing_month: invoiceMonth.replace("-", ""), billing_date: createDate });
      setCreateOpen(false); setInvoiceId(row.id); await refresh();
    } catch (err) { setDialogError(message(err)); }
    finally { setBusy(false); }
  }
  async function showHistory(row: BillingOrder) {
    setError("");
    try { setHistory({ title: row.document_number, items: (await getBillingHistory(row.version_id)).items }); }
    catch (err) { setError(message(err)); }
  }
  async function showPdf(id: string) {
    setError(""); setBusy(true);
    try { const blob = await fetchOrderBillingPdf(id); setInvoiceId(null); setPdfUrl(URL.createObjectURL(blob)); }
    catch (err) { setError(message(err)); }
    finally { setBusy(false); }
  }
  async function issue(id: string) {
    if (!(await confirmApp({ title: "月次請求書を発行", message: "PDFと明細を確認しましたか？ 発行後の金額・明細・PDFは固定され、上書きできません。", confirmLabel: "確認して発行する" }))) return;
    setBusy(true); setDialogError("");
    try { await issueBillingInvoice(id); await refresh(); }
    catch (err) { setDialogError(message(err)); }
    finally { setBusy(false); }
  }
  async function cancel(id: string) {
    const text = await promptApp({ title: "請求書の下書きを取り消す", message: "理由を入力してください。下書きとPDFは履歴として残り、金額を確認し直して再作成できます。", confirmLabel: "下書きを取り消す" });
    if (!text?.trim()) return;
    setBusy(true); setDialogError("");
    try { await cancelBillingInvoice(id, text); setInvoiceId(null); await refresh(); }
    catch (err) { setDialogError(message(err)); }
    finally { setBusy(false); }
  }

  return <div className="page-stack">
    <PageHeader title="依頼書の金額確定" eyebrow="全体管理者専用" description="クライアントへの請求総額（税抜）を依頼書ごとに確定し、指定した請求月・依頼元別に請求書を作成します。" />
    <section className="card" style={{ padding: "1rem" }}>
      <h3>請求金額の記録　{summary.data ? `未入力 ${summary.data.missing_count}件` : ""}</h3>
      <p className="order-field-hint">確定済みの最新依頼書が対象です。テストは金額入力を試せますが、正式な月次請求書には含まれません。請求先は案件のクライアントに固定します。インセンティブありの金額未確定も未入力件数に含みます。稼働者への支払額とは別です。</p>
      <div className="order-billing-filters">
        <label className="order-check"><input type="checkbox" checked={includeTest} onChange={(e) => { setIncludeTest(e.target.checked); setPage(0); }} />テストも含む</label>
        <label className="order-billing-status">表示<select aria-label="金額確定の表示条件" value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}>
          <option value="missing">金額未入力</option><option value="confirmed">金額確定済み</option><option value="invoice_created">請求書作成済み</option><option value="all">すべて</option>
        </select></label>
        <label className="order-billing-search">依頼書・案件名・依頼元で検索<input aria-label="依頼書・案件名・依頼元で検索" value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} maxLength={100} /></label>
        <button type="button" className="btn btn-ghost" onClick={() => void refresh()}>更新</button>
      </div>
      {error ? <p className="form-error" role="alert">{error}</p> : null}
      {orders.isError || summary.isError ? <p className="form-error">金額一覧・未入力件数を取得できませんでした。更新してお試しください。</p> : null}
      {orders.isLoading ? <p>読み込んでいます…</p> : null}
      <div className="order-list-table"><table className="data-table"><thead><tr><th>依頼書・案件名</th><th>稼働日</th><th>請求先</th><th>請求月</th><th>請求額（税抜）</th><th>インセンティブ</th><th>操作</th></tr></thead><tbody>
        {(orders.data?.items ?? []).map((row) => <tr key={row.version_id}>
          <td><button type="button" className="btn btn-ghost btn-sm" onClick={() => setSource(row.version_id)}>{row.document_number} 第{row.version_no}版</button><div className="order-cell-multiline">{row.is_test ? <TestBadge /> : null}{row.project_name || "案件名なし"}</div><div className="order-cell-multiline">カテゴリ：{row.categories?.join("、") || "未設定"}</div></td>
          <td className="order-cell-multiline">{row.work_date_label}</td><td>{row.client_name}{row.client_mismatch ? <p className="form-error">旧記録の請求先と不一致・再確認が必要</p> : null}</td><td>{row.billing_month ? monthLabel(row.billing_month) : "未設定"}</td><td>{row.amount !== null ? <>通常 {yen(row.amount)}{row.billing_ready && row.incentive_enabled ? <div>合計 {yen(row.total_amount!)}</div> : null}</> : <strong style={{ color: "#dc2626" }}>未入力</strong>}</td>
          <td className="order-cell-multiline">{row.incentive_enabled ? <>{row.incentive_note}<br />{row.incentive_amount !== null ? yen(row.incentive_amount) : <strong className="form-error">金額未確定</strong>}</> : "インセンティブなし"}</td>
          <td><div className="order-row-actions"><button type="button" className="btn create-button btn-sm" disabled={!!row.invoice_id} onClick={() => openEdit(row)}>{row.invoice_id ? "請求書作成済み" : row.amount_id ? "金額・請求月を変更" : "請求金額を確定"}</button>
            {row.invoice_id && !row.amount_id ? <span className="form-error">依頼書が改訂されています。作成済みの請求書を確認してください。</span> : null}
            {row.amount_id ? <button type="button" className="btn btn-ghost btn-sm" onClick={() => void showHistory(row)}>確定履歴</button> : null}
            {row.invoice_id ? <button type="button" className="btn btn-ghost btn-sm" onClick={() => { setDialogError(""); setInvoiceId(row.invoice_id); }}>請求書を確認</button> : null}
          </div></td>
        </tr>)}
      </tbody></table></div>
      {orders.data?.total === 0 ? <p>該当する依頼書はありません。</p> : null}
      <div className="order-template-pagination"><button type="button" className="btn btn-ghost btn-sm" disabled={!page} onClick={() => setPage(page - 1)}>前へ</button><span>{orders.data?.total ?? 0}件</span><button type="button" className="btn btn-ghost btn-sm" disabled={!orders.data || (page + 1) * 30 >= orders.data.total} onClick={() => setPage(page + 1)}>次へ</button></div>
    </section>

    <section className="card" style={{ padding: "1rem" }}>
      <h3>依頼元別の月次請求書</h3>
      <p className="order-field-hint">この画面で金額確定した正式な依頼をまとめます。テストは対象外です。消費税10%・税抜小計に対して円未満切捨て。同じ依頼元・請求月で、実績から生成する既存請求書との重複作成はできません。</p>
      <p className="order-field-hint">発行元・振込先・支払期限は、サイドメニューの「会社情報」で変更します。変更は新しく作成する請求書に反映されます。</p>
      <div className="order-template-actions"><label>請求月<input type="month" value={invoiceMonth} onChange={(e) => { setInvoiceMonth(e.target.value); setInvoicePage(0); }} /></label>
        <button type="button" className="btn create-button" disabled={!invoiceMonth} onClick={() => { setCreateClient(""); setDialogError(""); setCreateOpen(true); }}>月次請求書を作成</button>
        <Link className="btn btn-line-blue" to="/settings/company">会社情報（発行元・振込先）</Link>
      </div>
      {invoices.isError ? <p className="form-error">請求書一覧を取得できませんでした。</p> : null}
      <div className="order-list-table"><table className="data-table"><thead><tr><th>請求書番号</th><th>請求先</th><th>請求月</th><th>状態</th><th>合計（税込）</th><th>操作</th></tr></thead><tbody>
        {(invoices.data?.items ?? []).map((row) => <tr key={row.id}><td>{row.document_number}<br />第{row.version}版</td><td>{row.client_name}</td><td>{monthLabel(row.billing_month)}</td><td>{invoiceStatus[row.status]}</td><td>{yen(row.total_amount)}</td>
          <td><button type="button" className="btn btn-ghost btn-sm" onClick={() => { setDialogError(""); setInvoiceId(row.id); }}>明細・PDFを確認</button></td></tr>)}
      </tbody></table></div>
      <div className="order-template-pagination"><button type="button" className="btn btn-ghost btn-sm" disabled={!invoicePage} onClick={() => setInvoicePage(invoicePage - 1)}>前へ</button><span>{invoices.data?.total ?? 0}件</span><button type="button" className="btn btn-ghost btn-sm" disabled={!invoices.data || (invoicePage + 1) * 30 >= invoices.data.total} onClick={() => setInvoicePage(invoicePage + 1)}>次へ</button></div>
    </section>

    <FormDialog open={!!edit} title="依頼書の請求金額を確定" size="compact" busy={busy} onClose={() => setEdit(null)}>
      <dl className="billing-order-context">
        <div><dt>文書番号</dt><dd>{edit?.document_number} 第{edit?.version_no}版</dd></div>
        <div><dt>案件名</dt><dd>{edit?.is_test ? <TestBadge /> : null}{edit?.project_name || "案件名なし"}</dd></div>
        <div><dt>稼働期間</dt><dd>{edit?.work_date_label || "未設定"}</dd></div>
        <div><dt>カテゴリ</dt><dd>{edit?.categories?.join("、") || "未設定"}</dd></div>
      </dl>
      <label className="order-field">請求先（案件のクライアント・変更不可）<input readOnly value={edit?.client_name || "未設定"} /></label>
      {!edit?.client_id ? <p className="form-error">依頼書の発注元にクライアントを設定してください。</p> : null}
      <label className="order-field">請求月（必須）<input type="month" value={editMonth} disabled={busy} onChange={(e) => setEditMonth(e.target.value)} /></label>
      <p className="order-field-hint">月をまたぐ依頼も、ここで指定した月へ全額計上します。</p>
      <BillingAmountInput label="通常請求額（インセンティブを除く・税抜・円）" value={editAmount} disabled={busy} onChange={setEditAmount} />
      {edit?.incentive_enabled ? <div className="card" style={{ padding: "1rem" }}><strong>インセンティブ条件（依頼書の記載）</strong><p className="order-cell-multiline">{edit.incentive_note}</p>
        <BillingAmountInput label="インセンティブ金額（税抜・円）" value={editIncentive} disabled={busy} onChange={setEditIncentive} />
        <p className="order-field-hint">販売実績が出るまでは空欄で保存できます。空欄の間は未処理として残り、月次請求書を作成できません。実績が0円なら0を入力してください。</p>
        {isValidBillingAmount(editAmount) && isValidBillingAmount(editIncentive) ? <p>請求総額（税抜） {yen(String(Number(editAmount) + Number(editIncentive)))}</p> : null}
      </div> : <p>インセンティブなし</p>}
      <label className="order-field">{edit?.revision ? "変更理由（必須）" : "記録メモ（任意）"}<textarea rows={2} maxLength={2000} value={reason} disabled={busy} onChange={(e) => setReason(e.target.value)} /></label>
      {dialogError ? <p className="form-error" role="alert">{dialogError}</p> : null}
      <button type="button" className="btn create-button" disabled={busy || !edit?.client_id || !editMonth || !isValidBillingAmount(editAmount) || (editIncentive !== "" && !isValidBillingAmount(editIncentive)) || (!!edit?.revision && !reason.trim())} onClick={() => void save()}>{busy ? "保存しています…" : edit?.incentive_enabled && editIncentive === "" ? "通常請求額を保存（インセンティブ未確定）" : "請求金額を確定する"}</button>
    </FormDialog>
    <FormDialog open={createOpen} title="依頼元別の月次請求書を作成" size="compact" busy={busy} onClose={() => setCreateOpen(false)}>
      <p>{invoiceMonth}分。金額確定済みの依頼だけをまとめ、まず未発行の下書きを作成します。</p>
      <label className="order-field">請求先<select value={createClient} disabled={busy} onChange={(e) => setCreateClient(e.target.value)}><option value="">依頼元を選択</option>{clients.data?.items.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label className="order-field">請求日<input type="date" value={createDate} disabled={busy} onChange={(e) => setCreateDate(e.target.value)} /></label>
      {dialogError ? <p className="form-error" role="alert">{dialogError}</p> : null}
      <button type="button" className="btn create-button" disabled={busy || !createClient || !createDate} onClick={() => void create()}>{busy ? "作成しています…" : "請求書の下書きを作成"}</button>
    </FormDialog>
    <FormDialog open={!!invoiceId} title="月次請求書の確認" busy={busy} onClose={() => setInvoiceId(null)}>
      {invoice.isLoading ? <p>読み込んでいます…</p> : null}
      {invoice.isError ? <p className="form-error">請求書を取得できませんでした。</p> : null}
      {invoice.data ? <><h4>{invoice.data.client_name}　{monthLabel(invoice.data.billing_month)}　{invoiceStatus[invoice.data.status]}</h4><p>{invoice.data.document_number}　第{invoice.data.version}版</p>
        <div className="order-list-table"><table className="data-table"><thead><tr><th>依頼書</th><th>案件名・稼働日</th><th>税抜金額</th></tr></thead><tbody>{invoice.data.lines?.map((line) => <tr key={line.id}><td>{line.document_number}</td><td className="order-cell-multiline">{line.description}<br />{line.work_date_label}{line.incentive_amount != null ? <><br />インセンティブ：{line.incentive_note}<br />内訳：通常 {yen(String(Number(line.amount) - Number(line.incentive_amount)))} ＋ インセンティブ {yen(line.incentive_amount)}</> : null}</td><td>{yen(line.amount)}</td></tr>)}</tbody></table></div>
        <p>税抜小計 {yen(invoice.data.subtotal)} ／ 消費税 {yen(invoice.data.tax_amount)} ／ 合計 {yen(invoice.data.total_amount)}</p>
        <div className="order-cell-multiline"><strong>発行元：{invoice.data.issuer_snapshot?.name}</strong><br />{invoice.data.issuer_snapshot?.postal_code ? `〒${invoice.data.issuer_snapshot.postal_code} ` : ""}{invoice.data.issuer_snapshot?.address}<br />{invoice.data.issuer_snapshot?.phone ? <>TEL：{invoice.data.issuer_snapshot.phone}<br /></> : null}{invoice.data.issuer_snapshot?.email ? <>メール：{invoice.data.issuer_snapshot.email}<br /></> : null}{invoice.data.issuer_snapshot?.registration_number ? `登録番号：${invoice.data.issuer_snapshot.registration_number}` : "登録番号：未設定"}<br />振込先：{invoice.data.issuer_snapshot?.bank_details || "未設定"}<br />支払期限・条件：{invoice.data.issuer_snapshot?.payment_terms || "未設定"}</div>
        <div className="order-template-actions"><button type="button" className="btn btn-line-blue" disabled={busy} onClick={() => void showPdf(invoice.data!.id)}>PDFを表示</button>
          {invoice.data.status === "draft" ? <><button type="button" className="btn create-button" disabled={busy} onClick={() => void issue(invoice.data!.id)}>確認して発行する</button><button type="button" className="btn btn-ghost" disabled={busy} onClick={() => void cancel(invoice.data!.id)}>下書きを取り消す</button></> : null}
        </div>
      </> : null}
      {dialogError ? <p className="form-error" role="alert">{dialogError}</p> : null}
    </FormDialog>
    <FormDialog open={!!pdfUrl} title="月次請求書PDF" onClose={() => setPdfUrl(null)}>{pdfUrl ? <iframe title="月次請求書PDF" src={pdfUrl} style={{ width: "100%", height: "70vh", border: 0 }} /> : null}</FormDialog>
    <FormDialog open={!!history} title={`金額確定履歴 ${history?.title || ""}`} onClose={() => setHistory(null)}>{history?.items.map((r) => <p className="order-cell-multiline" key={r.revision}>第{r.revision}版　{r.client_name}　{monthLabel(r.billing_month)}　通常 {yen(r.amount)}{r.incentive_enabled ? <><br />インセンティブ：{r.incentive_note}　{r.incentive_amount !== null ? yen(r.incentive_amount) : "金額未確定"}</> : null}<br />{r.reason || "初回確定"}　{r.created_at}</p>)}</FormDialog>
    {source ? <OrderRequestDetailDialog versionId={source} onClose={() => setSource(null)} /> : null}
  </div>;
}
