"""POST /api/csv/upload のAPIテスト"""
from datetime import datetime, time, timezone

from src.api.jwt_auth import create_access_token, create_user_with_hashed_password
from src.models.base import generate_ulid
from src.models.enums import UserRole
from src.models.transaction import Actual, ImportBatch, Project


def _auth_header(username: str) -> dict[str, str]:
	token = create_access_token({"sub": username})
	return {"Authorization": f"Bearer {token}"}


def test_csv_upload_requires_authentication(api_client, project):
	csv_content = "worker_id,role_id,work_date,start_time,end_time,break_minutes\nworker-1,role-1,2026-01-15,09:00,18:00,60\n"

	response = api_client.post(
		"/api/csv/upload",
		data={
			"project_id": project.id,
			"period_key": "202601",
			"import_mode": "replace_scope",
			"scope_type": "project_month",
		},
		files={"file": ("actuals.csv", csv_content, "text/csv")},
	)

	assert response.status_code == 401


def test_csv_upload_allows_ops_and_creates_actual(api_client, db_session, project, worker, role, assignment):
	user = create_user_with_hashed_password(
		db=db_session,
		username="ops_csv_upload",
		email="ops_csv_upload@example.com",
		password="secret123",
		role=UserRole.OPS.value,
	)
	db_session.commit()

	csv_content = (
		"worker_id,role_id,work_date,start_time,end_time,break_minutes\n"
		f"{worker.id},{role.id},2026-01-15,09:00,18:00,60\n"
	)

	response = api_client.post(
		"/api/csv/upload",
		data={
			"project_id": project.id,
			"period_key": "202601",
			"import_mode": "replace_scope",
			"scope_type": "project_month",
		},
		files={"file": ("actuals.csv", csv_content, "text/csv")},
		headers=_auth_header(user.username),
	)

	assert response.status_code == 200
	payload = response.json()
	assert payload["status"] == "completed"
	assert payload["batch_id"]
	assert payload["total_rows"] == 1
	assert payload["success_rows"] == 1
	assert payload["error_rows"] == 0
	assert payload["superseded_rows"] == 0

	actuals = db_session.query(Actual).all()
	assert len(actuals) == 1
	assert actuals[0].project_id == project.id
	assert actuals[0].worker_id == worker.id


def test_csv_upload_forbids_accounting(api_client, db_session, project, worker, role, assignment):
	user = create_user_with_hashed_password(
		db=db_session,
		username="accounting_csv_upload",
		email="accounting_csv_upload@example.com",
		password="secret123",
		role=UserRole.ACCOUNTING.value,
	)
	db_session.commit()

	csv_content = (
		"worker_id,role_id,work_date,start_time,end_time,break_minutes\n"
		f"{worker.id},{role.id},2026-01-15,09:00,18:00,60\n"
	)

	response = api_client.post(
		"/api/csv/upload",
		data={
			"project_id": project.id,
			"period_key": "202601",
			"import_mode": "replace_scope",
			"scope_type": "project_month",
		},
		files={"file": ("actuals.csv", csv_content, "text/csv")},
		headers=_auth_header(user.username),
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "CSV import permission denied"


def test_csv_upload_scopes_site_manager_projects(api_client, db_session, project, worker, role, assignment, client):
	project.primary_manager_id = worker.id
	db_session.add(project)
	db_session.flush()

	unmanaged_project = Project(
		id=generate_ulid(),
		name="Unmanaged Project",
		code="UP001",
		client_id=client.id,
		rounding_unit_minutes=15,
		rounding_method="ceil",
		break_deduction_rule="auto",
		time_calc_mode="system_first",
		night_window_start=time(22, 0),
		night_window_end=time(5, 0),
		night_calc_mode="store_minutes",
		is_active=True,
	)
	db_session.add(unmanaged_project)

	site_manager = create_user_with_hashed_password(
		db=db_session,
		username="site_manager_csv_upload",
		email="site_manager_csv_upload@example.com",
		password="secret123",
		role=UserRole.SITE_MANAGER.value,
	)
	site_manager.worker_id = worker.id
	db_session.add(site_manager)
	db_session.commit()

	csv_content = (
		"worker_id,role_id,work_date,start_time,end_time,break_minutes\n"
		f"{worker.id},{role.id},2026-01-15,09:00,18:00,60\n"
	)

	allowed_response = api_client.post(
		"/api/csv/upload",
		data={
			"project_id": project.id,
			"period_key": "202601",
			"import_mode": "replace_scope",
			"scope_type": "project_month",
		},
		files={"file": ("actuals.csv", csv_content, "text/csv")},
		headers=_auth_header(site_manager.username),
	)
	denied_response = api_client.post(
		"/api/csv/upload",
		data={
			"project_id": unmanaged_project.id,
			"period_key": "202601",
			"import_mode": "replace_scope",
			"scope_type": "project_month",
		},
		files={"file": ("actuals.csv", csv_content, "text/csv")},
		headers=_auth_header(site_manager.username),
	)

	assert allowed_response.status_code == 200
	assert denied_response.status_code == 403
	assert denied_response.json()["detail"] == "Project access denied"


def test_csv_upload_rejects_non_csv_extension(api_client, db_session, project, worker, role, assignment):
	user = create_user_with_hashed_password(
		db=db_session,
		username="ops_csv_extension",
		email="ops_csv_extension@example.com",
		password="secret123",
		role=UserRole.OPS.value,
	)
	db_session.commit()

	response = api_client.post(
		"/api/csv/upload",
		data={
			"project_id": project.id,
			"period_key": "202601",
			"import_mode": "replace_scope",
			"scope_type": "project_month",
		},
		files={"file": ("actuals.txt", "x", "text/plain")},
		headers=_auth_header(user.username),
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "CSVファイルのみアップロードできます"


def test_csv_upload_rejects_invalid_period_key(api_client, db_session, project, worker, role, assignment):
	user = create_user_with_hashed_password(
		db=db_session,
		username="ops_csv_period",
		email="ops_csv_period@example.com",
		password="secret123",
		role=UserRole.OPS.value,
	)
	db_session.commit()

	csv_content = (
		"worker_id,role_id,work_date,start_time,end_time,break_minutes\n"
		f"{worker.id},{role.id},2026-01-15,09:00,18:00,60\n"
	)

	response = api_client.post(
		"/api/csv/upload",
		data={
			"project_id": project.id,
			"period_key": "2026-01",
			"import_mode": "replace_scope",
			"scope_type": "project_month",
		},
		files={"file": ("actuals.csv", csv_content, "text/csv")},
		headers=_auth_header(user.username),
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "period_key は YYYYMM 形式で指定してください"


def test_csv_upload_rejects_oversized_file(api_client, db_session, project):
	user = create_user_with_hashed_password(
		db=db_session,
		username="ops_csv_size",
		email="ops_csv_size@example.com",
		password="secret123",
		role=UserRole.OPS.value,
	)
	db_session.commit()

	response = api_client.post(
		"/api/csv/upload",
		data={
			"project_id": project.id,
			"period_key": "202601",
			"import_mode": "replace_scope",
			"scope_type": "project_month",
		},
		files={"file": ("actuals.csv", b"a" * (2 * 1024 * 1024 + 1), "text/csv")},
		headers=_auth_header(user.username),
	)

	assert response.status_code == 400
	assert response.json()["detail"] == "CSVファイルサイズが上限を超えています"


def test_import_batches_list_scopes_site_manager_projects(api_client, db_session, project, worker, client):
	project.primary_manager_id = worker.id
	db_session.add(project)
	db_session.flush()

	other_project = Project(
		id=generate_ulid(),
		name="Other Project",
		code="OP002",
		client_id=client.id,
		rounding_unit_minutes=15,
		rounding_method="ceil",
		break_deduction_rule="auto",
		time_calc_mode="system_first",
		night_window_start=time(22, 0),
		night_window_end=time(5, 0),
		night_calc_mode="store_minutes",
		is_active=True,
	)
	db_session.add(other_project)
	db_session.flush()

	db_session.add_all([
		ImportBatch(
			id=generate_ulid(),
			submitted_by="ops1",
			submit_channel="system_upload",
			file_name="managed.csv",
			file_hash="hash-managed-1",
			project_id=project.id,
			period_key="202601",
			mode="replace_scope",
			scope_type="project_month",
			status="completed",
			count_success=1,
			count_error=0,
			count_skip=0,
			count_superseded=0,
			errors_json=[],
			has_row_count_warning=False,
			has_total_time_warning=False,
			created_at=datetime.now(timezone.utc),
			updated_at=datetime.now(timezone.utc),
		),
		ImportBatch(
			id=generate_ulid(),
			submitted_by="ops2",
			submit_channel="system_upload",
			file_name="other.csv",
			file_hash="hash-other-1",
			project_id=other_project.id,
			period_key="202601",
			mode="replace_scope",
			scope_type="project_month",
			status="completed",
			count_success=1,
			count_error=0,
			count_skip=0,
			count_superseded=0,
			errors_json=[],
			has_row_count_warning=False,
			has_total_time_warning=False,
			created_at=datetime.now(timezone.utc),
			updated_at=datetime.now(timezone.utc),
		),
	])

	site_manager = create_user_with_hashed_password(
		db=db_session,
		username="site_manager_batch_list",
		email="site_manager_batch_list@example.com",
		password="secret123",
		role=UserRole.SITE_MANAGER.value,
	)
	site_manager.worker_id = worker.id
	db_session.add(site_manager)
	db_session.commit()

	response = api_client.get(
		"/api/import-batches",
		params={"period_key": "202601"},
		headers=_auth_header(site_manager.username),
	)

	assert response.status_code == 200
	payload = response.json()
	assert payload["total"] == 1
	assert payload["items"][0]["file_name"] == "managed.csv"


def test_import_batches_list_rejects_unscoped_project_for_site_manager(api_client, db_session, project, worker, client):
	other_project = Project(
		id=generate_ulid(),
		name="Other Project",
		code="OP003",
		client_id=client.id,
		rounding_unit_minutes=15,
		rounding_method="ceil",
		break_deduction_rule="auto",
		time_calc_mode="system_first",
		night_window_start=time(22, 0),
		night_window_end=time(5, 0),
		night_calc_mode="store_minutes",
		is_active=True,
	)
	db_session.add(other_project)

	site_manager = create_user_with_hashed_password(
		db=db_session,
		username="site_manager_batch_denied",
		email="site_manager_batch_denied@example.com",
		password="secret123",
		role=UserRole.SITE_MANAGER.value,
	)
	site_manager.worker_id = worker.id
	db_session.add(site_manager)
	db_session.commit()

	response = api_client.get(
		"/api/import-batches",
		params={"project_id": other_project.id},
		headers=_auth_header(site_manager.username),
	)

	assert response.status_code == 403
	assert response.json()["detail"] == "Project access denied"
