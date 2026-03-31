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
import { ApiError, createProject, getClients, getProjectTypes, getProjects, getSites, getWorkers, updateProject } from "../lib/api/client";
import { formatDate } from "../lib/formatters";
import type { ProjectListItem } from "../types/api";

const PAGE_SIZE = 20;

export function ProjectsPage() {
  const [search, setSearch] = useState("");
  const [isActive, setIsActive] = useState("");
  const [sortBy, setSortBy] = useState("name");
  const [sortOrder, setSortOrder] = useState("asc");
  const [page, setPage] = useState(0);
  const [createName, setCreateName] = useState("");
  const [createCode, setCreateCode] = useState("");
  const [createClientId, setCreateClientId] = useState("");
  const [createSiteId, setCreateSiteId] = useState("");
  const [createProjectTypeId, setCreateProjectTypeId] = useState("");
  const [createPrimaryManagerId, setCreatePrimaryManagerId] = useState("");
  const [createSecondaryManagerId, setCreateSecondaryManagerId] = useState("");
  const [createStartDate, setCreateStartDate] = useState("");
  const [createEndDate, setCreateEndDate] = useState("");
  const [createNotes, setCreateNotes] = useState("");
  const [createIsActive, setCreateIsActive] = useState(true);
  const [formError, setFormError] = useState("");
  const [editingProject, setEditingProject] = useState<ProjectListItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editCode, setEditCode] = useState("");
  const [editClientId, setEditClientId] = useState("");
  const [editSiteId, setEditSiteId] = useState("");
  const [editProjectTypeId, setEditProjectTypeId] = useState("");
  const [editPrimaryManagerId, setEditPrimaryManagerId] = useState("");
  const [editSecondaryManagerId, setEditSecondaryManagerId] = useState("");
  const [editStartDate, setEditStartDate] = useState("");
  const [editEndDate, setEditEndDate] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editIsActive, setEditIsActive] = useState(true);
  const [editError, setEditError] = useState("");
  const [editMessage, setEditMessage] = useState("");
  const queryClient = useQueryClient();

  const projectsQuery = useQuery({
    queryKey: ["projects", search, isActive, sortBy, sortOrder, page],
    queryFn: () =>
      getProjects({
        search: search || undefined,
        is_active: isActive === "" ? undefined : isActive === "true",
        sort_by: sortBy,
        sort_order: sortOrder,
        offset: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
  });

  const clientsQuery = useQuery({
    queryKey: ["clients-project-form"],
    queryFn: () => getClients({ limit: 200, sort_by: "name", sort_order: "asc" }),
  });

  const sitesQuery = useQuery({
    queryKey: ["sites-project-form"],
    queryFn: () => getSites({ limit: 200, sort_by: "name", sort_order: "asc" }),
  });

  const projectTypesQuery = useQuery({
    queryKey: ["project-types-project-form"],
    queryFn: () => getProjectTypes({ limit: 200, sort_by: "name", sort_order: "asc" }),
  });

  const workersQuery = useQuery({
    queryKey: ["workers-project-form"],
    queryFn: () => getWorkers({ limit: 200, sort_by: "name", sort_order: "asc", is_active: true }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createProject({
        name: createName,
        code: createCode || null,
        client_id: createClientId,
        site_id: createSiteId || null,
        project_type_id: createProjectTypeId || null,
        primary_manager_id: createPrimaryManagerId || null,
        secondary_manager_id: createSecondaryManagerId || null,
        start_date: createStartDate || null,
        end_date: createEndDate || null,
        notes: createNotes || null,
        is_active: createIsActive,
      }),
    onSuccess: async () => {
      setFormError("");
      setCreateName("");
      setCreateCode("");
      setCreateStartDate("");
      setCreateEndDate("");
      setCreateNotes("");
      setPage(0);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error: unknown) => {
      setFormError(error instanceof ApiError ? error.message : "案件作成に失敗しました");
    },
  });

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editingProject) {
        throw new Error("対象案件を選択してください");
      }
      return updateProject(editingProject.id, {
        name: editName,
        code: editCode || null,
        client_id: editClientId,
        site_id: editSiteId || null,
        project_type_id: editProjectTypeId || null,
        primary_manager_id: editPrimaryManagerId || null,
        secondary_manager_id: editSecondaryManagerId || null,
        start_date: editStartDate || null,
        end_date: editEndDate || null,
        notes: editNotes || null,
        is_active: editIsActive,
      });
    },
    onSuccess: async (project) => {
      setEditError("");
      setEditMessage("案件を更新しました");
      setEditingProject(project);
      setEditName(project.name);
      setEditCode(project.code || "");
      setEditClientId(project.client_id || "");
      setEditSiteId(project.site_id || "");
      setEditProjectTypeId(project.project_type_id || "");
      setEditPrimaryManagerId(project.primary_manager_id || "");
      setEditSecondaryManagerId(project.secondary_manager_id || "");
      setEditStartDate(project.start_date || "");
      setEditEndDate(project.end_date || "");
      setEditNotes(project.notes || "");
      setEditIsActive(project.is_active);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error: unknown) => {
      setEditMessage("");
      setEditError(error instanceof ApiError ? error.message : "案件更新に失敗しました");
    },
  });

  const openProjectEditor = (project: ProjectListItem) => {
    setEditingProject(project);
    setEditName(project.name);
    setEditCode(project.code || "");
    setEditClientId(project.client_id || "");
    setEditSiteId(project.site_id || "");
    setEditProjectTypeId(project.project_type_id || "");
    setEditPrimaryManagerId(project.primary_manager_id || "");
    setEditSecondaryManagerId(project.secondary_manager_id || "");
    setEditStartDate(project.start_date || "");
    setEditEndDate(project.end_date || "");
    setEditNotes(project.notes || "");
    setEditIsActive(project.is_active);
    setEditError("");
    setEditMessage("");
  };

  const closeProjectEditor = () => {
    setEditingProject(null);
    setEditError("");
    setEditMessage("");
  };

  if (projectsQuery.isLoading) {
    return <LoadingOverlay label="案件一覧を読み込み中..." />;
  }

  if (projectsQuery.error instanceof ApiError && projectsQuery.error.status === 403) {
    return <Navigate to="/403" replace />;
  }

  if (projectsQuery.isError || !projectsQuery.data) {
    return <ErrorState title="案件一覧の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
  }

  return (
    <div className="page-stack">
      <PageHeader title="案件一覧" description="案件の作成と編集、取引先、現場、期間、稼働状態を管理します。" />

      <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
        <strong>案件を作成</strong>
        <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
          <label>
            案件名
            <input value={createName} onChange={(event) => setCreateName(event.target.value)} placeholder="案件名" />
          </label>
          <label>
            コード
            <input value={createCode} onChange={(event) => setCreateCode(event.target.value)} placeholder="任意" />
          </label>
          <label>
            取引先
            <select value={createClientId} onChange={(event) => setCreateClientId(event.target.value)}>
              <option value="">選択してください</option>
              {(clientsQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            現場
            <select value={createSiteId} onChange={(event) => setCreateSiteId(event.target.value)}>
              <option value="">未設定</option>
              {(sitesQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            案件種別
            <select value={createProjectTypeId} onChange={(event) => setCreateProjectTypeId(event.target.value)}>
              <option value="">未設定</option>
              {(projectTypesQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            主担当
            <select value={createPrimaryManagerId} onChange={(event) => setCreatePrimaryManagerId(event.target.value)}>
              <option value="">未設定</option>
              {(workersQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            副担当
            <select value={createSecondaryManagerId} onChange={(event) => setCreateSecondaryManagerId(event.target.value)}>
              <option value="">未設定</option>
              {(workersQuery.data?.items ?? []).map((row) => (
                <option key={row.id} value={row.id}>{row.name}</option>
              ))}
            </select>
          </label>
          <label>
            開始日
            <input type="date" value={createStartDate} onChange={(event) => setCreateStartDate(event.target.value)} />
          </label>
          <label>
            終了日
            <input type="date" value={createEndDate} onChange={(event) => setCreateEndDate(event.target.value)} />
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", paddingTop: "1.7rem" }}>
            <input type="checkbox" checked={createIsActive} onChange={(event) => setCreateIsActive(event.target.checked)} />
            有効
          </label>
        </div>
        <label>
          メモ
          <textarea value={createNotes} onChange={(event) => setCreateNotes(event.target.value)} rows={3} style={{ width: "100%", resize: "vertical" }} />
        </label>
        {formError ? <p className="form-error">{formError}</p> : null}
        <div>
          <button
            type="button"
            className="primary-button"
            onClick={() => createMutation.mutate()}
            disabled={!createName || !createClientId || createMutation.isPending}
          >
            {createMutation.isPending ? "作成中..." : "案件を作成"}
          </button>
        </div>
      </section>

      {editingProject ? (
        <section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem", flexWrap: "wrap" }}>
            <div style={{ display: "grid", gap: "0.2rem" }}>
              <strong>案件を編集</strong>
              <span style={{ color: "var(--color-text-subtle, #667085)", fontSize: "0.9rem" }}>
                {editingProject.name} / {editingProject.client_name}
              </span>
            </div>
            <button type="button" onClick={closeProjectEditor} style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}>
              閉じる
            </button>
          </div>
          <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            <label>
              案件名
              <input value={editName} onChange={(event) => setEditName(event.target.value)} />
            </label>
            <label>
              コード
              <input value={editCode} onChange={(event) => setEditCode(event.target.value)} />
            </label>
            <label>
              取引先
              <select value={editClientId} onChange={(event) => setEditClientId(event.target.value)}>
                <option value="">選択してください</option>
                {(clientsQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              現場
              <select value={editSiteId} onChange={(event) => setEditSiteId(event.target.value)}>
                <option value="">未設定</option>
                {(sitesQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              案件種別
              <select value={editProjectTypeId} onChange={(event) => setEditProjectTypeId(event.target.value)}>
                <option value="">未設定</option>
                {(projectTypesQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              主担当
              <select value={editPrimaryManagerId} onChange={(event) => setEditPrimaryManagerId(event.target.value)}>
                <option value="">未設定</option>
                {(workersQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              副担当
              <select value={editSecondaryManagerId} onChange={(event) => setEditSecondaryManagerId(event.target.value)}>
                <option value="">未設定</option>
                {(workersQuery.data?.items ?? []).map((row) => (
                  <option key={row.id} value={row.id}>{row.name}</option>
                ))}
              </select>
            </label>
            <label>
              開始日
              <input type="date" value={editStartDate} onChange={(event) => setEditStartDate(event.target.value)} />
            </label>
            <label>
              終了日
              <input type="date" value={editEndDate} onChange={(event) => setEditEndDate(event.target.value)} />
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", paddingTop: "1.7rem" }}>
              <input type="checkbox" checked={editIsActive} onChange={(event) => setEditIsActive(event.target.checked)} />
              有効
            </label>
          </div>
          <label>
            メモ
            <textarea value={editNotes} onChange={(event) => setEditNotes(event.target.value)} rows={4} style={{ width: "100%", resize: "vertical" }} />
          </label>
          {editError ? <p className="form-error">{editError}</p> : null}
          {editMessage ? <p style={{ margin: 0, color: "var(--color-success, #067647)" }}>{editMessage}</p> : null}
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button
              type="button"
              className="primary-button"
              onClick={() => updateMutation.mutate()}
              disabled={!editName || !editClientId || updateMutation.isPending}
            >
              {updateMutation.isPending ? "更新中..." : "更新する"}
            </button>
            <button type="button" onClick={() => openProjectEditor(editingProject)} disabled={updateMutation.isPending}>
              元に戻す
            </button>
          </div>
        </section>
      ) : null}

      <FilterBar>
        <label>
          検索
          <input value={search} onChange={(event) => { setSearch(event.target.value); setPage(0); }} placeholder="案件名、コード、取引先" />
        </label>
        <label>
          稼働状態
          <select value={isActive} onChange={(event) => { setIsActive(event.target.value); setPage(0); }}>
            <option value="">すべて</option>
            <option value="true">有効</option>
            <option value="false">無効</option>
          </select>
        </label>
        <label>
          ソート
          <select value={sortBy} onChange={(event) => { setSortBy(event.target.value); setPage(0); }}>
            <option value="name">案件名</option>
            <option value="code">コード</option>
            <option value="client_name">取引先名</option>
            <option value="site_name">現場名</option>
            <option value="start_date">開始日</option>
          </select>
        </label>
        <label>
          順序
          <select value={sortOrder} onChange={(event) => { setSortOrder(event.target.value); setPage(0); }}>
            <option value="asc">昇順</option>
            <option value="desc">降順</option>
          </select>
        </label>
      </FilterBar>

      <DataTable
        columns={[
          { key: "code", header: "コード", render: (row) => row.code || "-" },
          { key: "name", header: "案件", render: (row) => row.name },
          { key: "client", header: "取引先", render: (row) => row.client_name },
          { key: "site", header: "現場", render: (row) => row.site_name },
          { key: "type", header: "案件種別", render: (row) => row.project_type_name },
          { key: "start", header: "開始日", render: (row) => formatDate(row.start_date) },
          { key: "end", header: "終了日", render: (row) => formatDate(row.end_date) },
          { key: "notes", header: "メモ", render: (row) => row.notes || "-" },
          { key: "status", header: "状態", render: (row) => <StatusBadge value={row.is_active ? "active" : "inactive"} /> },
          {
            key: "actions",
            header: "操作",
            render: (row) => (
              <button
                type="button"
                onClick={() => openProjectEditor(row)}
                style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
              >
                編集
              </button>
            ),
          },
        ]}
        rows={projectsQuery.data.items}
        getRowKey={(row) => row.id}
        emptyTitle="案件はありません"
        emptyDescription="条件に一致する案件は見つかりませんでした。"
      />

      <PaginationBar
        page={page}
        total={projectsQuery.data.total}
        limit={projectsQuery.data.limit}
        onPrevious={() => setPage((value) => Math.max(0, value - 1))}
        onNext={() => setPage((value) => value + 1)}
      />
    </div>
  );
}