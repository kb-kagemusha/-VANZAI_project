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
import type { ImportBatchListItem } from "../types/api";

const PROJECT_PAGE_SIZE = 100;
const IMPORT_BATCH_PAGE_SIZE = 10;

function buildRejectionMessage(batch: ImportBatchListItem) {
	const headline = batch.errors_preview.length
		? batch.errors_preview
				.slice(0, 5)
				.map((error) => {
					const rowLabel = error.row ? `${error.row}行目` : "行番号不明";
					const fieldLabel = error.field ? ` / ${error.field}` : "";
					const message = error.message || "不明なエラー";
					return `- ${rowLabel}${fieldLabel}: ${message}`;
				})
				.join("\n")
		: "- 詳細エラーは管理画面の取込履歴を確認してください";

	return [
		"CSV取込の差戻し連絡",
		`案件: ${batch.project_name || "-"}`,
		`対象月: ${formatPeriodKey(batch.period_key)}`,
		`取込ファイル: ${batch.file_name}`,
		`取込日時: ${formatDateTime(batch.created_at)}`,
		`結果: 成功 ${batch.success_rows}件 / エラー ${batch.error_rows}件 / スキップ ${batch.skipped_rows}件`,
		"",
		"以下の内容を修正して CSV を再送してください。",
		headline,
	].join("\n");
}

async function copyText(text: string) {
	if (navigator.clipboard?.writeText) {
		await navigator.clipboard.writeText(text);
		return;
	}

	const textarea = document.createElement("textarea");
	textarea.value = text;
	textarea.style.position = "fixed";
	textarea.style.opacity = "0";
	document.body.appendChild(textarea);
	textarea.focus();
	textarea.select();
	document.execCommand("copy");
	textarea.remove();
}

export function CsvImportPage() {
	const queryClient = useQueryClient();
	const [projectId, setProjectId] = useState("");
	const [monthValue, setMonthValue] = useState(currentMonthInput());
	const [importMode, setImportMode] = useState("replace_scope");
	const [scopeType, setScopeType] = useState("project_month");
	const [selectedFile, setSelectedFile] = useState<File | null>(null);
	const [formError, setFormError] = useState<string | null>(null);
	const [historyPage, setHistoryPage] = useState(0);
	const [selectedBatch, setSelectedBatch] = useState<ImportBatchListItem | null>(null);
	const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

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
		setSelectedBatch(null);
		setCopyFeedback(null);
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
									{
										key: "actions",
										header: "差戻し",
										render: (row) =>
											row.error_rows > 0 || row.errors_preview.length ? (
												<button
													onClick={() => {
														setSelectedBatch(row);
														setCopyFeedback(null);
													}}
													style={{ fontSize: "0.8rem", padding: "0.2rem 0.6rem" }}
												>
													文面作成
												</button>
											) : (
												"-"
											),
									},
						]}
						rows={importBatchesQuery.data.items}
						getRowKey={(row) => row.id}
						emptyTitle="取込履歴はありません"
						emptyDescription="この案件・対象月ではまだ CSV 取込が実行されていません。"
					/>

							{selectedBatch ? (
								<section className="card" style={{ padding: "1rem", display: "grid", gap: "0.75rem" }}>
									<div style={{ display: "flex", justifyContent: "space-between", gap: "1rem", flexWrap: "wrap" }}>
										<div>
											<strong>差戻し文面</strong>
											<p style={{ margin: "0.35rem 0 0", color: "var(--color-text-muted, #667085)" }}>
												{selectedBatch.file_name} のエラー概要を連絡用テキストに整形しています。
											</p>
										</div>
										<button
											onClick={() => {
												const message = buildRejectionMessage(selectedBatch);
												void copyText(message)
													.then(() => setCopyFeedback("差戻し文面をコピーしました"))
													.catch(() => setCopyFeedback("コピーに失敗しました。文面を手動で選択してください"));
											}}
										>
											文面をコピー
										</button>
									</div>

									<textarea
										readOnly
										value={buildRejectionMessage(selectedBatch)}
										rows={10}
										style={{ width: "100%", resize: "vertical", fontFamily: "inherit" }}
									/>

									{copyFeedback ? <p style={{ margin: 0, color: "var(--color-text-muted, #667085)" }}>{copyFeedback}</p> : null}
								</section>
							) : null}

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
