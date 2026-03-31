import { Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { FilterBar } from "../components/FilterBar";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import { useAuth } from "../lib/auth/auth-context";
import {
  ApiError,
  createPriceOutsource,
  createPriceRule,
  createPriceSales,
  getClients,
  getPriceOutsource,
  getPriceRules,
  getPriceSales,
  getProjects,
  getRoles,
  getWorkers,
  updatePriceOutsource,
  updatePriceRule,
  updatePriceSales,
} from "../lib/api/client";
import { formatCurrency, formatDate } from "../lib/formatters";
import type { PriceOutsourceListItem, PriceRuleListItem, PriceSalesListItem } from "../types/api";

const PAGE_SIZE = 20;

type PriceView = "sales" | "outsource" | "rules";
type SavePriceVariables =
  | { mode: "create"; view: "sales"; body: { project_id: string | null; role_id: string | null; client_id: string | null; unit_price: string; unit_type: "hourly" | "daily" | "monthly" | "fixed"; valid_from: string | null; valid_to: string | null; is_default: boolean; notes: string | null } }
  | { mode: "update"; view: "sales"; id: string; body: { project_id: string | null; role_id: string | null; client_id: string | null; unit_price: string; unit_type: "hourly" | "daily" | "monthly" | "fixed"; valid_from: string | null; valid_to: string | null; is_default: boolean; notes: string | null } }
  | { mode: "create"; view: "outsource"; body: { project_id: string | null; worker_id: string | null; role_id: string | null; unit_price: string; unit_type: "hourly" | "daily" | "monthly" | "fixed"; valid_from: string | null; valid_to: string | null; is_default: boolean; notes: string | null } }
  | { mode: "update"; view: "outsource"; id: string; body: { project_id: string | null; worker_id: string | null; role_id: string | null; unit_price: string; unit_type: "hourly" | "daily" | "monthly" | "fixed"; valid_from: string | null; valid_to: string | null; is_default: boolean; notes: string | null } }
  | { mode: "create"; view: "rules"; body: { name: string; priority: number; conditions: Record<string, unknown>; sales_price: string | null; outsource_price: string | null; valid_from: string | null; valid_to: string | null; is_active: boolean; notes: string | null } }
  | { mode: "update"; view: "rules"; id: string; body: { name: string; priority: number; conditions: Record<string, unknown>; sales_price: string | null; outsource_price: string | null; valid_from: string | null; valid_to: string | null; is_active: boolean; notes: string | null } };

function formatUnitType(unitType: string): string {
  const labels: Record<string, string> = {
    hourly: "時給",
    daily: "日給",
    monthly: "月額",
    fixed: "固定",
  };

  return labels[unitType] || unitType;
}

export function PriceManagementPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [priceView, setPriceView] = useState<PriceView>("sales");
  const [page, setPage] = useState(0);
  const [sortOrder, setSortOrder] = useState("desc");
  const [defaultOnly, setDefaultOnly] = useState("");
  const [activeOnly, setActiveOnly] = useState("");
  const [search, setSearch] = useState("");
  const [salesSortBy, setSalesSortBy] = useState("valid_from");
  const [outsourceSortBy, setOutsourceSortBy] = useState("valid_from");
  const [ruleSortBy, setRuleSortBy] = useState("priority");
  const [selectedSales, setSelectedSales] = useState<PriceSalesListItem | null>(null);
  const [selectedOutsource, setSelectedOutsource] = useState<PriceOutsourceListItem | null>(null);
  const [selectedRule, setSelectedRule] = useState<PriceRuleListItem | null>(null);
  const [formError, setFormError] = useState("");
  const [formMessage, setFormMessage] = useState("");
  const [ruleName, setRuleName] = useState("");
  const [rulePriority, setRulePriority] = useState("100");
  const [ruleConditions, setRuleConditions] = useState('{"default": true}');
  const [ruleSalesPrice, setRuleSalesPrice] = useState("");
  const [ruleOutsourcePrice, setRuleOutsourcePrice] = useState("");
  const [ruleValidFrom, setRuleValidFrom] = useState("");
  const [ruleValidTo, setRuleValidTo] = useState("");
  const [ruleIsActive, setRuleIsActive] = useState(true);
  const [ruleNotes, setRuleNotes] = useState("");
  const [salesProjectId, setSalesProjectId] = useState("");
  const [salesClientId, setSalesClientId] = useState("");
  const [salesRoleId, setSalesRoleId] = useState("");
  const [salesUnitPrice, setSalesUnitPrice] = useState("");
  const [salesUnitType, setSalesUnitType] = useState<"hourly" | "daily" | "monthly" | "fixed">("hourly");
  const [salesValidFrom, setSalesValidFrom] = useState("");
  const [salesValidTo, setSalesValidTo] = useState("");
  const [salesIsDefault, setSalesIsDefault] = useState(false);
  const [salesNotes, setSalesNotes] = useState("");
  const [outProjectId, setOutProjectId] = useState("");
  const [outWorkerId, setOutWorkerId] = useState("");
  const [outRoleId, setOutRoleId] = useState("");
  const [outUnitPrice, setOutUnitPrice] = useState("");
  const [outUnitType, setOutUnitType] = useState<"hourly" | "daily" | "monthly" | "fixed">("hourly");
  const [outValidFrom, setOutValidFrom] = useState("");
  const [outValidTo, setOutValidTo] = useState("");
  const [outIsDefault, setOutIsDefault] = useState(false);
  const [outNotes, setOutNotes] = useState("");

  function clearStatus() {
    setFormError("");
    setFormMessage("");
  }

  function clearSelection() {
    setSelectedSales(null);
    setSelectedOutsource(null);
    setSelectedRule(null);
  }

  function resetRuleForm() {
    setRuleName("");
    setRulePriority("100");
    setRuleConditions('{"default": true}');
    setRuleSalesPrice("");
    setRuleOutsourcePrice("");
    setRuleValidFrom("");
    setRuleValidTo("");
    setRuleIsActive(true);
    setRuleNotes("");
  }

  function resetSalesForm() {
    setSalesProjectId("");
    setSalesClientId("");
    setSalesRoleId("");
    setSalesUnitPrice("");
    setSalesUnitType("hourly");
    setSalesValidFrom("");
    setSalesValidTo("");
    setSalesIsDefault(false);
    setSalesNotes("");
  }

  function resetOutsourceForm() {
    setOutProjectId("");
    setOutWorkerId("");
    setOutRoleId("");
    setOutUnitPrice("");
    setOutUnitType("hourly");
    setOutValidFrom("");
    setOutValidTo("");
    setOutIsDefault(false);
    setOutNotes("");
  }

  function resetCurrentForm() {
    clearSelection();
    clearStatus();
    resetRuleForm();
    resetSalesForm();
    resetOutsourceForm();
  }

  const salesQuery = useQuery({
    queryKey: ["price-sales-page", defaultOnly, salesSortBy, sortOrder, page],
    queryFn: () => getPriceSales({ is_default: defaultOnly === "" ? undefined : defaultOnly === "true", sort_by: salesSortBy, sort_order: sortOrder, offset: page * PAGE_SIZE, limit: PAGE_SIZE }),
    enabled: priceView === "sales",
  });

  const outsourceQuery = useQuery({
    queryKey: ["price-outsource-page", defaultOnly, outsourceSortBy, sortOrder, page],
    queryFn: () => getPriceOutsource({ is_default: defaultOnly === "" ? undefined : defaultOnly === "true", sort_by: outsourceSortBy, sort_order: sortOrder, offset: page * PAGE_SIZE, limit: PAGE_SIZE }),
    enabled: priceView === "outsource",
  });

  const rulesQuery = useQuery({
    queryKey: ["price-rules-page", search, activeOnly, ruleSortBy, sortOrder, page],
    queryFn: () => getPriceRules({ search: search || undefined, is_active: activeOnly === "" ? undefined : activeOnly === "true", sort_by: ruleSortBy, sort_order: sortOrder, offset: page * PAGE_SIZE, limit: PAGE_SIZE }),
    enabled: priceView === "rules",
  });

  const projectsQuery = useQuery({
    queryKey: ["price-form-projects"],
    queryFn: () => getProjects({ limit: 200, sort_by: "name", sort_order: "asc" }),
    enabled: user?.role === "admin",
  });

  const clientsQuery = useQuery({
    queryKey: ["price-form-clients"],
    queryFn: () => getClients({ limit: 200, sort_by: "name", sort_order: "asc" }),
    enabled: user?.role === "admin",
  });

  const workersQuery = useQuery({
    queryKey: ["price-form-workers"],
    queryFn: () => getWorkers({ limit: 200, sort_by: "name", sort_order: "asc", is_active: true }),
    enabled: user?.role === "admin",
  });

  const rolesQuery = useQuery({
    queryKey: ["price-form-roles"],
    queryFn: () => getRoles({ limit: 200, sort_by: "name", sort_order: "asc" }),
    enabled: user?.role === "admin",
  });

  const activeQuery = priceView === "sales" ? salesQuery : priceView === "outsource" ? outsourceQuery : rulesQuery;

  const saveMutation = useMutation<unknown, unknown, SavePriceVariables>({
    mutationFn: async (variables) => {
      if (variables.view === "sales") {
        return variables.mode === "create" ? createPriceSales(variables.body) : updatePriceSales(variables.id, variables.body);
      }
      if (variables.view === "outsource") {
        return variables.mode === "create" ? createPriceOutsource(variables.body) : updatePriceOutsource(variables.id, variables.body);
      }
      return variables.mode === "create" ? createPriceRule(variables.body) : updatePriceRule(variables.id, variables.body);
    },
    onSuccess: async (_, variables) => {
      setFormError("");
      setFormMessage(variables.mode === "create" ? "単価を作成しました" : "単価を更新しました");
      if (variables.view === "sales") {
        await queryClient.invalidateQueries({ queryKey: ["price-sales-page"] });
        resetSalesForm();
      } else if (variables.view === "outsource") {
        await queryClient.invalidateQueries({ queryKey: ["price-outsource-page"] });
        resetOutsourceForm();
      } else {
        await queryClient.invalidateQueries({ queryKey: ["price-rules-page"] });
        resetRuleForm();
      }
      clearSelection();
    },
    onError: (error: unknown) => {
      setFormMessage("");
      setFormError(error instanceof ApiError ? error.message : "単価の保存に失敗しました");
    },
  });

  function openSalesEditor(row: PriceSalesListItem) {
    clearSelection();
    clearStatus();
    setSelectedSales(row);
    setSalesProjectId(row.project_id ?? "");
    setSalesClientId(row.client_id ?? "");
    setSalesRoleId(row.role_id ?? "");
    setSalesUnitPrice(row.unit_price);
    setSalesUnitType(row.unit_type as "hourly" | "daily" | "monthly" | "fixed");
    setSalesValidFrom(row.valid_from ?? "");
    setSalesValidTo(row.valid_to ?? "");
    setSalesIsDefault(row.is_default);
    setSalesNotes(row.notes ?? "");
  }

  function openOutsourceEditor(row: PriceOutsourceListItem) {
    clearSelection();
    clearStatus();
    setSelectedOutsource(row);
    setOutProjectId(row.project_id ?? "");
    setOutWorkerId(row.worker_id ?? "");
    setOutRoleId(row.role_id ?? "");
    setOutUnitPrice(row.unit_price);
    setOutUnitType(row.unit_type as "hourly" | "daily" | "monthly" | "fixed");
    setOutValidFrom(row.valid_from ?? "");
    setOutValidTo(row.valid_to ?? "");
    setOutIsDefault(row.is_default);
    setOutNotes(row.notes ?? "");
  }

  function openRuleEditor(row: PriceRuleListItem) {
    clearSelection();
    clearStatus();
    setSelectedRule(row);
    setRuleName(row.name);
    setRulePriority(String(row.priority));
    setRuleConditions(JSON.stringify(row.conditions, null, 2));
    setRuleSalesPrice(row.sales_price ?? "");
    setRuleOutsourcePrice(row.outsource_price ?? "");
    setRuleValidFrom(row.valid_from ?? "");
    setRuleValidTo(row.valid_to ?? "");
    setRuleIsActive(row.is_active);
    setRuleNotes(row.notes ?? "");
  }

  function saveCurrentPrice() {
    setFormError("");
    setFormMessage("");

    if (priceView === "sales") {
      const body = {
        project_id: salesProjectId || null,
        role_id: salesRoleId || null,
        client_id: salesClientId || null,
        unit_price: salesUnitPrice,
        unit_type: salesUnitType,
        valid_from: salesValidFrom || null,
        valid_to: salesValidTo || null,
        is_default: salesIsDefault,
        notes: salesNotes || null,
      };
      if (selectedSales) {
        saveMutation.mutate({ mode: "update", view: "sales", id: selectedSales.id, body });
      } else {
        saveMutation.mutate({ mode: "create", view: "sales", body });
      }
      return;
    }

    if (priceView === "outsource") {
      const body = {
        project_id: outProjectId || null,
        worker_id: outWorkerId || null,
        role_id: outRoleId || null,
        unit_price: outUnitPrice,
        unit_type: outUnitType,
        valid_from: outValidFrom || null,
        valid_to: outValidTo || null,
        is_default: outIsDefault,
        notes: outNotes || null,
      };
      if (selectedOutsource) {
        saveMutation.mutate({ mode: "update", view: "outsource", id: selectedOutsource.id, body });
      } else {
        saveMutation.mutate({ mode: "create", view: "outsource", body });
      }
      return;
    }

    let parsedConditions: Record<string, unknown>;
    try {
      parsedConditions = JSON.parse(ruleConditions) as Record<string, unknown>;
    } catch {
      setFormError("条件 JSON の形式が不正です");
      return;
    }

    const body = {
      name: ruleName,
      priority: Number(rulePriority || 100),
      conditions: parsedConditions,
      sales_price: ruleSalesPrice || null,
      outsource_price: ruleOutsourcePrice || null,
      valid_from: ruleValidFrom || null,
      valid_to: ruleValidTo || null,
      is_active: ruleIsActive,
      notes: ruleNotes || null,
    };
    if (selectedRule) {
      saveMutation.mutate({ mode: "update", view: "rules", id: selectedRule.id, body });
    } else {
      saveMutation.mutate({ mode: "create", view: "rules", body });
    }
  }

  if (activeQuery.isLoading) {
    return <LoadingOverlay label="単価一覧を読み込み中..." />;
  }

  if (activeQuery.error instanceof ApiError && activeQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (activeQuery.isError || !activeQuery.data) {
    return <ErrorState title="単価一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="単価一覧" description="売上単価、外注単価、単価ルールを参照し、admin は追加・更新できます。" />
      <section className="upload-card">
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <strong>表示切替</strong>
          <button type="button" onClick={() => { setPriceView("sales"); setPage(0); resetCurrentForm(); }} style={{ opacity: priceView === "sales" ? 1 : 0.7 }}>売上単価</button>
          <button type="button" onClick={() => { setPriceView("outsource"); setPage(0); resetCurrentForm(); }} style={{ opacity: priceView === "outsource" ? 1 : 0.7 }}>外注単価</button>
          <button type="button" onClick={() => { setPriceView("rules"); setPage(0); resetCurrentForm(); }} style={{ opacity: priceView === "rules" ? 1 : 0.7 }}>単価ルール</button>
        </div>
      </section>

      {user?.role === "admin" ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <strong>{selectedSales || selectedOutsource || selectedRule ? "単価を編集" : "単価を追加"}</strong>

          {priceView === "sales" ? (
            <>
              <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
                <label>
                  案件
                  <select value={salesProjectId} onChange={(event) => setSalesProjectId(event.target.value)}>
                    <option value="">未設定</option>
                    {(projectsQuery.data?.items ?? []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  取引先
                  <select value={salesClientId} onChange={(event) => setSalesClientId(event.target.value)}>
                    <option value="">未設定</option>
                    {(clientsQuery.data?.items ?? []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  役割
                  <select value={salesRoleId} onChange={(event) => setSalesRoleId(event.target.value)}>
                    <option value="">未設定</option>
                    {(rolesQuery.data?.items ?? []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  単価
                  <input value={salesUnitPrice} onChange={(event) => setSalesUnitPrice(event.target.value)} placeholder="15000.00" />
                </label>
                <label>
                  単位
                  <select value={salesUnitType} onChange={(event) => setSalesUnitType(event.target.value as typeof salesUnitType)}>
                    <option value="hourly">時給</option>
                    <option value="daily">日給</option>
                    <option value="monthly">月額</option>
                    <option value="fixed">固定</option>
                  </select>
                </label>
                <label>
                  開始日
                  <input type="date" value={salesValidFrom} onChange={(event) => setSalesValidFrom(event.target.value)} />
                </label>
                <label>
                  終了日
                  <input type="date" value={salesValidTo} onChange={(event) => setSalesValidTo(event.target.value)} />
                </label>
              </div>
              <label>
                メモ
                <textarea value={salesNotes} onChange={(event) => setSalesNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input type="checkbox" checked={salesIsDefault} onChange={(event) => setSalesIsDefault(event.target.checked)} />
                既定単価
              </label>
            </>
          ) : null}

          {priceView === "outsource" ? (
            <>
              <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
                <label>
                  案件
                  <select value={outProjectId} onChange={(event) => setOutProjectId(event.target.value)}>
                    <option value="">未設定</option>
                    {(projectsQuery.data?.items ?? []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  稼働者
                  <select value={outWorkerId} onChange={(event) => setOutWorkerId(event.target.value)}>
                    <option value="">未設定</option>
                    {(workersQuery.data?.items ?? []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  役割
                  <select value={outRoleId} onChange={(event) => setOutRoleId(event.target.value)}>
                    <option value="">未設定</option>
                    {(rolesQuery.data?.items ?? []).map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
                  </select>
                </label>
                <label>
                  単価
                  <input value={outUnitPrice} onChange={(event) => setOutUnitPrice(event.target.value)} placeholder="9000.00" />
                </label>
                <label>
                  単位
                  <select value={outUnitType} onChange={(event) => setOutUnitType(event.target.value as typeof outUnitType)}>
                    <option value="hourly">時給</option>
                    <option value="daily">日給</option>
                    <option value="monthly">月額</option>
                    <option value="fixed">固定</option>
                  </select>
                </label>
                <label>
                  開始日
                  <input type="date" value={outValidFrom} onChange={(event) => setOutValidFrom(event.target.value)} />
                </label>
                <label>
                  終了日
                  <input type="date" value={outValidTo} onChange={(event) => setOutValidTo(event.target.value)} />
                </label>
              </div>
              <label>
                メモ
                <textarea value={outNotes} onChange={(event) => setOutNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input type="checkbox" checked={outIsDefault} onChange={(event) => setOutIsDefault(event.target.checked)} />
                既定単価
              </label>
            </>
          ) : null}

          {priceView === "rules" ? (
            <>
              <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
                <label>
                  ルール名
                  <input value={ruleName} onChange={(event) => setRuleName(event.target.value)} placeholder="ルール名" />
                </label>
                <label>
                  優先順位
                  <input type="number" min="0" value={rulePriority} onChange={(event) => setRulePriority(event.target.value)} />
                </label>
                <label>
                  売上単価
                  <input value={ruleSalesPrice} onChange={(event) => setRuleSalesPrice(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  外注単価
                  <input value={ruleOutsourcePrice} onChange={(event) => setRuleOutsourcePrice(event.target.value)} placeholder="任意" />
                </label>
                <label>
                  開始日
                  <input type="date" value={ruleValidFrom} onChange={(event) => setRuleValidFrom(event.target.value)} />
                </label>
                <label>
                  終了日
                  <input type="date" value={ruleValidTo} onChange={(event) => setRuleValidTo(event.target.value)} />
                </label>
              </div>
              <label>
                条件 JSON
                <textarea value={ruleConditions} onChange={(event) => setRuleConditions(event.target.value)} rows={6} style={{ width: "100%", resize: "vertical", fontFamily: "monospace" }} />
              </label>
              <label>
                メモ
                <textarea value={ruleNotes} onChange={(event) => setRuleNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input type="checkbox" checked={ruleIsActive} onChange={(event) => setRuleIsActive(event.target.checked)} />
                有効
              </label>
            </>
          ) : null}

          {formError ? <p className="form-error">{formError}</p> : null}
          {formMessage ? <p>{formMessage}</p> : null}
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <button
              type="button"
              className="primary-button"
              onClick={saveCurrentPrice}
              disabled={saveMutation.isPending || (priceView === "rules" ? !ruleName.trim() : priceView === "sales" ? !salesUnitPrice.trim() : !outUnitPrice.trim())}
            >
              {saveMutation.isPending ? "保存中..." : selectedSales || selectedOutsource || selectedRule ? "更新する" : "追加する"}
            </button>
            <button type="button" onClick={resetCurrentForm}>入力をクリア</button>
          </div>
        </section>
      ) : null}

      <FilterBar>
        {priceView === "rules" ? (
          <>
            <label>
              検索
              <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="ルール名" />
            </label>
            <label>
              稼働状態
              <select value={activeOnly} onChange={(event) => { setActiveOnly(event.target.value); setPage(0); }}>
                <option value="">すべて</option>
                <option value="true">有効のみ</option>
                <option value="false">無効のみ</option>
              </select>
            </label>
            <label>
              ソート
              <select value={ruleSortBy} onChange={(event) => { setRuleSortBy(event.target.value); setPage(0); }}>
                <option value="priority">優先順位</option>
                <option value="name">ルール名</option>
                <option value="valid_from">開始日</option>
                <option value="valid_to">終了日</option>
              </select>
            </label>
          </>
        ) : (
          <>
            <label>
              既定単価
              <select value={defaultOnly} onChange={(event) => { setDefaultOnly(event.target.value); setPage(0); }}>
                <option value="">すべて</option>
                <option value="true">既定のみ</option>
                <option value="false">個別のみ</option>
              </select>
            </label>
            <label>
              ソート
              <select value={priceView === "sales" ? salesSortBy : outsourceSortBy} onChange={(event) => { if (priceView === "sales") { setSalesSortBy(event.target.value); } else { setOutsourceSortBy(event.target.value); } setPage(0); }}>
                <option value="valid_from">開始日</option>
                <option value="valid_to">終了日</option>
                <option value="unit_price">単価</option>
                <option value="project_name">案件名</option>
                <option value="role_name">役割名</option>
                {priceView === "sales" ? <option value="client_name">取引先名</option> : <option value="worker_name">稼働者名</option>}
              </select>
            </label>
          </>
        )}
        <label>
          順序
          <select value={sortOrder} onChange={(event) => { setSortOrder(event.target.value); setPage(0); }}>
            <option value="desc">降順</option>
            <option value="asc">昇順</option>
          </select>
        </label>
      </FilterBar>

      {priceView === "sales" ? (
        <DataTable
          columns={[
            { key: "project", header: "案件", render: (row) => row.project_name || "既定単価" },
            { key: "client", header: "取引先", render: (row) => row.client_name || "-" },
            { key: "role", header: "役割", render: (row) => row.role_name || "-" },
            { key: "price", header: "単価", render: (row) => formatCurrency(row.unit_price) },
            { key: "unitType", header: "単位", render: (row) => formatUnitType(row.unit_type) },
            { key: "validFrom", header: "開始日", render: (row) => formatDate(row.valid_from) },
            { key: "validTo", header: "終了日", render: (row) => formatDate(row.valid_to) },
            { key: "default", header: "適用", render: (row) => (row.is_default ? "既定" : "個別") },
            { key: "actions", header: "操作", render: (row) => user?.role === "admin" ? <button type="button" onClick={() => openSalesEditor(row)}>編集</button> : "—" },
          ]}
          rows={salesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="売上単価はありません"
          emptyDescription="条件に一致する売上単価は見つかりませんでした。"
        />
      ) : null}

      {priceView === "outsource" ? (
        <DataTable
          columns={[
            { key: "project", header: "案件", render: (row) => row.project_name || "既定単価" },
            { key: "worker", header: "稼働者", render: (row) => row.worker_name || "-" },
            { key: "role", header: "役割", render: (row) => row.role_name || "-" },
            { key: "price", header: "単価", render: (row) => formatCurrency(row.unit_price) },
            { key: "unitType", header: "単位", render: (row) => formatUnitType(row.unit_type) },
            { key: "validFrom", header: "開始日", render: (row) => formatDate(row.valid_from) },
            { key: "validTo", header: "終了日", render: (row) => formatDate(row.valid_to) },
            { key: "default", header: "適用", render: (row) => (row.is_default ? "既定" : "個別") },
            { key: "actions", header: "操作", render: (row) => user?.role === "admin" ? <button type="button" onClick={() => openOutsourceEditor(row)}>編集</button> : "—" },
          ]}
          rows={outsourceQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="外注単価はありません"
          emptyDescription="条件に一致する外注単価は見つかりませんでした。"
        />
      ) : null}

      {priceView === "rules" ? (
        <DataTable
          columns={[
            { key: "priority", header: "優先順位", render: (row) => row.priority },
            { key: "name", header: "ルール名", render: (row) => row.name },
            { key: "salesPrice", header: "売上単価", render: (row) => formatCurrency(row.sales_price) },
            { key: "outsourcePrice", header: "外注単価", render: (row) => formatCurrency(row.outsource_price) },
            { key: "validFrom", header: "開始日", render: (row) => formatDate(row.valid_from) },
            { key: "validTo", header: "終了日", render: (row) => formatDate(row.valid_to) },
            { key: "status", header: "状態", render: (row) => <StatusBadge value={row.is_active ? "active" : "inactive"} /> },
            { key: "actions", header: "操作", render: (row) => user?.role === "admin" ? <button type="button" onClick={() => openRuleEditor(row)}>編集</button> : "—" },
          ]}
          rows={rulesQuery.data?.items ?? []}
          getRowKey={(row) => row.id}
          emptyTitle="単価ルールはありません"
          emptyDescription="条件に一致する単価ルールは見つかりませんでした。"
        />
      ) : null}

      <PaginationBar page={page} total={activeQuery.data.total} limit={activeQuery.data.limit} onPrevious={() => setPage((value) => Math.max(0, value - 1))} onNext={() => setPage((value) => value + 1)} />
    </div>
  );
}