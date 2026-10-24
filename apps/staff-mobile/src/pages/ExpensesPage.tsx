import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, downloadExpenseReceipt, getAssignments, getExpenses, submitExpense } from "../lib/api/client";
import { currentDateInput, currentMonthInput, formatCurrency, formatDate, formatStatus, periodKeyToDateRange, toPeriodKey } from "../lib/formatters";

const expenseCategories = ["交通費", "材料費", "備品", "その他"];

export function ExpensesPage() {
  const queryClient = useQueryClient();
  const [monthValue, setMonthValue] = useState(currentMonthInput());
  const [projectId, setProjectId] = useState("");
  const [expenseDate, setExpenseDate] = useState(currentDateInput());
  const [category, setCategory] = useState(expenseCategories[0]);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const periodKey = toPeriodKey(monthValue);
  const { from, to } = periodKeyToDateRange(periodKey);

  const assignmentsQuery = useQuery({
    queryKey: ["staff-expense-projects", periodKey],
    queryFn: () =>
      getAssignments({
        work_date_from: from,
        work_date_to: to,
        sort_by: "work_date",
        sort_order: "desc",
        limit: 100,
      }),
  });

  const expensesQuery = useQuery({
    queryKey: ["staff-expenses", periodKey],
    queryFn: () =>
      getExpenses({
        expense_date_from: from,
        expense_date_to: to,
        sort_by: "expense_date",
        sort_order: "desc",
        limit: 50,
      }),
  });

  const projectOptions: Array<{ id: string; name: string }> = [];
  for (const item of assignmentsQuery.data?.items ?? []) {
    if (!projectOptions.some((option) => option.id === item.project_id)) {
      projectOptions.push({ id: item.project_id, name: item.project_name });
    }
  }

  useEffect(() => {
    if (!projectId && projectOptions.length > 0) {
      setProjectId(projectOptions[0].id);
    }
  }, [projectId, projectOptions]);

  const submitMutation = useMutation({
    mutationFn: (formData: FormData) => submitExpense(formData),
    onSuccess: async () => {
      setMessage("経費を申請しました。");
      setAmount("");
      setDescription("");
      setReceiptFile(null);
      await queryClient.invalidateQueries({ queryKey: ["staff-expenses", periodKey] });
    },
    onError: (error) => {
      setMessage(error instanceof ApiError ? error.message : "経費申請に失敗しました。");
    },
  });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);

    const formData = new FormData(event.currentTarget);
    if (receiptFile) {
      formData.set("receipt", receiptFile);
    }
    submitMutation.mutate(formData);
  };

  if (assignmentsQuery.isLoading || expensesQuery.isLoading) {
    return <div className="panel-card">経費情報を読み込み中...</div>;
  }

  if (assignmentsQuery.isError || expensesQuery.isError) {
    return (
      <div className="panel-card">
        <h2>経費情報を取得できませんでした</h2>
        <p>
          {assignmentsQuery.error instanceof ApiError
            ? assignmentsQuery.error.message
            : expensesQuery.error instanceof ApiError
              ? expensesQuery.error.message
              : "API 疎通を確認してください。"}
        </p>
      </div>
    );
  }

  const expenses = expensesQuery.data?.items ?? [];

  return (
    <div className="page-stack">
      <section className="hero-panel tide">
        <p className="panel-label">経費申請</p>
        <div className="month-toolbar">
          <h2>{monthValue}</h2>
          <input type="month" value={monthValue} onChange={(event) => setMonthValue(event.target.value)} />
        </div>
        <p>自分の配置案件に対して、そのまま経費を申請します。</p>
      </section>

      <section className="panel-card accent-sand">
        <form className="expense-form" onSubmit={handleSubmit}>
          <label>
            案件
            <select name="project_id" value={projectId} onChange={(event) => setProjectId(event.target.value)} disabled={projectOptions.length === 0}>
              {projectOptions.length === 0 ? <option value="">案件がありません</option> : null}
              {projectOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </label>

          <div className="two-up form-grid">
            <label>
              日付
              <input type="date" name="expense_date" value={expenseDate} onChange={(event) => setExpenseDate(event.target.value)} />
            </label>
            <label>
              区分
              <select name="category" value={category} onChange={(event) => setCategory(event.target.value)}>
                {expenseCategories.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label>
            金額
            <input type="number" name="amount" inputMode="decimal" min="1" step="1" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="1250" />
          </label>

          <label>
            内容
            <textarea name="description" rows={3} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="移動内容や立替理由を入力" />
          </label>

          <label>
            領収書
            <input
              type="file"
              name="receipt"
              accept="image/*,.pdf"
              onChange={(event) => setReceiptFile(event.target.files?.[0] || null)}
            />
          </label>

          {message ? <p className="note-banner">{message}</p> : null}

          <div className="button-row">
            <button type="submit" className="primary-button" disabled={submitMutation.isPending || !projectId || !amount}>
              {submitMutation.isPending ? "送信中..." : "経費を申請する"}
            </button>
          </div>
        </form>
      </section>

      <section className="list-section">
        <div className="section-heading">
          <h2>今月の申請</h2>
          <span>{expenses.length} 件</span>
        </div>

        {expenses.length === 0 ? (
          <div className="panel-card empty-card">対象月の経費申請はありません。</div>
        ) : (
          expenses.map((expense) => (
            <article key={expense.id} className="actual-card">
              <div className="assignment-header">
                <div>
                  <p className="panel-label">{expense.project_name}</p>
                  <h3>{expense.category}</h3>
                </div>
                <span className={`status-pill status-${expense.status}`}>{formatStatus(expense.status)}</span>
              </div>
              <dl className="detail-grid">
                <div>
                  <dt>日付</dt>
                  <dd>{formatDate(expense.expense_date)}</dd>
                </div>
                <div>
                  <dt>金額</dt>
                  <dd>{formatCurrency(expense.amount)}</dd>
                </div>
                <div>
                  <dt>申請者</dt>
                  <dd>{expense.worker_name}</dd>
                </div>
                <div>
                  <dt>領収書</dt>
                  <dd>{expense.has_receipt ? "あり" : "なし"}</dd>
                </div>
              </dl>
              {expense.reject_reason ? <p className="note-banner">却下理由: {expense.reject_reason}</p> : null}
              {expense.has_receipt ? (
                <div className="button-row">
                  <button
                    type="button"
                    onClick={() => {
                      setMessage(null);
                      void downloadExpenseReceipt(expense.id).catch((error: unknown) => {
                        setMessage(error instanceof ApiError ? error.message : "領収書のダウンロードに失敗しました。");
                      });
                    }}
                  >
                    領収書を開く
                  </button>
                </div>
              ) : null}
            </article>
          ))
        )}
      </section>
    </div>
  );
}