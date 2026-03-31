import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { DataTable } from "../components/DataTable";
import { ErrorState } from "../components/ErrorState";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PageHeader } from "../components/PageHeader";
import { PaginationBar } from "../components/PaginationBar";
import { StatusBadge } from "../components/StatusBadge";
import { ApiError, getImportBatches, getProjects, uploadCsvFile } from "../lib/api/client";
import { currentMonthInput, formatDateTime, formatImportMode, formatImportScopeType, formatPeriodKey, toPeriodKey } from "../lib/formatters";

const PROJECT_PAGE_SIZE = 100;
const IMPORT_BATCH_PAGE_SIZE = 10;

export function CsvImportPage() {
	const queryClient = useQueryClient();
	const [projectId, setProjectId] = useState("");
	const [monthValue, setMonthValue] = useState(currentMonthInput());
	const [importMode, setImportMode] = useState("replace_scope");
	const [scopeType, setScopeType] = useState("project_month");
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const [formError, setFormError] = useState<string | null>(null);
	const [historyPage, setHistoryPage] = useState(0);

	const periodKey = toPeriodKey(monthValue);

	const projectsQuery = useQuery({
		queryKey: ["csv-import-projects"],
		queryFn: () =>
			getProjects({
				is_active: true,
				sort_by: "name",
				sort_order: "asc",
				offset: 0,
				limit: PROJECT_PAGE_SIZE,
			}),
	});

	useEffect(() => {
		if (!projectId && projectsQuery.data?.items.length) {
			setProjectId(projectsQuery.data.items[0].id);
		}
	}, [projectId, projectsQuery.data]);

	useEffect(() => {
		setHistoryPage(0);
	}, [projectId, periodKey]);

	const importBatchesQuery = useQuery({
		queryKey: ["import-batches", projectId, periodKey, historyPage],
		enabled: Boolean(projectId),
		queryFn: () =>
			getImportBatches({
				project_id: projectId,
				period_key: periodKey,
				offset: historyPage * IMPORT_BATCH_PAGE_SIZE,
				limit: IMPORT_BATCH_PAGE_SIZE,
			}),
	});

	const uploadMutation = useMutation({
		mutationFn: async () => {
			if (!selectedFile) {
				throw new Error("CSVファイルを選択してください");
			}

			if (!projectId) {
				throw new Error("対象案件を選択してください");
			}

			return uploadCsvFile({
				file: selectedFile,
				projectId,
				periodKey,
				importMode,
				scopeType,
			});
		},
		onMutate: () => {
			setFormError(null);
		},
		onError: (error) => {
			if (error instanceof ApiError) {
				setFormError(error.message);
				return;
			}

			setFormError(error instanceof Error ? error.message : "CSV取込に失敗しました");
		},
		onSuccess: async () => {
			setHistoryPage(0);
			await queryClient.invalidateQueries({ queryKey: ["import-batches"] });
		},
	});

	if (projectsQuery.isLoading) {
		return <LoadingOverlay label="CSV取込画面を準備中..." />;
	}

	if (projectsQuery.error instanceof ApiError && projectsQuery.error.status === 403) {
		return <Navigate to="/403" replace />;
	}

	if (projectsQuery.isError || !projectsQuery.data) {
		return <ErrorState title="案件候補の取得に失敗しました" description="認証または API 疎通を確認してください。" />;
	}

	return (
		<div className="page-stack">
			<PageHeader
				eyebrow="月次運用"
				title="CSV取込"
				description="実績CSVをアップロードし、案件×月単位の洗い替えまたは追加取込を実行します。"
			/>

			<form
				className="upload-card"
				onSubmit={(event) => {
					event.preventDefault();
					void uploadMutation.mutateAsync();
				}}
			>
				<div className="upload-form-grid">
					<label>
						対象案件
						<select value={projectId} onChange={(event) => setProjectId(event.target.value)}>
							{projectsQuery.data.items.map((project) => (
								<option key={project.id} value={project.id}>
									{project.name}
									{project.code ? ` (${project.code})` : ""}
								</option>
							))}
						</select>
					</label>

					<label>
						対象月
						<input type="month" value={monthValue} onChange={(event) => setMonthValue(event.target.value)} />
					</label>

					<label>
						取込モード
						<select value={importMode} onChange={(event) => setImportMode(event.target.value)}>
							<option value="replace_scope">洗い替え</option>
							<option value="append">追加</option>
						</select>
					</label>

					<label>
						洗い替え範囲
						<select
							value={scopeType}
							onChange={(event) => setScopeType(event.target.value)}
							disabled={importMode !== "replace_scope"}
						>
							<option value="project_month">案件×月</option>
							<option value="project_day">案件×日</option>
							<option value="project_day_worker">案件×日×稼働者</option>
						</select>
					</label>

					<label className="upload-file-field">
						CSVファイル
						<input
							type="file"
							accept=".csv,text/csv"
							onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
						/>
					</label>
				</div>

				<p className="upload-help">
					推奨は「洗い替え / 案件×月」です。修正CSVの再投入時も二重化せず、既存実績は superseded に退避されます。
				</p>

				{selectedFile ? <p className="upload-selected-file">選択中: {selectedFile.name}</p> : null}
				{formError ? <p className="form-error">{formError}</p> : null}

				<div className="upload-actions">
					<button type="submit" className="primary-button" disabled={uploadMutation.isPending || !selectedFile || !projectId}>
						{uploadMutation.isPending ? "取込中..." : "CSVを取り込む"}
					</button>
				</div>
			</form>

			{uploadMutation.data ? (
				<section className="upload-result-card">
					<div className="upload-result-header">
						<div>
							<p className="eyebrow">取込結果</p>
							<h3>バッチ {uploadMutation.data.batch_id}</h3>
						</div>
						<StatusBadge value={uploadMutation.data.status} />
					</div>

					<div className="upload-result-grid">
						<div>
							<span className="upload-result-label">対象行</span>
							<strong>{uploadMutation.data.total_rows}</strong>
						</div>
						<div>
							<span className="upload-result-label">成功</span>
							<strong>{uploadMutation.data.success_rows}</strong>
						</div>
						<div>
							<span className="upload-result-label">エラー</span>
							<strong>{uploadMutation.data.error_rows}</strong>
						</div>
						<div>
							<span className="upload-result-label">洗い替え件数</span>
							<strong>{uploadMutation.data.superseded_rows}</strong>
						</div>
					</div>

					{uploadMutation.data.warnings.length ? (
						<div className="upload-message-block warning">
							<h4>警告</h4>
							<ul>
								{uploadMutation.data.warnings.map((warning) => (
									<li key={warning}>{warning}</li>
								))}
							</ul>
						</div>
					) : null}

					{uploadMutation.data.errors?.length ? (
						<div className="upload-message-block error">
							<h4>先頭エラー</h4>
							<ul>
								{uploadMutation.data.errors.map((error) => (
									<li key={`${error.row}-${error.field || "none"}-${error.message}`}>
										{error.row}行目{error.field ? ` / ${error.field}` : ""}: {error.message}
									</li>
								))}
							</ul>
						</div>
					) : null}
				</section>
			) : null}

			{importBatchesQuery.error instanceof ApiError && importBatchesQuery.error.status === 403 ? (
				<Navigate to="/403" replace />
			) : importBatchesQuery.isError ? (
				<ErrorState title="取込履歴の取得に失敗しました" description="認証または API 疎通を確認してください。" />
			) : importBatchesQuery.isLoading || !importBatchesQuery.data ? (
				<LoadingOverlay label="取込履歴を読み込み中..." />
			) : (
				<section className="page-stack">
					<PageHeader
						eyebrow="月次運用"
						title="取込履歴"
						description="選択中の案件と対象月に対する CSV 取込結果を確認します。"
					/>

					<DataTable
						columns={[
							{ key: "createdAt", header: "実行日時", render: (row) => formatDateTime(row.created_at) },
							{ key: "fileName", header: "ファイル", render: (row) => row.file_name },
							{ key: "mode", header: "モード", render: (row) => formatImportMode(row.mode) },
							{ key: "scope", header: "範囲", render: (row) => formatImportScopeType(row.scope_type) },
							{ key: "period", header: "対象月", render: (row) => formatPeriodKey(row.period_key) },
							{ key: "actor", header: "実行者", render: (row) => row.submitted_by || "-" },
							{ key: "status", header: "状態", render: (row) => <StatusBadge value={row.status} /> },
							{ key: "success", header: "成功", render: (row) => row.success_rows },
							{ key: "error", header: "エラー", render: (row) => row.error_rows },
							{
								key: "warnings",
								header: "警告",
								render: (row) => (row.has_warnings ? "あり" : "-"),
							},
							{
								key: "preview",
								header: "エラー概要",
								render: (row) =>
									row.errors_preview.length
										? row.errors_preview
												.map((error) => `${error.row || "-"}行目: ${error.message || "不明なエラー"}`)
												.slice(0, 2)
												.join(" / ")
										: "-",
							},
						]}
						rows={importBatchesQuery.data.items}
						getRowKey={(row) => row.id}
						emptyTitle="取込履歴はありません"
						emptyDescription="この案件・対象月ではまだ CSV 取込が実行されていません。"
					/>

					<PaginationBar
						page={historyPage}
						total={importBatchesQuery.data.total}
						limit={importBatchesQuery.data.limit}
						onPrevious={() => setHistoryPage((value) => Math.max(0, value - 1))}
						onNext={() => setHistoryPage((value) => value + 1)}
					/>
				</section>
			)}
		</div>
	);
}
