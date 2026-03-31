"""
FastAPI メインアプリケーション

案件・シフト・実績・請求・支払 一元管理システムのREST API
"""
from contextlib import asynccontextmanager
from pathlib import PurePath
import re

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List
import base64
from datetime import date, timedelta

from src.api.deps import get_db
from src.api.jwt_auth import (
    authenticate_user, 
    create_access_token, 
    create_refresh_token,
    get_current_user,
    get_current_active_user
)
from src.api.schemas import (
    CSVImportRequest, CSVImportResponse,
    ImportBatchListItem, ImportBatchListQuery, ImportBatchListResponse,
    DashboardResponse, UnprocessedItem, VarianceAlert, ClosingStatusItem,
    ActualListQuery, ActualListItem, ActualListResponse,
    AssignmentListQuery, AssignmentListItem, AssignmentListResponse,
    ProjectListQuery, ProjectListItem, ProjectListResponse,
    ShiftSlotListQuery, ShiftSlotListItem, ShiftSlotListResponse,
    ExpenseListQuery, ExpenseListItem, ExpenseListResponse,
    PriceRuleListQuery, PriceRuleListItem, PriceRuleListResponse,
    PriceSalesListQuery, PriceSalesListItem, PriceSalesListResponse,
    PriceOutsourceListQuery, PriceOutsourceListItem, PriceOutsourceListResponse,
    InvoiceListQuery, InvoiceListItem, InvoiceListResponse,
    InvoiceGenerateRequest, InvoiceResponse, InvoiceLineResponse,
    PayoutListQuery, PayoutListItem, PayoutListResponse,
    PayoutGenerateRequest, PayoutResponse, PayoutLineResponse,
    MonthlyBillingGenerateRequest, MonthlyBillingGenerateResponse,
    SoftCloseRequest, HardCloseRequest, SoftCloseReleaseRequest, HardCloseReleaseRequest, ClosingResponse,
    AuditLogSearchRequest, AuditLogResponse, AuditLogListResponse,
    ErrorResponse
)
from src.models.master import User

from src.services.csv_import import CsvImportService
from src.services.dashboard import get_dashboard_summary, get_project_closings_for_period
from src.services import invoice_service
from src.services import payout_service
from src.services.billing_batch import generate_monthly_billing
from src.services import closing
from src.services.audit import AuditService, AuditLogSearchFilter
from src.services import aggregation
from src.services.scheduler import initialize_default_jobs
from src.services.auth import AuthorizationError, check_permission, can_access_project, has_permission
from src.exceptions import VANZAIException
from src.models.enums import ImportMode, ImportScopeType, Permission, UserRole, ClosingStatus


CSV_UPLOAD_MAX_BYTES = 2 * 1024 * 1024
PERIOD_KEY_PATTERN = re.compile(r"^\d{6}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_default_jobs()
    yield


# FastAPIアプリケーション初期化
app = FastAPI(
    title="VANZAI API",
    description="案件・シフト・実績・請求・支払 一元管理システム",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501"],  # Streamlit用
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================
# 例外ハンドラー
# ===========================

@app.exception_handler(VANZAIException)
async def vanzai_exception_handler(request, exc: VANZAIException):
    """カスタム例外ハンドラー"""
    return JSONResponse(
        status_code=400,
        content={
            "error_code": exc.code,
            "message": exc.message,
            "detail": exc.details,
        },
    )


def _default_period_key(period_key: str | None) -> str:
    if period_key:
        return period_key
    today = date.today()
    return f"{today.year}{today.month:02d}"


def _status_to_str(value) -> str:
    if value is None:
        return ""
    return getattr(value, "value", str(value))


def _sanitize_upload_file_name(file_name: str | None) -> str:
    candidate = PurePath((file_name or "").replace("\\", "/")).name.strip()

    if not candidate:
        raise HTTPException(status_code=400, detail="CSVファイル名は必須です")
    if len(candidate) > 255:
        raise HTTPException(status_code=400, detail="CSVファイル名が長すぎます")
    if not candidate.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSVファイルのみアップロードできます")

    return candidate


def _validate_period_key(period_key: str) -> str:
    if not PERIOD_KEY_PATTERN.fullmatch(period_key):
        raise HTTPException(status_code=400, detail="period_key は YYYYMM 形式で指定してください")
    return period_key


def _validate_csv_file_bytes(file_bytes: bytes) -> None:
    if not file_bytes:
        raise HTTPException(status_code=400, detail="CSVファイルが空です")
    if len(file_bytes) > CSV_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="CSVファイルサイズが上限を超えています")


def _resolve_import_mode(value: str | None) -> ImportMode:
    if not value:
        return ImportMode.REPLACE_SCOPE

    normalized = value.strip().lower()
    alias_map = {
        "append": ImportMode.APPEND,
        "replace_scope": ImportMode.REPLACE_SCOPE,
        "upsert_by_external_key": ImportMode.UPSERT_BY_EXTERNAL_KEY,
    }

    if normalized not in alias_map:
        raise HTTPException(status_code=400, detail=f"Unsupported import_mode: {value}")

    return alias_map[normalized]


def _resolve_import_scope_type(value: str | None) -> ImportScopeType:
    if not value:
        return ImportScopeType.PROJECT_MONTH

    normalized = value.strip().lower()
    alias_map = {
        "project_month": ImportScopeType.PROJECT_MONTH,
        "project_day": ImportScopeType.PROJECT_DAY,
        "project_day_worker": ImportScopeType.PROJECT_DAY_WORKER,
    }

    if normalized not in alias_map:
        raise HTTPException(status_code=400, detail=f"Unsupported scope_type: {value}")

    return alias_map[normalized]


def _ensure_csv_import_permission(db: Session, user: User, project_id: str) -> None:
    if has_permission(user, Permission.CSV_IMPORT):
        return

    if has_permission(user, Permission.CSV_SUBMIT):
        if not can_access_project(db, user, project_id):
            raise HTTPException(status_code=403, detail="Project access denied")
        return

    raise HTTPException(status_code=403, detail="CSV import permission denied")


def _build_csv_import_response(result) -> CSVImportResponse:
    return CSVImportResponse(
        batch_id=result.batch_id,
        status=result.status.value,
        total_rows=result.count_success + result.count_error + result.count_skip,
        success_rows=result.count_success,
        error_rows=result.count_error,
        skipped_rows=result.count_skip,
        superseded_rows=result.count_superseded,
        warnings=result.warnings,
        errors=[
            {"row": error.row_number, "field": error.field, "message": error.message}
            for error in result.errors[:10]
        ] or None,
    )


def _ensure_import_batch_read_permission(db: Session, user: User, project_id: str | None) -> None:
    if has_permission(user, Permission.CSV_IMPORT):
        return

    if has_permission(user, Permission.CSV_SUBMIT):
        if project_id and not can_access_project(db, user, project_id):
            raise HTTPException(status_code=403, detail="Project access denied")
        return

    raise HTTPException(status_code=403, detail="Import batch access denied")


def _summarize_audit_log_details(details: dict | None, reason: str | None) -> str | None:
    if reason:
        return reason
    if not details:
        return None

    preferred_keys = [
        "reason",
        "approver_id",
        "reclose_deadline",
        "release_count",
        "period_key",
        "project_id",
        "file_name",
        "count",
    ]
    summary_parts = []
    for key in preferred_keys:
        if key in details and details[key] is not None:
            summary_parts.append(f"{key}={details[key]}")
        if len(summary_parts) >= 3:
            break

    if not summary_parts:
        summary_parts = [f"{key}={value}" for key, value in list(details.items())[:3]]
    return ", ".join(summary_parts) if summary_parts else None


def _extract_audit_project_id(
    extra_metadata: dict | None,
    before_value: dict | None,
    after_value: dict | None,
    target_type: str | None,
    target_id: str | None,
) -> str | None:
    for payload in (extra_metadata, after_value, before_value):
        if not isinstance(payload, dict):
            continue
        project_id = payload.get("project_id")
        if project_id is None:
            continue
        candidate = str(project_id).strip()
        if candidate:
            return candidate

    if target_type in {"project", "projects"} and target_id:
        return target_id

    return None


# ===========================
# 認証エンドポイント
# ===========================

@app.post("/api/auth/token", tags=["Authentication"])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    ログインしてアクセストークンを取得
    
    Args:
        form_data: OAuth2 form（username, password）
        db: データベースセッション
    
    Returns:
        access_token, refresh_token, token_type
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.username}
    )
    refresh_token = create_refresh_token(
        data={"sub": user.username}
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.get("/api/auth/me", tags=["Authentication"])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """
    現在のユーザー情報取得
    
    Args:
        current_user: JWT検証済みユーザー
    
    Returns:
        ユーザー情報
    """
    return {
        "username": current_user.username,
        "email": current_user.email,
        "role": getattr(current_user.role, "value", current_user.role),
        "is_active": current_user.is_active
    }


# ===========================
# ヘルスチェック
# ===========================

@app.get("/", tags=["Health"])
async def root():
    """APIヘルスチェック"""
    return {"status": "ok", "message": "VANZAI API is running"}


@app.get("/api/health", tags=["Health"])
async def health_check():
    """詳細ヘルスチェック"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "services": {
            "database": "connected",
            "csv_import": "ready",
            "invoice": "ready",
            "payout": "ready"
        }
    }


# ===========================
# CSV取り込みエンドポイント
# ===========================

@app.post("/api/csv/import", response_model=CSVImportResponse, tags=["CSV Import"])
async def import_csv(
    request: CSVImportRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    CSV取り込み
    
    - **file_content**: Base64エンコードされたCSVファイル内容
    - **file_name**: ファイル名
    - **project_id**: 対象案件ID
    - **period_key**: 対象期間キー（YYYYMM）
    - **import_mode**: append（追加） or replace_scope（洗い替え）
    - **scope_type**: 洗い替えスコープ（project_month, project_day 等）
    """
    try:
        _ensure_csv_import_permission(db, current_user, request.project_id)
        file_name = _sanitize_upload_file_name(request.file_name)
        period_key = _validate_period_key(request.period_key)

        # Base64デコード
        file_bytes = base64.b64decode(request.file_content, validate=True)
        _validate_csv_file_bytes(file_bytes)

        # CSV取り込みサービス実行
        import_service = CsvImportService(db)
        result = import_service.import_csv(
            file_content=file_bytes,
            file_name=file_name,
            project_id=request.project_id,
            period_key=period_key,
            mode=_resolve_import_mode(request.import_mode),
            scope_type=_resolve_import_scope_type(request.scope_type),
            submitted_by=current_user.username,
        )

        return _build_csv_import_response(result)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Base64 データが不正です: {str(exc)}") from exc
    except VANZAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="CSV取り込みに失敗しました")


@app.post("/api/csv/upload", response_model=CSVImportResponse, tags=["CSV Import"])
async def upload_csv_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    period_key: str = Form(...),
    import_mode: str = Form("replace_scope"),
    scope_type: str = Form("project_month"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    CSVファイルアップロード
    
    multipart/form-data形式でCSVファイルを直接アップロード
    """
    try:
        file_name = _sanitize_upload_file_name(file.filename)
        period_key = _validate_period_key(period_key)
        _ensure_csv_import_permission(db, current_user, project_id)

        # ファイル読み込み
        content = await file.read()
        _validate_csv_file_bytes(content)

        # CSV取り込みサービス実行
        import_service = CsvImportService(db)
        result = import_service.import_csv(
            file_content=content,
            file_name=file_name,
            project_id=project_id,
            period_key=period_key,
            mode=_resolve_import_mode(import_mode),
            scope_type=_resolve_import_scope_type(scope_type),
            submitted_by=current_user.username,
        )

        return _build_csv_import_response(result)
    except HTTPException:
        raise
    except VANZAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="ファイルアップロードに失敗しました")


@app.get("/api/import-batches", response_model=ImportBatchListResponse, tags=["CSV Import"])
async def list_import_batches(
    query: ImportBatchListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """CSV取り込み履歴取得"""
    _ensure_import_batch_read_permission(db, current_user, query.project_id)

    from src.models.transaction import ImportBatch, Project

    sort_map = {
        "created_at": ImportBatch.created_at,
        "file_name": ImportBatch.file_name,
        "status": ImportBatch.status,
        "period_key": ImportBatch.period_key,
        "project_name": Project.name,
    }
    sort_column = sort_map.get(query.sort_by or "created_at", ImportBatch.created_at)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = db.query(ImportBatch, Project.name).join(Project, ImportBatch.project_id == Project.id, isouter=True)

    if query.project_id:
        stmt = stmt.filter(ImportBatch.project_id == query.project_id)
    if query.period_key:
        stmt = stmt.filter(ImportBatch.period_key == query.period_key)
    if query.status:
        stmt = stmt.filter(ImportBatch.status == query.status)
    if query.search:
        like_term = f"%{query.search}%"
        stmt = stmt.filter(
            or_(
                ImportBatch.file_name.ilike(like_term),
                ImportBatch.submitted_by.ilike(like_term),
                Project.name.ilike(like_term),
            )
        )

    role = UserRole(current_user.role)
    if role == UserRole.SITE_MANAGER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Site manager is not linked to worker")
        stmt = stmt.filter(
            or_(
                Project.primary_manager_id == current_user.worker_id,
                Project.secondary_manager_id == current_user.worker_id,
            )
        )

    total = stmt.count()
    rows = stmt.order_by(sort_expression, ImportBatch.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        ImportBatchListItem(
            id=batch.id,
            file_name=batch.file_name,
            project_id=batch.project_id,
            project_name=project_name or "-",
            period_key=batch.period_key,
            submitted_by=batch.submitted_by,
            submit_channel=batch.submit_channel,
            mode=batch.mode,
            scope_type=batch.scope_type,
            status=batch.status,
            success_rows=batch.count_success,
            error_rows=batch.count_error,
            skipped_rows=batch.count_skip,
            superseded_rows=batch.count_superseded,
            has_warnings=batch.has_row_count_warning or batch.has_total_time_warning,
            errors_preview=(batch.errors_json or [])[:5] if isinstance(batch.errors_json, list) else [],
            created_at=batch.created_at,
        )
        for batch, project_name in rows
    ]

    return ImportBatchListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


# ===========================
# ダッシュボードエンドポイント
# ===========================

@app.get("/api/dashboard", response_model=DashboardResponse, tags=["Dashboard"])
async def get_dashboard(
    period_key: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    ダッシュボード取得
    
    未処理項目、差異アラート、締め状況を一括取得
    """
    try:
        check_permission(current_user, Permission.PROJECT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    try:
        period_key = _default_period_key(period_key)
        project_ids: list[str] | None = None

        if UserRole(current_user.role) == UserRole.SITE_MANAGER:
            if not current_user.worker_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Site manager is not linked to worker")

            from src.models.transaction import Project

            project_ids = [
                project_id
                for project_id, in (
                    db.query(Project.id)
                    .filter(
                        or_(
                            Project.primary_manager_id == current_user.worker_id,
                            Project.secondary_manager_id == current_user.worker_id,
                        )
                    )
                    .all()
                )
            ]

        # ダッシュボードサマリー取得
        summary = get_dashboard_summary(db, period_key, project_ids=project_ids)

        # 未処理一覧（UI向けに item_type ごとに束ねる）
        unprocessed_items: list[UnprocessedItem] = []

        if summary.unprocessed_assignments:
            unprocessed_items.append(
                UnprocessedItem(
                    item_type="assignment_variance",
                    count=len(summary.unprocessed_assignments),
                    details=[
                        {
                            "assignment_id": a.assignment_id,
                            "project_name": a.project_name,
                            "worker_name": a.worker_name,
                            "work_date": a.work_date,
                            "expected_minutes": a.expected_minutes,
                            "actual_minutes": a.actual_minutes,
                            "delta_minutes": a.delta_minutes,
                            "status": _status_to_str(a.status),
                            "reason": a.reason,
                        }
                        for a in summary.unprocessed_assignments
                    ],
                )
            )

        if summary.missing_prices:
            unprocessed_items.append(
                UnprocessedItem(
                    item_type="missing_price",
                    count=len(summary.missing_prices),
                    details=[
                        {
                            "assignment_id": m.assignment_id,
                            "project_name": m.project_name,
                            "worker_name": m.worker_name,
                            "work_date": m.work_date,
                            "price_type": m.price_type,
                            "reason": m.reason,
                        }
                        for m in summary.missing_prices
                    ],
                )
            )

        if summary.unprocessed_invoices:
            unprocessed_items.append(
                UnprocessedItem(
                    item_type="unissued_invoice",
                    count=len(summary.unprocessed_invoices),
                    details=[
                        {
                            "invoice_id": i.invoice_id,
                            "client_name": i.client_name,
                            "project_name": i.project_name,
                            "period_key": i.period_key,
                            "status": _status_to_str(i.status),
                            "total_amount": i.total_amount,
                            "reason": i.reason,
                        }
                        for i in summary.unprocessed_invoices
                    ],
                )
            )

        if summary.unprocessed_payouts:
            unprocessed_items.append(
                UnprocessedItem(
                    item_type="unprocessed_payout",
                    count=len(summary.unprocessed_payouts),
                    details=[
                        {
                            "payout_id": p.payout_id,
                            "worker_name": p.worker_name,
                            "project_name": p.project_name,
                            "period_key": p.period_key,
                            "status": _status_to_str(p.status),
                            "total_amount": p.total_amount,
                            "reason": p.reason,
                        }
                        for p in summary.unprocessed_payouts
                    ],
                )
            )

        # 未締めプロジェクト（countのみ）
        if summary.unclosed_project_count:
            unprocessed_items.append(
                UnprocessedItem(
                    item_type="unclosed_projects",
                    count=summary.unclosed_project_count,
                    details=[],
                )
            )

        variance_alerts = [
            VarianceAlert(
                project_name=a.project_name,
                worker_name=a.worker_name,
                work_date=a.work_date,
                planned_minutes=a.expected_minutes,
                actual_minutes=a.actual_minutes,
                variance_minutes=a.delta_minutes,
            )
            for a in summary.unprocessed_assignments
        ]

        closing_status: list[ClosingStatusItem] = []
        for project, closing_row in get_project_closings_for_period(db, period_key, project_ids=project_ids):
            status_str = _status_to_str(closing_row.status) if closing_row else ClosingStatus.OPEN.value
            closed_at = None
            closed_by = None
            if status_str.lower() in {"hard_closed", "hard", "closed"}:
                closed_at = closing_row.hard_closed_at if closing_row else None
                closed_by = closing_row.hard_closed_by if closing_row else None
            elif status_str.lower() in {"soft_closed", "soft"}:
                closed_at = closing_row.soft_closed_at if closing_row else None
                closed_by = closing_row.soft_closed_by if closing_row else None

            closing_status.append(
                ClosingStatusItem(
                    project_id=project.id,
                    period_key=period_key,
                    project_name=project.name,
                    status=status_str,
                    closed_at=closed_at,
                    closed_by=closed_by,
                    release_count=closing_row.release_count if closing_row else 0,
                    last_released_at=closing_row.last_released_at if closing_row else None,
                    last_released_by=closing_row.last_released_by if closing_row else None,
                    reclose_deadline=closing_row.reclose_deadline if closing_row else None,
                )
            )

        return DashboardResponse(
            unprocessed_items=unprocessed_items,
            variance_alerts=variance_alerts,
            closing_status=closing_status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ダッシュボード取得エラー: {str(e)}")


# ===========================
# 実績一覧エンドポイント
# ===========================

@app.get("/api/actuals", response_model=ActualListResponse, tags=["Actuals"])
async def list_actuals(
    query: ActualListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """実績一覧取得"""
    try:
        check_permission(current_user, Permission.ACTUAL_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker, Role
    from src.models.transaction import Actual, ImportBatch, Project

    sort_map = {
        "work_date": Actual.work_date,
        "worker_name": Worker.name,
        "project_name": Project.name,
        "status": Actual.status,
        "calc_minutes_billable": Actual.calc_minutes_billable,
    }

    sort_column = sort_map.get(query.sort_by or "work_date", Actual.work_date)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(Actual, Project.name, Worker.name, Role.name, ImportBatch.file_name)
        .join(Project, Actual.project_id == Project.id)
        .join(Worker, Actual.worker_id == Worker.id)
        .join(Role, Actual.role_id == Role.id)
        .join(ImportBatch, Actual.import_batch_id == ImportBatch.id)
    )

    if query.project_id:
        stmt = stmt.filter(Actual.project_id == query.project_id)
    if query.worker_id:
        stmt = stmt.filter(Actual.worker_id == query.worker_id)
    if query.status:
        stmt = stmt.filter(Actual.status == query.status)
    if query.needs_review is not None:
        stmt = stmt.filter(Actual.needs_review == query.needs_review)
    if query.period_key:
        stmt = stmt.filter(Actual.period_key == query.period_key)
    if query.work_date_from:
        stmt = stmt.filter(Actual.work_date >= query.work_date_from)
    if query.work_date_to:
        stmt = stmt.filter(Actual.work_date <= query.work_date_to)
    if query.import_batch_id:
        stmt = stmt.filter(Actual.import_batch_id == query.import_batch_id)

    role = UserRole(current_user.role)
    if role == UserRole.SITE_MANAGER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Site manager is not linked to worker")
        if query.project_id and not can_access_project(db, current_user, query.project_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied")

        stmt = stmt.filter(
            or_(
                Project.primary_manager_id == current_user.worker_id,
                Project.secondary_manager_id == current_user.worker_id,
            )
        )
    elif role == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        stmt = stmt.filter(Actual.worker_id == current_user.worker_id)

    total = stmt.count()
    rows = (
        stmt.order_by(sort_expression, Actual.id.desc())
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )

    items = [
        ActualListItem(
            id=actual.id,
            project_id=actual.project_id,
            project_name=project_name,
            worker_id=actual.worker_id,
            worker_name=worker_name,
            role_id=actual.role_id,
            role_name=role_name,
            assignment_id=actual.assignment_id,
            import_batch_id=actual.import_batch_id,
            import_batch_file_name=file_name,
            work_date=actual.work_date,
            start_time=actual.start_time.isoformat() if actual.start_time else None,
            end_time=actual.end_time.isoformat() if actual.end_time else None,
            calc_minutes_billable=actual.calc_minutes_billable,
            applied_price_sales=actual.applied_price_sales,
            applied_price_outsource=actual.applied_price_outsource,
            status=actual.status,
            needs_review=actual.needs_review,
            review_reason=actual.review_reason,
            external_row_key=actual.external_row_key,
        )
        for actual, project_name, worker_name, role_name, file_name in rows
    ]

    return ActualListResponse(
        items=items,
        total=total,
        offset=query.offset,
        limit=query.limit,
    )


# ===========================
# アサイン一覧エンドポイント
# ===========================

@app.get("/api/assignments", response_model=AssignmentListResponse, tags=["Assignments"])
async def list_assignments(
    query: AssignmentListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン一覧取得"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker, Role
    from src.models.transaction import Assignment, Project, ShiftSlot

    sort_map = {
        "work_date": ShiftSlot.work_date,
        "worker_name": Worker.name,
        "project_name": Project.name,
        "status": Assignment.status,
    }
    sort_column = sort_map.get(query.sort_by or "work_date", ShiftSlot.work_date)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(Assignment, Project.name, ShiftSlot.work_date, ShiftSlot.shift_label, Worker.name, Role.name)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .join(Project, ShiftSlot.project_id == Project.id)
        .join(Worker, Assignment.worker_id == Worker.id)
        .join(Role, Assignment.role_id == Role.id)
    )

    if query.project_id:
        stmt = stmt.filter(Project.id == query.project_id)
    if query.worker_id:
        stmt = stmt.filter(Assignment.worker_id == query.worker_id)
    if query.role_id:
        stmt = stmt.filter(Assignment.role_id == query.role_id)
    if query.status:
        stmt = stmt.filter(Assignment.status == query.status)
    if query.work_date_from:
        stmt = stmt.filter(ShiftSlot.work_date >= query.work_date_from)
    if query.work_date_to:
        stmt = stmt.filter(ShiftSlot.work_date <= query.work_date_to)

    role = UserRole(current_user.role)
    if role == UserRole.SITE_MANAGER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Site manager is not linked to worker")
        if query.project_id and not can_access_project(db, current_user, query.project_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied")
        stmt = stmt.filter(
            or_(
                Project.primary_manager_id == current_user.worker_id,
                Project.secondary_manager_id == current_user.worker_id,
            )
        )
    elif role == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        stmt = stmt.filter(Assignment.worker_id == current_user.worker_id)

    total = stmt.count()
    rows = (
        stmt.order_by(sort_expression, Assignment.id.desc())
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )

    items = [
        AssignmentListItem(
            id=assignment.id,
            shift_slot_id=assignment.shift_slot_id,
            project_id=assignment.shift_slot.project_id,
            project_name=project_name,
            work_date=work_date,
            shift_label=shift_label,
            worker_id=assignment.worker_id,
            worker_name=worker_name,
            role_id=assignment.role_id,
            role_name=role_name,
            status=assignment.status,
            cancel_reason=assignment.cancel_reason,
            locked_price_sales=assignment.locked_price_sales,
            locked_price_outsource=assignment.locked_price_outsource,
        )
        for assignment, project_name, work_date, shift_label, worker_name, role_name in rows
    ]

    return AssignmentListResponse(
        items=items,
        total=total,
        offset=query.offset,
        limit=query.limit,
    )


# ===========================
# 案件一覧エンドポイント
# ===========================

@app.get("/api/projects", response_model=ProjectListResponse, tags=["Projects"])
async def list_projects(
    query: ProjectListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """案件一覧取得"""
    try:
        check_permission(current_user, Permission.PROJECT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Client, ProjectType, Site
    from src.models.transaction import Project

    sort_map = {
        "name": Project.name,
        "code": Project.code,
        "client_name": Client.name,
        "site_name": Site.name,
        "project_type_name": ProjectType.name,
        "start_date": Project.start_date,
        "end_date": Project.end_date,
    }
    sort_column = sort_map.get(query.sort_by or "name", Project.name)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(Project, Client.name, Site.name, ProjectType.name)
        .join(Client, Project.client_id == Client.id)
        .outerjoin(Site, Project.site_id == Site.id)
        .outerjoin(ProjectType, Project.project_type_id == ProjectType.id)
    )

    if query.client_id:
        stmt = stmt.filter(Project.client_id == query.client_id)
    if query.site_id:
        stmt = stmt.filter(Project.site_id == query.site_id)
    if query.project_type_id:
        stmt = stmt.filter(Project.project_type_id == query.project_type_id)
    if query.is_active is not None:
        stmt = stmt.filter(Project.is_active == query.is_active)
    if query.search:
        search_term = f"%{query.search}%"
        stmt = stmt.filter(or_(Project.name.ilike(search_term), Project.code.ilike(search_term)))

    role = UserRole(current_user.role)
    if role == UserRole.SITE_MANAGER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Site manager is not linked to worker")
        stmt = stmt.filter(
            or_(
                Project.primary_manager_id == current_user.worker_id,
                Project.secondary_manager_id == current_user.worker_id,
            )
        )

    total = stmt.count()
    rows = stmt.order_by(sort_expression, Project.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        ProjectListItem(
            id=project.id,
            code=project.code,
            name=project.name,
            client_name=client_name,
            site_name=site_name or "",
            project_type_name=project_type_name or "",
            start_date=project.start_date,
            end_date=project.end_date,
            is_active=project.is_active,
        )
        for project, client_name, site_name, project_type_name in rows
    ]

    return ProjectListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


# ===========================
# シフト枠一覧エンドポイント
# ===========================

@app.get("/api/shift-slots", response_model=ShiftSlotListResponse, tags=["Shift Slots"])
async def list_shift_slots(
    query: ShiftSlotListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """シフト枠一覧取得"""
    try:
        check_permission(current_user, Permission.SHIFT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from sqlalchemy import select
    from src.models.transaction import Assignment, Project, ShiftSlot

    assigned_count_subquery = (
        select(Assignment.shift_slot_id, func.count(Assignment.id).label("assigned_count"))
        .group_by(Assignment.shift_slot_id)
        .subquery()
    )

    sort_map = {
        "work_date": ShiftSlot.work_date,
        "project_name": Project.name,
        "shift_label": ShiftSlot.shift_label,
        "required_count": ShiftSlot.required_count,
    }
    sort_column = sort_map.get(query.sort_by or "work_date", ShiftSlot.work_date)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(ShiftSlot, Project.name, func.coalesce(assigned_count_subquery.c.assigned_count, 0))
        .join(Project, ShiftSlot.project_id == Project.id)
        .outerjoin(assigned_count_subquery, assigned_count_subquery.c.shift_slot_id == ShiftSlot.id)
    )

    if query.project_id:
        stmt = stmt.filter(ShiftSlot.project_id == query.project_id)
    if query.work_date_from:
        stmt = stmt.filter(ShiftSlot.work_date >= query.work_date_from)
    if query.work_date_to:
        stmt = stmt.filter(ShiftSlot.work_date <= query.work_date_to)
    if query.search:
        search_term = f"%{query.search}%"
        stmt = stmt.filter(or_(Project.name.ilike(search_term), ShiftSlot.shift_label.ilike(search_term)))

    role = UserRole(current_user.role)
    if role == UserRole.SITE_MANAGER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Site manager is not linked to worker")
        if query.project_id and not can_access_project(db, current_user, query.project_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied")
        stmt = stmt.filter(
            or_(
                Project.primary_manager_id == current_user.worker_id,
                Project.secondary_manager_id == current_user.worker_id,
            )
        )

    total = stmt.count()
    rows = stmt.order_by(sort_expression, ShiftSlot.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        ShiftSlotListItem(
            id=slot.id,
            project_id=slot.project_id,
            project_name=project_name,
            work_date=slot.work_date,
            start_time=slot.start_time.isoformat() if slot.start_time else None,
            end_time=slot.end_time.isoformat() if slot.end_time else None,
            shift_label=slot.shift_label,
            required_count=slot.required_count,
            assigned_count=assigned_count,
            notes=slot.notes,
        )
        for slot, project_name, assigned_count in rows
    ]

    return ShiftSlotListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


# ===========================
# 経費一覧エンドポイント
# ===========================

@app.get("/api/expenses", response_model=ExpenseListResponse, tags=["Expenses"])
async def list_expenses(
    query: ExpenseListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """経費一覧取得"""
    try:
        check_permission(current_user, Permission.EXPENSE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker
    from src.models.transaction import Expense, Project

    sort_map = {
        "expense_date": Expense.expense_date,
        "project_name": Project.name,
        "worker_name": Worker.name,
        "amount": Expense.amount,
        "status": Expense.status,
    }
    sort_column = sort_map.get(query.sort_by or "expense_date", Expense.expense_date)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(Expense, Project.name, Worker.name)
        .join(Project, Expense.project_id == Project.id)
        .outerjoin(Worker, Expense.worker_id == Worker.id)
    )

    if query.project_id:
        stmt = stmt.filter(Expense.project_id == query.project_id)
    if query.worker_id:
        stmt = stmt.filter(Expense.worker_id == query.worker_id)
    if query.status:
        stmt = stmt.filter(Expense.status == query.status)
    if query.category:
        stmt = stmt.filter(Expense.category == query.category)
    if query.expense_date_from:
        stmt = stmt.filter(Expense.expense_date >= query.expense_date_from)
    if query.expense_date_to:
        stmt = stmt.filter(Expense.expense_date <= query.expense_date_to)

    total = stmt.count()
    rows = stmt.order_by(sort_expression, Expense.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        ExpenseListItem(
            id=expense.id,
            expense_date=expense.expense_date,
            project_id=expense.project_id,
            project_name=project_name,
            worker_id=expense.worker_id,
            worker_name=worker_name or "",
            category=expense.category,
            amount=expense.amount,
            status=expense.status,
            approved_by=expense.approved_by,
            approved_at=expense.approved_at,
            has_receipt=bool(expense.receipt_file_key),
        )
        for expense, project_name, worker_name in rows
    ]

    return ExpenseListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


# ===========================
# 単価ルール一覧エンドポイント
# ===========================

@app.get("/api/price-rules", response_model=PriceRuleListResponse, tags=["Price Rules"])
async def list_price_rules(
    query: PriceRuleListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """単価ルール一覧取得"""
    try:
        check_permission(current_user, Permission.PRICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import PriceRule

    sort_map = {
        "name": PriceRule.name,
        "priority": PriceRule.priority,
        "valid_from": PriceRule.valid_from,
        "valid_to": PriceRule.valid_to,
    }
    sort_column = sort_map.get(query.sort_by or "priority", PriceRule.priority)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = db.query(PriceRule).filter(PriceRule.deleted_at.is_(None))

    if query.is_active is not None:
        stmt = stmt.filter(PriceRule.is_active == query.is_active)
    if query.search:
        search_term = f"%{query.search}%"
        stmt = stmt.filter(PriceRule.name.ilike(search_term))

    total = stmt.count()
    rows = stmt.order_by(sort_expression, PriceRule.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        PriceRuleListItem(
            id=rule.id,
            name=rule.name,
            priority=rule.priority,
            sales_price=rule.sales_price,
            outsource_price=rule.outsource_price,
            valid_from=rule.valid_from,
            valid_to=rule.valid_to,
            is_active=rule.is_active,
        )
        for rule in rows
    ]

    return PriceRuleListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.get("/api/price-sales", response_model=PriceSalesListResponse, tags=["Price"])
async def list_price_sales(
    query: PriceSalesListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """売上単価一覧取得"""
    try:
        check_permission(current_user, Permission.PRICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Client, PriceSales, Role
    from src.models.transaction import Project

    sort_map = {
        "project_name": Project.name,
        "role_name": Role.name,
        "client_name": Client.name,
        "unit_price": PriceSales.unit_price,
        "valid_from": PriceSales.valid_from,
        "valid_to": PriceSales.valid_to,
    }
    sort_column = sort_map.get(query.sort_by or "valid_from", PriceSales.valid_from)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(PriceSales, Project.name, Role.name, Client.name)
        .outerjoin(Project, PriceSales.project_id == Project.id)
        .outerjoin(Role, PriceSales.role_id == Role.id)
        .outerjoin(Client, PriceSales.client_id == Client.id)
        .filter(PriceSales.deleted_at.is_(None))
    )

    if query.project_id:
        stmt = stmt.filter(PriceSales.project_id == query.project_id)
    if query.role_id:
        stmt = stmt.filter(PriceSales.role_id == query.role_id)
    if query.client_id:
        stmt = stmt.filter(PriceSales.client_id == query.client_id)
    if query.is_default is not None:
        stmt = stmt.filter(PriceSales.is_default == query.is_default)

    total = stmt.count()
    rows = stmt.order_by(sort_expression, PriceSales.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        PriceSalesListItem(
            id=price.id,
            project_id=price.project_id,
            project_name=project_name or "",
            role_id=price.role_id,
            role_name=role_name or "",
            client_id=price.client_id,
            client_name=client_name or "",
            unit_price=price.unit_price,
            unit_type=price.unit_type,
            valid_from=price.valid_from,
            valid_to=price.valid_to,
            is_default=price.is_default,
        )
        for price, project_name, role_name, client_name in rows
    ]

    return PriceSalesListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.get("/api/price-outsource", response_model=PriceOutsourceListResponse, tags=["Price"])
async def list_price_outsource(
    query: PriceOutsourceListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """外注単価一覧取得"""
    try:
        check_permission(current_user, Permission.PRICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import PriceOutsource, Role, Worker
    from src.models.transaction import Project

    sort_map = {
        "project_name": Project.name,
        "worker_name": Worker.name,
        "role_name": Role.name,
        "unit_price": PriceOutsource.unit_price,
        "valid_from": PriceOutsource.valid_from,
        "valid_to": PriceOutsource.valid_to,
    }
    sort_column = sort_map.get(query.sort_by or "valid_from", PriceOutsource.valid_from)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(PriceOutsource, Project.name, Worker.name, Role.name)
        .outerjoin(Project, PriceOutsource.project_id == Project.id)
        .outerjoin(Worker, PriceOutsource.worker_id == Worker.id)
        .outerjoin(Role, PriceOutsource.role_id == Role.id)
        .filter(PriceOutsource.deleted_at.is_(None))
    )

    if query.project_id:
        stmt = stmt.filter(PriceOutsource.project_id == query.project_id)
    if query.role_id:
        stmt = stmt.filter(PriceOutsource.role_id == query.role_id)
    if query.worker_id:
        stmt = stmt.filter(PriceOutsource.worker_id == query.worker_id)
    if query.is_default is not None:
        stmt = stmt.filter(PriceOutsource.is_default == query.is_default)

    total = stmt.count()
    rows = stmt.order_by(sort_expression, PriceOutsource.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        PriceOutsourceListItem(
            id=price.id,
            project_id=price.project_id,
            project_name=project_name or "",
            worker_id=price.worker_id,
            worker_name=worker_name or "",
            role_id=price.role_id,
            role_name=role_name or "",
            unit_price=price.unit_price,
            unit_type=price.unit_type,
            valid_from=price.valid_from,
            valid_to=price.valid_to,
            is_default=price.is_default,
        )
        for price, project_name, worker_name, role_name in rows
    ]

    return PriceOutsourceListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


# ===========================
# 請求一覧エンドポイント
# ===========================

@app.get("/api/invoices", response_model=InvoiceListResponse, tags=["Invoice"])
async def list_invoices(
    query: InvoiceListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """請求一覧取得"""
    try:
        check_permission(current_user, Permission.INVOICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Client
    from src.models.transaction import Invoice, Project

    sort_map = {
        "period_key": Invoice.period_key,
        "client_name": Client.name,
        "project_name": Project.name,
        "status": Invoice.status,
        "version": Invoice.version,
        "total_amount": Invoice.total_amount,
        "issued_at": Invoice.issued_at,
    }
    sort_column = sort_map.get(query.sort_by or "issued_at", Invoice.issued_at)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(Invoice, Client.name, Project.name)
        .join(Client, Invoice.client_id == Client.id)
        .outerjoin(Project, Invoice.project_id == Project.id)
    )

    if query.period_key:
        stmt = stmt.filter(Invoice.period_key == query.period_key)
    if query.client_id:
        stmt = stmt.filter(Invoice.client_id == query.client_id)
    if query.project_id:
        stmt = stmt.filter(Invoice.project_id == query.project_id)
    if query.status:
        stmt = stmt.filter(Invoice.status == query.status)
    if query.version is not None:
        stmt = stmt.filter(Invoice.version == query.version)

    total = stmt.count()
    rows = (
        stmt.order_by(sort_expression, Invoice.id.desc())
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )

    items = [
        InvoiceListItem(
            id=invoice.id,
            invoice_number=invoice.id,
            client_id=invoice.client_id,
            client_name=client_name,
            project_id=invoice.project_id,
            project_name=project_name or "",
            period_key=invoice.period_key,
            version=invoice.version,
            status=invoice.status,
            total_amount=invoice.total_amount,
            issued_at=invoice.issued_at,
            has_pdf=bool(invoice.pdf_object_key),
        )
        for invoice, client_name, project_name in rows
    ]

    return InvoiceListResponse(
        items=items,
        total=total,
        offset=query.offset,
        limit=query.limit,
    )


# ===========================
# 支払一覧エンドポイント
# ===========================

@app.get("/api/payouts", response_model=PayoutListResponse, tags=["Payout"])
async def list_payouts(
    query: PayoutListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """支払一覧取得"""
    try:
        check_permission(current_user, Permission.PAYOUT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Supplier, Worker
    from src.models.transaction import Payout, Project

    sort_map = {
        "period_key": Payout.period_key,
        "payee_name": Worker.name,
        "status": Payout.status,
        "version": Payout.version,
        "total_amount": Payout.total_amount,
        "approved_at": Payout.approved_at,
        "paid_at": Payout.paid_at,
        "project_name": Project.name,
    }
    sort_column = sort_map.get(query.sort_by or "approved_at", Payout.approved_at)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(Payout, Worker.name, Supplier.name, Project.name)
        .outerjoin(Worker, Payout.worker_id == Worker.id)
        .outerjoin(Supplier, Payout.supplier_id == Supplier.id)
        .outerjoin(Project, Payout.project_id == Project.id)
    )

    if query.period_key:
        stmt = stmt.filter(Payout.period_key == query.period_key)
    if query.worker_id:
        stmt = stmt.filter(Payout.worker_id == query.worker_id)
    if query.supplier_id:
        stmt = stmt.filter(Payout.supplier_id == query.supplier_id)
    if query.project_id:
        stmt = stmt.filter(Payout.project_id == query.project_id)
    if query.status:
        stmt = stmt.filter(Payout.status == query.status)

    total = stmt.count()
    rows = (
        stmt.order_by(sort_expression, Payout.id.desc())
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )

    items = []
    for payout, worker_name, supplier_name, project_name in rows:
        payee_name = worker_name or supplier_name or ""
        payee_type = "worker" if payout.worker_id else "supplier" if payout.supplier_id else "unknown"
        items.append(
            PayoutListItem(
                id=payout.id,
                payout_number=payout.id,
                payee_name=payee_name,
                payee_type=payee_type,
                project_id=payout.project_id,
                project_name=project_name or "",
                period_key=payout.period_key,
                version=payout.version,
                status=payout.status,
                total_amount=payout.total_amount,
                approved_at=payout.approved_at,
                paid_at=payout.paid_at,
            )
        )

    return PayoutListResponse(
        items=items,
        total=total,
        offset=query.offset,
        limit=query.limit,
    )


# ===========================
# 請求書エンドポイント
# ===========================

@app.post("/api/invoices/generate", response_model=InvoiceResponse, tags=["Invoice"])
async def generate_invoice(
    request: InvoiceGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    請求書生成
    
    指定したプロジェクトと期間の実績から請求書を生成
    """
    try:
        # Project からclient_id取得
        from src.models.transaction import Project
        project = db.query(Project).filter(Project.id == request.project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        check_permission(current_user, Permission.INVOICE_GENERATE)
        invoice = invoice_service.generate_invoice(
            session=db,
            client_id=project.client_id,
            project_id=request.project_id,
            period_key=request.period_key,
            billing_date=date.today(),
            user_id=current_user.username
        )
        
        # 明細行を取得
        lines = [
            InvoiceLineResponse(
                line_type=_status_to_str(line.line_type),
                description=line.description,
                quantity=line.quantity_snapshot,
                unit_price=line.unit_price_snapshot,
                amount=line.line_amount,
            )
            for line in invoice.lines
        ]
        
        return InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.id,
            client_name=invoice.client.name if invoice.client else "",
            project_name=invoice.project.name if invoice.project else "",
            period_key=invoice.period_key,
            total_amount=invoice.total_amount,
            status=_status_to_str(invoice.status),
            lines=lines,
            issued_at=invoice.issued_at
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="請求書生成に失敗しました")


@app.post("/api/invoices/{invoice_id}/issue", response_model=InvoiceResponse, tags=["Invoice"])
async def issue_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    請求書発行
    
    下書き状態の請求書を発行済みにする
    """
    try:
        check_permission(current_user, Permission.INVOICE_ISSUE)
        invoice = invoice_service.issue_invoice(
            session=db,
            invoice_id=invoice_id,
            user_id=current_user.username,
        )
        
        lines = [
            InvoiceLineResponse(
                line_type=_status_to_str(line.line_type),
                description=line.description,
                quantity=line.quantity_snapshot,
                unit_price=line.unit_price_snapshot,
                amount=line.line_amount,
            )
            for line in invoice.lines
        ]
        
        return InvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.id,
            client_name=invoice.client.name if invoice.client else "",
            project_name=invoice.project.name if invoice.project else "",
            period_key=invoice.period_key,
            total_amount=invoice.total_amount,
            status=_status_to_str(invoice.status),
            lines=lines,
            issued_at=invoice.issued_at
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="請求書発行に失敗しました")


# ===========================
# 支払明細エンドポイント
# ===========================

@app.post("/api/payouts/generate", response_model=PayoutResponse, tags=["Payout"])
async def generate_payout(
    request: PayoutGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    支払明細生成
    
    指定したプロジェクト、稼働者、期間の実績から支払明細を生成
    """
    try:
        check_permission(current_user, Permission.PAYOUT_GENERATE)
        payout = payout_service.generate_payout(
            session=db,
            worker_id=request.worker_id,
            project_id=request.project_id,
            period_key=request.period_key,
            payment_date=date.today(),
            user_id=current_user.username,
        )
        
        lines = [
            PayoutLineResponse(
                line_type=_status_to_str(line.line_type),
                description=line.description,
                quantity=line.quantity_snapshot,
                unit_price=line.unit_price_snapshot,
                amount=line.line_amount,
            )
            for line in payout.lines
        ]
        
        return PayoutResponse(
            id=payout.id,
            payout_number=payout.id,
            worker_name=payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else ""),
            project_name=payout.project.name if payout.project else "",
            period_key=payout.period_key,
            total_amount=payout.total_amount,
            status=_status_to_str(payout.status),
            lines=lines,
            approved_at=payout.approved_at,
            paid_at=payout.paid_at,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="支払明細生成に失敗しました")


@app.post("/api/payouts/{payout_id}/confirm", response_model=PayoutResponse, tags=["Payout"])
async def confirm_payout(
    payout_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    支払確定
    
    下書き状態の支払明細を確定する
    """
    try:
        check_permission(current_user, Permission.PAYOUT_APPROVE)
        payout = payout_service.approve_payout(
            session=db,
            payout_id=payout_id,
            user_id=current_user.username,
        )
        
        lines = [
            PayoutLineResponse(
                line_type=_status_to_str(line.line_type),
                description=line.description,
                quantity=line.quantity_snapshot,
                unit_price=line.unit_price_snapshot,
                amount=line.line_amount,
            )
            for line in payout.lines
        ]
        
        return PayoutResponse(
            id=payout.id,
            payout_number=payout.id,
            worker_name=payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else ""),
            project_name=payout.project.name if payout.project else "",
            period_key=payout.period_key,
            total_amount=payout.total_amount,
            status=_status_to_str(payout.status),
            lines=lines,
            approved_at=payout.approved_at,
            paid_at=payout.paid_at,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="支払確定に失敗しました")


@app.post("/api/billing/generate-monthly", response_model=MonthlyBillingGenerateResponse, tags=["Billing"])
async def generate_monthly_invoice_and_payout(
    request: MonthlyBillingGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    月次一括生成

    指定年月について、
    - 請求書（クライアント単位）
    - 支払明細（稼働者単位）
    をまとめて生成する。
    """
    try:
        check_permission(current_user, Permission.INVOICE_GENERATE)
        check_permission(current_user, Permission.PAYOUT_GENERATE)
        result = generate_monthly_billing(
            session=db,
            period_key=request.period_key,
            user_id=current_user.username,
        )
        db.commit()

        return MonthlyBillingGenerateResponse(
            period_key=request.period_key,
            generated_invoices=result.generated_invoices,
            skipped_invoices=result.skipped_invoices,
            failed_invoices=result.failed_invoices,
            generated_payouts=result.generated_payouts,
            skipped_payouts=result.skipped_payouts,
            failed_payouts=result.failed_payouts,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="月次一括生成に失敗しました")


# ===========================
# 締め処理エンドポイント
# ===========================

def _build_closing_response(result) -> ClosingResponse:
    status_str = _status_to_str(result.status)
    closed_at = None
    closed_by = None
    if status_str.lower() in {"hard_closed", "hard", "closed"}:
        closed_at = result.hard_closed_at
        closed_by = result.hard_closed_by
    elif status_str.lower() in {"soft_closed", "soft"}:
        closed_at = result.soft_closed_at
        closed_by = result.soft_closed_by

    return ClosingResponse(
        id=result.id,
        project_id=result.project_id,
        period_key=result.period_key,
        status=result.status,
        closed_at=closed_at,
        closed_by=closed_by,
        release_count=result.release_count,
        last_released_at=result.last_released_at,
        last_released_by=result.last_released_by,
        last_release_reason=result.last_release_reason,
        reclose_deadline=result.reclose_deadline,
    )

@app.post("/api/closing/soft", response_model=ClosingResponse, tags=["Closing"])
async def close_soft(
    request: SoftCloseRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Soft Close実行
    
    指定したプロジェクトと期間をSoft Close（解除可能）
    """
    try:
        check_permission(current_user, Permission.SOFT_CLOSE)
        result = closing.soft_close(
            session=db,
            project_id=request.project_id,
            period_key=request.period_key,
            user_id=current_user.username,
            notes=request.reason
        )
        db.commit()

        return _build_closing_response(result)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Soft Closeに失敗しました")


@app.post("/api/closing/hard", response_model=ClosingResponse, tags=["Closing"])
async def close_hard(
    request: HardCloseRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Hard Close実行
    
    指定したプロジェクトと期間をHard Close（二者承認必要）
    """
    try:
        check_permission(current_user, Permission.HARD_CLOSE)
        result = closing.hard_close(
            session=db,
            project_id=request.project_id,
            period_key=request.period_key,
            user_id=current_user.username,
            approver_id=request.approver,
            notes=request.reason
        )
        db.commit()

        return _build_closing_response(result)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Hard Closeに失敗しました")


@app.post("/api/closing/soft/release", response_model=ClosingResponse, tags=["Closing"])
async def release_close_soft(
    request: SoftCloseReleaseRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Soft Close解除

    指定したプロジェクトと期間の Soft Close を解除する
    """
    try:
        check_permission(current_user, Permission.SOFT_CLOSE_RELEASE)
        result = closing.release_soft_close(
            session=db,
            project_id=request.project_id,
            period_key=request.period_key,
            user_id=current_user.username,
            approver_id=request.approver,
            reason=request.reason,
        )
        db.commit()

        return _build_closing_response(result)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Soft Close解除に失敗しました")


@app.post("/api/closing/hard/release", response_model=ClosingResponse, tags=["Closing"])
async def release_close_hard(
    request: HardCloseReleaseRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Hard Close解除

    指定したプロジェクトと期間の Hard Close を例外解除する
    """
    try:
        check_permission(current_user, Permission.HARD_CLOSE_RELEASE)
        result = closing.release_hard_close(
            session=db,
            project_id=request.project_id,
            period_key=request.period_key,
            user_id=current_user.username,
            approver_id=request.approver,
            reason=request.reason,
        )
        db.commit()

        return _build_closing_response(result)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Hard Close解除に失敗しました")


# ===========================
# 集計エンドポイント
# ===========================

@app.get("/api/aggregation/sales", tags=["Aggregation"])
async def get_sales_aggregation(
    year: int,
    month: int,
    project_id: str = None,
    client_id: str = None,
    db: Session = Depends(get_db)
):
    """
    売上集計（予定/確定）
    
    - **year**: 集計年
    - **month**: 集計月
    - **project_id**: (Optional) 案件ID指定
    - **client_id**: (Optional) クライアントID指定
    """
    try:
        period_key = f"{year:04d}{month:02d}"
        results = aggregation.aggregate_by_project(
            session=db,
            period_key=period_key
        )
        
        # フィルタリング
        if project_id:
            results = [r for r in results if r.project_id == project_id]
        if client_id:
            results = [r for r in results if r.client_id == client_id]
        
        return {
            "period": f"{year}-{month:02d}",
            "count": len(results),
            "items": [
                {
                    "project_id": r.project_id,
                    "project_name": r.project_name,
                    "client_id": r.client_id,
                    "client_name": r.client_name,
                    "planned": {
                        "hours": float(r.planned_hours),
                        "sales": float(r.planned_sales),
                        "cost": float(r.planned_cost),
                        "profit": float(r.planned_profit),
                        "profit_rate": float(r.planned_profit_rate) if r.planned_profit_rate else None
                    },
                    "confirmed": {
                        "hours": float(r.confirmed_hours),
                        "sales": float(r.confirmed_sales),
                        "cost": float(r.confirmed_cost),
                        "profit": float(r.confirmed_profit),
                        "profit_rate": float(r.confirmed_profit_rate) if r.confirmed_profit_rate else None
                    },
                    "delta": {
                        "hours": float(r.delta_hours),
                        "sales": float(r.delta_sales),
                        "cost": float(r.delta_cost),
                        "profit": float(r.delta_profit)
                    }
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"売上集計エラー: {str(e)}")


@app.get("/api/aggregation/outsource", tags=["Aggregation"])
async def get_outsource_aggregation(
    year: int,
    month: int,
    worker_id: str = None,
    db: Session = Depends(get_db)
):
    """
    外注費集計（予定/確定）
    
    - **year**: 集計年
    - **month**: 集計月
    - **worker_id**: (Optional) 稼働者ID指定
    """
    try:
        period_key = f"{year:04d}{month:02d}"
        
        # 簡易実装: Actualから集計
        from src.models.transaction import Actual
        from src.models.master import Worker
        
        query = db.query(
            Worker.id,
            Worker.name,
            func.sum(Actual.calc_minutes_billable).label("total_minutes"),
            func.sum(Actual.applied_price_outsource * Actual.calc_minutes_billable / 60).label("total_amount")
        ).join(Actual, Actual.worker_id == Worker.id).filter(
            Actual.period_key == period_key,
            Actual.status == "active"
        ).group_by(Worker.id, Worker.name)
        
        if worker_id:
            query = query.filter(Worker.id == worker_id)
        
        results = query.all()
        
        return {
            "period": f"{year}-{month:02d}",
            "count": len(results),
            "items": [
                {
                    "worker_id": r.id,
                    "worker_name": r.name,
                    "confirmed": {
                        "hours": float(r.total_minutes / 60) if r.total_minutes else 0,
                        "amount": float(r.total_amount) if r.total_amount else 0
                    }
                }
                for r in results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"外注費集計エラー: {str(e)}")


# ===========================
# 監査ログエンドポイント
# ===========================

@app.post("/api/audit/search", response_model=AuditLogListResponse, tags=["Audit"])
async def search_audit_logs(
    request: AuditLogSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    監査ログ検索
    
    各種条件で監査ログを検索
    """
    try:
        check_permission(current_user, Permission.AUDIT_LOG_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    try:
        audit_service = AuditService(db)
        result = audit_service.search_audit_logs(
            AuditLogSearchFilter(
                period_key=request.period_key,
                project_id=request.project_id,
                action_type=request.action_type,
                action_group=request.action_group,
                actor=request.actor,
                target_type=request.target_type,
                target_id=request.target_id,
                date_from=request.date_from,
                date_to=request.date_to,
                limit=request.limit,
                offset=request.offset,
            )
        )

        items = [
            AuditLogResponse(
                id=log.id,
                timestamp=log.created_at,
                action=log.action,
                actor=log.actor,
                actor_role=log.actor_role,
                project_id=_extract_audit_project_id(
                    log.extra_metadata,
                    log.before_value,
                    log.after_value,
                    log.target_type,
                    log.target_id,
                ),
                target_type=log.target_type,
                target_id=log.target_id,
                reason=log.reason,
                details=log.extra_metadata,
                details_summary=_summarize_audit_log_details(log.extra_metadata, log.reason),
            )
            for log in result.logs
        ]

        return AuditLogListResponse(
            items=items,
            total=result.total_count,
            offset=request.offset,
            limit=request.limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"監査ログ検索エラー: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
