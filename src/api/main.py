"""
FastAPI メインアプリケーション

案件・シフト・実績・請求・支払 一元管理システムのREST API
"""
from contextlib import asynccontextmanager
import hashlib
import mimetypes
import os
from pathlib import Path, PurePath
import re
import secrets
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Depends, HTTPException, Query, Request, UploadFile, File, Form, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_, select
from typing import List, Optional
import base64
from datetime import date, datetime, time, timedelta, timezone

from src.api.deps import get_db
from src.api.jwt_auth import (
    authenticate_user, 
    create_access_token, 
    create_refresh_token,
    get_current_user,
    get_current_active_user,
    get_password_hash,
    verify_password,
)
from src.api.schemas import (
    CSVImportRequest, CSVImportResponse,
    ImportBatchListItem, ImportBatchListQuery, ImportBatchListResponse,
    DashboardResponse, UnprocessedItem, VarianceAlert, ClosingStatusItem,
    ActualListQuery, ActualListItem, ActualListResponse, AttendanceActionRequest, AttendanceRecordResponse,
    WorkerAvailabilityListQuery, WorkerAvailabilityListItem, WorkerAvailabilityListResponse, WorkerAvailabilityUpsertRequest,
    WorkerAvailabilityPreferenceResponse, WorkerAvailabilityPreferenceUpsertRequest,
    AvailabilityCalendarResponse, CalendarWorkerRow, CalendarDayInfo, CalendarDayAssignment,
    AssignmentListQuery, AssignmentListItem, AssignmentListResponse, AssignmentReminderSendRequest, AssignmentReminderSendResponse, AssignmentReminderSendWorkerResult, AssignmentReminderHistoryRequest, AssignmentReminderHistoryItem, AssignmentReminderHistoryResponse, AssignmentEscalationSendRequest, AssignmentEscalationSendResponse, AssignmentEscalationRecipientResult, AssignmentEscalationHistoryRequest, AssignmentEscalationHistoryItem, AssignmentEscalationHistoryResponse, AssignmentCancellationHistoryQuery, AssignmentCancellationHistoryItem, AssignmentCancellationHistoryResponse, AssignmentSelectionSetListQuery, AssignmentSelectionSetItem, AssignmentSelectionSetListResponse, AssignmentSelectionSetCreateRequest, AssignmentCreateRequest, AssignmentUpdateRequest, AssignmentBulkStatusUpdateRequest, AssignmentStatusUpdateRequest, AssignmentWorkerResponseUpdateRequest, AssignmentBulkMutationResponse,
    ProjectListQuery, ProjectListItem, ProjectListResponse, ProjectCreateRequest, ProjectUpdateRequest, ProjectNotesUpdateRequest,
    ShiftSlotListQuery, ShiftSlotListItem, ShiftSlotListResponse, ShiftSlotCreateRequest, ShiftSlotUpdateRequest, ShiftSlotNotesUpdateRequest,
    ExpenseListQuery, ExpenseListItem, ExpenseListResponse, ExpenseSubmissionResponse, ExpenseActionRequest,
    PriceRuleListQuery, PriceRuleListItem, PriceRuleListResponse, PriceRuleCreateRequest, PriceRuleUpdateRequest,
    PriceSalesListQuery, PriceSalesListItem, PriceSalesListResponse, PriceSalesCreateRequest, PriceSalesUpdateRequest,
    PriceOutsourceListQuery, PriceOutsourceListItem, PriceOutsourceListResponse, PriceOutsourceCreateRequest, PriceOutsourceUpdateRequest,
    WorkerListQuery, WorkerListItem, WorkerListResponse, WorkerCreateRequest, WorkerUpdateRequest, WorkerQualsUpdateRequest,
    SupplierListQuery, SupplierListItem, SupplierListResponse, SupplierCreateRequest, SupplierUpdateRequest,
    ClientListQuery, ClientListItem, ClientListResponse, ClientCreateRequest,
    SiteListQuery, SiteListItem, SiteListResponse, SiteCreateRequest,
    ProjectTypeListQuery, ProjectTypeListItem, ProjectTypeListResponse, ProjectTypeCreateRequest, ProjectTypeTreeItem, ProjectTypeTreeResponse,
    RegistrationRequestListQuery, RegistrationRequestListItem, RegistrationRequestListResponse, RegistrationRequestDetailResponse,
    RegistrationDedupeCandidateItem, RegistrationLinkCreateRequest, RegistrationLinkResponse,
    RegistrationRequestApproveRequest, RegistrationRequestRejectRequest, RegistrationRequestFileItem,
    RegistrationFieldDifferenceItem, PublicRegistrationAccessResponse, PublicRegistrationFileUploadResponse, PublicRegistrationSubmitResponse,
    PublicWorkerRegistrationSubmitRequest, PublicSupplierIndividualRegistrationSubmitRequest,
    PublicSupplierCorporationRegistrationSubmitRequest, PublicIntroducerIdentityRegistrationSubmitRequest,
    RoleListQuery, RoleListItem, RoleListResponse, RoleCreateRequest,
    InvoiceListQuery, InvoiceListItem, InvoiceListResponse,
    InvoiceGenerateRequest, InvoiceResponse, InvoiceLineResponse,
    PayoutListQuery, PayoutListItem, PayoutListResponse,
    PayoutGenerateRequest, PayoutResponse, PayoutLineResponse, PayoutDeliveryRequest, PayoutDeliveryItem, PayoutDeliveryListResponse,
    MonthlyBillingGenerateRequest, MonthlyBillingGenerateResponse,
    SoftCloseRequest, HardCloseRequest, SoftCloseReleaseRequest, HardCloseReleaseRequest, ClosingResponse,
    AuditLogSearchRequest, AuditLogResponse, AuditLogListResponse,
    NoticeCreateRequest, NoticeListQuery, NoticeListItem, NoticeListResponse,
    WorkerNoticeItem, WorkerNoticeListResponse, StaffNoticeRespondRequest,
    PushSubscriptionRequest, VapidPublicKeyResponse,
    VanzaiStaffListQuery, VanzaiStaffItem, VanzaiStaffListResponse, VanzaiStaffCreateRequest, VanzaiStaffUpdateRequest,
    ClientStaffListQuery, ClientStaffItem, ClientStaffListResponse, ClientStaffCreateRequest, ClientStaffUpdateRequest,
    WorkerBankAccountItem, WorkerBankAccountListResponse, WorkerBankAccountCreateRequest, WorkerBankAccountUpdateRequest,
    SupplierBankAccountItem, SupplierBankAccountListResponse, SupplierBankAccountCreateRequest, SupplierBankAccountUpdateRequest,
    ErrorResponse
)
from src.models.base import generate_ulid
from src.models.master import User, StaffNotice, StaffNoticeRead, PushSubscription, RegistrationRequest, RegistrationRequestFile, VanzaiStaff, ClientStaff, WorkerBankAccount, SupplierBankAccount, Client

from src.services.csv_import import CsvImportService
from src.services.dashboard import build_assignment_response_monitoring, get_dashboard_summary, get_project_closings_for_period
from src.services import invoice_service
from src.services import payout_service
from src.services.billing_batch import generate_monthly_billing
from src.services import closing
from src.services.audit import AuditService, AuditLogSearchFilter
from src.services import aggregation
from src.services.pdf_generator import PDFGenerator
from src.services.document_storage import DocumentStorage, ObjectStorage, build_invoice_pdf_object_key, build_payout_pdf_object_key, build_receipt_object_key, build_registration_request_file_object_key
from src.services.email_sender import get_default_sender
from src.services.email_template import EmailAttachment, EmailTemplateService
from src.services.scheduler import SchedulerService, initialize_default_jobs
from src.services.auth import AuthorizationError, check_permission, can_access_project, has_permission
from src.services.price_resolver import resolve_outsource_price, resolve_sales_price
from src.services.time_calc import calculate_time
from src.exceptions import VANZAIException
from src.models.enums import ActualStatus, AssignmentStatus, AssignmentWorkerResponseStatus, AuditAction, AvailabilityStatus, ExpenseStatus, ImportMode, ImportScopeType, NoticeTargetType, NoticeType, Permission, UserRole, ClosingStatus


CSV_UPLOAD_MAX_BYTES = 2 * 1024 * 1024
RECEIPT_UPLOAD_MAX_BYTES = 5 * 1024 * 1024
REGISTRATION_FILE_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
PERIOD_KEY_PATTERN = re.compile(r"^\d{6}$")
REGISTRATION_ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
REGISTRATION_ALLOWED_DOCUMENT_TYPES = {
    "driver_license",
    "my_number_card",
    "residence_card",
    "passport",
    "other",
}
REGISTRATION_ALLOWED_DOCUMENT_PARTS = {"front", "back", "single"}


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
# 本番環境は CORS_ALLOW_ORIGINS 環境変数でカンマ区切りドメインを上書きすること
_default_origins = [
    "http://localhost:3000",  # admin-web
    "http://localhost:3001",  # staff-mobile
    "http://localhost:8501",  # Streamlit
]
_cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
_cors_origins = (
    [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
    if _cors_origins_env
    else _default_origins
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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


def _sanitize_receipt_file_name(file_name: str | None) -> str:
    candidate = PurePath((file_name or "").replace("\\", "/")).name.strip()

    if not candidate:
        raise HTTPException(status_code=400, detail="領収書ファイル名は必須です")
    if len(candidate) > 255:
        raise HTTPException(status_code=400, detail="領収書ファイル名が長すぎます")

    return candidate


def _sanitize_registration_file_name(file_name: str | None) -> str:
    candidate = PurePath((file_name or "").replace("\\", "/")).name.strip()

    if not candidate:
        raise HTTPException(status_code=400, detail="ファイル名は必須です")
    if len(candidate) > 255:
        raise HTTPException(status_code=400, detail="ファイル名が長すぎます")

    return candidate


def _parse_optional_time(value: str | None) -> time | None:
    if not value:
        return None
    return time.fromisoformat(value)


def _parse_attendance_time(value: str | None) -> time:
    try:
        return _parse_optional_time(value) or datetime.now().time().replace(microsecond=0)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="action_time は HH:MM[:SS] 形式で指定してください") from exc


def _validate_period_key(period_key: str) -> str:
    if not PERIOD_KEY_PATTERN.fullmatch(period_key):
        raise HTTPException(status_code=400, detail="period_key は YYYYMM 形式で指定してください")
    return period_key


def _validate_csv_file_bytes(file_bytes: bytes) -> None:
    if not file_bytes:
        raise HTTPException(status_code=400, detail="CSVファイルが空です")
    if len(file_bytes) > CSV_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="CSVファイルサイズが上限を超えています")


def _parse_decimal_form_value(value: str, field_name: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} は数値で指定してください") from exc

    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{field_name} は 0 より大きい値で指定してください")

    return parsed


async def _store_receipt_upload(expense_id: str, expense_date: date, upload_file: UploadFile) -> str:
    file_name = _sanitize_receipt_file_name(upload_file.filename)
    file_bytes = await upload_file.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="領収書ファイルが空です")
    if len(file_bytes) > RECEIPT_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="領収書ファイルサイズが上限を超えています")

    object_key = build_receipt_object_key(expense_id, expense_date, file_name)
    storage = ObjectStorage(root=Path(os.getenv("RECEIPT_STORAGE_ROOT", "storage/receipts")))
    return storage.save_bytes(object_key, file_bytes)


def _receipt_storage() -> ObjectStorage:
    return ObjectStorage(root=Path(os.getenv("RECEIPT_STORAGE_ROOT", "storage/receipts")))


def _registration_file_storage() -> ObjectStorage:
    return ObjectStorage(root=Path(os.getenv("REGISTRATION_FILE_STORAGE_ROOT", "storage/registration_files")))


def _validate_availability_status(value: str) -> str:
    legacy_aliases = {
        "available": AvailabilityStatus.AVAILABLE_ALL_DAY.value,
    }
    normalized = legacy_aliases.get(value, value)
    try:
        return AvailabilityStatus(normalized).value
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                "status は available_all_day / available_after_15 / unavailable / consult_required "
                "/ undecided のいずれかで指定してください"
            ),
        ) from exc


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _append_notes(*parts: str | None) -> str | None:
    normalized_parts = [part.strip() for part in parts if part and part.strip()]
    if not normalized_parts:
        return None
    return "\n\n".join(normalized_parts)


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        normalized = _normalize_optional_text(value)
        if normalized:
            return normalized
    return None


REGISTRATION_LINK_MAX_FAILED_ATTEMPTS = 5
PUBLIC_FORM_TYPE_TO_REQUEST_TYPE = {
    "worker": "worker",
    "supplier-individual": "supplier_individual",
    "supplier-corporation": "supplier_corporation",
    "introducer-identity": "introducer_identity",
}
REQUEST_TYPE_TO_PUBLIC_FORM_TYPE = {value: key for key, value in PUBLIC_FORM_TYPE_TO_REQUEST_TYPE.items()}


def _request_type_from_public_form_type(form_type: str) -> str:
    request_type = PUBLIC_FORM_TYPE_TO_REQUEST_TYPE.get(form_type)
    if not request_type:
        raise HTTPException(status_code=404, detail="未対応の公開フォーム種別です")
    return request_type


def _public_form_type_from_request_type(request_type: str) -> str:
    form_type = REQUEST_TYPE_TO_PUBLIC_FORM_TYPE.get(request_type)
    if not form_type:
        raise HTTPException(status_code=400, detail="未対応の request_type です")
    return form_type


def _hash_public_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_registration_link_credentials(expires_in_days: int) -> tuple[str, str, datetime]:
    token = secrets.token_urlsafe(24)
    pin = f"{secrets.randbelow(1000000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    return token, pin, expires_at


def _build_registration_link_response(request_record: RegistrationRequest, token: str, pin: str) -> RegistrationLinkResponse:
    form_type = _public_form_type_from_request_type(request_record.request_type)
    return RegistrationLinkResponse(
        request_id=request_record.id,
        request_type=request_record.request_type,
        status=request_record.status,
        expires_at=request_record.expires_at or datetime.now(timezone.utc),
        public_form_url=f"/public/registrations/{form_type}?token={token}",
        public_token=token,
        access_pin=pin,
        failed_attempts=request_record.failed_attempts,
        locked_at=request_record.locked_at,
        notes=request_record.notes,
    )


def _issue_registration_link(
    request_record: RegistrationRequest,
    *,
    request_type: str,
    expires_in_days: int,
    notes: str | None = None,
) -> tuple[str, str]:
    token, pin, expires_at = _generate_registration_link_credentials(expires_in_days)
    request_record.request_type = request_type
    request_record.status = "link_issued"
    request_record.source_type = "public_form"
    request_record.public_token_hash = _hash_public_token(token)
    request_record.access_pin_hash = get_password_hash(pin)
    request_record.expires_at = expires_at
    request_record.failed_attempts = 0
    request_record.locked_at = None
    request_record.submitted_at = None
    request_record.reviewed_at = None
    request_record.reviewed_by = None
    request_record.approved_target_type = None
    request_record.approved_target_id = None
    request_record.superseded_by_request_id = None
    request_record.dedupe_key = None
    request_record.submitted_ip = None
    request_record.user_agent = None
    request_record.notes = _append_notes(request_record.notes, notes)
    return token, pin


def _registration_detail_record(db: Session, request_record: RegistrationRequest):
    from src.models.master import (
        IntroducerIdentityRequestDetail,
        SupplierCorporationRequestDetail,
        SupplierIndividualRequestDetail,
        WorkerRegistrationRequestDetail,
    )

    model_map = {
        "worker": WorkerRegistrationRequestDetail,
        "supplier_individual": SupplierIndividualRequestDetail,
        "supplier_corporation": SupplierCorporationRequestDetail,
        "introducer_identity": IntroducerIdentityRequestDetail,
    }
    model = model_map.get(request_record.request_type)
    if model is None:
        return None
    return db.query(model).filter(model.request_id == request_record.id).first()


def _registration_detail_data(db: Session, request_record: RegistrationRequest) -> dict | None:
    detail = _registration_detail_record(db, request_record)
    if detail is None:
        return None

    data: dict[str, object | None] = {}
    for column in detail.__table__.columns:
        if column.name in {"id", "request_id", "created_at", "updated_at"}:
            continue
        data[column.name] = getattr(detail, column.name)
    return data


def _registration_summary_name(db: Session, request_record: RegistrationRequest) -> str | None:
    detail_data = _registration_detail_data(db, request_record) or {}
    if request_record.request_type == "worker":
        return _first_non_empty(
            " ".join(
                part for part in [detail_data.get("last_name"), detail_data.get("first_name")] if part
            ),
            detail_data.get("sole_proprietor_name"),
        )
    if request_record.request_type == "supplier_individual":
        return _first_non_empty(detail_data.get("trade_name"), detail_data.get("name"))
    if request_record.request_type == "supplier_corporation":
        return _first_non_empty(detail_data.get("company_name"), detail_data.get("representative_name"))
    if request_record.request_type == "introducer_identity":
        return _first_non_empty(detail_data.get("subject_name"))
    return None


def _registration_file_item(file_record: RegistrationRequestFile) -> RegistrationRequestFileItem:
    return RegistrationRequestFileItem(
        id=file_record.id,
        document_type=file_record.document_type,
        document_part=file_record.document_part,
        original_filename=file_record.original_filename,
        mime_type=file_record.mime_type,
        size_bytes=file_record.size_bytes,
        scan_status=file_record.scan_status,
        uploaded_at=file_record.uploaded_at,
        delete_after=file_record.delete_after,
        deleted_at=file_record.deleted_at,
    )


def _registration_list_item(db: Session, request_record: RegistrationRequest) -> RegistrationRequestListItem:
    return RegistrationRequestListItem(
        id=request_record.id,
        request_type=request_record.request_type,
        status=request_record.status,
        source_type=request_record.source_type,
        summary_name=_registration_summary_name(db, request_record),
        submitted_at=request_record.submitted_at,
        reviewed_at=request_record.reviewed_at,
        reviewed_by=request_record.reviewed_by,
        approved_target_type=request_record.approved_target_type,
        approved_target_id=request_record.approved_target_id,
        expires_at=request_record.expires_at,
        failed_attempts=request_record.failed_attempts,
        locked_at=request_record.locked_at,
        dedupe_key=request_record.dedupe_key,
        notes=request_record.notes,
    )


def _registration_detail_response(db: Session, request_record: RegistrationRequest) -> RegistrationRequestDetailResponse:
    reviewer_name = request_record.reviewer.display_name if request_record.reviewer else None
    if not reviewer_name and request_record.reviewer:
        reviewer_name = request_record.reviewer.username

    return RegistrationRequestDetailResponse(
        id=request_record.id,
        request_type=request_record.request_type,
        status=request_record.status,
        source_type=request_record.source_type,
        summary_name=_registration_summary_name(db, request_record),
        submitted_at=request_record.submitted_at,
        reviewed_at=request_record.reviewed_at,
        reviewed_by=request_record.reviewed_by,
        reviewed_by_name=reviewer_name,
        approved_target_type=request_record.approved_target_type,
        approved_target_id=request_record.approved_target_id,
        expires_at=request_record.expires_at,
        failed_attempts=request_record.failed_attempts,
        locked_at=request_record.locked_at,
        dedupe_key=request_record.dedupe_key,
        superseded_by_request_id=request_record.superseded_by_request_id,
        submitted_ip=request_record.submitted_ip,
        user_agent=request_record.user_agent,
        notes=request_record.notes,
        detail_data=_registration_detail_data(db, request_record),
        dedupe_candidates=_build_registration_dedupe_candidates(db, request_record),
        files=_registration_file_items(db, request_record.id),
    )


def _build_registration_dedupe_candidates(
    db: Session,
    request_record: RegistrationRequest,
) -> list[RegistrationDedupeCandidateItem]:
    from src.models.master import Supplier, Worker

    detail_data = _registration_detail_data(db, request_record) or {}
    candidates: dict[str, RegistrationDedupeCandidateItem] = {}

    def build_field_differences(target_type: str, row) -> list[RegistrationFieldDifferenceItem]:
        field_specs: list[tuple[str, str, str | None, str | None]] = []
        if target_type == "worker":
            request_name = _normalize_optional_text(
                " ".join(part for part in [detail_data.get("last_name"), detail_data.get("first_name")] if part)
            )
            request_furigana = _normalize_optional_text(
                " ".join(part for part in [detail_data.get("last_name_furigana"), detail_data.get("first_name_furigana")] if part)
            )
            field_specs = [
                ("name", "氏名", request_name, _normalize_optional_text(row.name)),
                ("furigana", "ふりがな", request_furigana, _normalize_optional_text(row.furigana)),
                ("phone", "電話番号", _normalize_optional_text(detail_data.get("phone")), _normalize_optional_text(row.phone)),
                ("email", "メール", _normalize_optional_text(detail_data.get("email")), _normalize_optional_text(row.email)),
                (
                    "sole_proprietor_name",
                    "屋号",
                    _normalize_optional_text(detail_data.get("sole_proprietor_name")),
                    _normalize_optional_text(row.sole_proprietor_name),
                ),
                ("gender", "性別", _normalize_optional_text(detail_data.get("gender")), _normalize_optional_text(row.gender)),
                (
                    "invoice_registration_status",
                    "インボイス登録状況",
                    _normalize_optional_text(detail_data.get("invoice_registration_status")),
                    _normalize_optional_text(row.invoice_registration_status),
                ),
                (
                    "invoice_number",
                    "インボイス番号",
                    _normalize_optional_text(detail_data.get("invoice_registration_number")),
                    _normalize_optional_text(row.invoice_number),
                ),
            ]
        elif target_type == "supplier":
            request_name = _first_non_empty(
                detail_data.get("trade_name"),
                detail_data.get("company_name"),
                detail_data.get("name"),
            )
            field_specs = [
                ("name", "名称", _normalize_optional_text(request_name), _normalize_optional_text(row.name)),
                ("phone", "電話番号", _normalize_optional_text(detail_data.get("phone")), _normalize_optional_text(row.contact_phone)),
                ("email", "メール", _normalize_optional_text(detail_data.get("email")), _normalize_optional_text(row.contact_email)),
                (
                    "supplier_type",
                    "supplier_type",
                    _normalize_optional_text(detail_data.get("supplier_type")),
                    _normalize_optional_text(row.supplier_type),
                ),
                (
                    "entity_type",
                    "entity_type",
                    "individual" if request_record.request_type == "supplier_individual" else "corporation" if request_record.request_type == "supplier_corporation" else None,
                    _normalize_optional_text(row.entity_type),
                ),
            ]

        differences: list[RegistrationFieldDifferenceItem] = []
        for field_name, field_label, request_value, existing_value in field_specs:
            if request_value is None and existing_value is None:
                continue
            differences.append(
                RegistrationFieldDifferenceItem(
                    field_name=field_name,
                    field_label=field_label,
                    request_value=request_value,
                    existing_value=existing_value,
                    is_match=(request_value or "") == (existing_value or ""),
                )
            )
        return differences

    def add_candidate(
        *,
        target_type: str,
        target_id: str,
        display_name: str,
        match_reason: str,
        phone: str | None,
        email: str | None,
        entity_type: str | None,
        notes: str | None,
        field_differences: list[RegistrationFieldDifferenceItem],
    ) -> None:
        existing = candidates.get(target_id)
        if existing:
            if match_reason not in existing.match_reasons:
                existing.match_reasons.append(match_reason)
            return
        candidates[target_id] = RegistrationDedupeCandidateItem(
            target_type=target_type,
            target_id=target_id,
            display_name=display_name,
            match_reasons=[match_reason],
            phone=phone,
            email=email,
            entity_type=entity_type,
            notes=notes,
            field_differences=field_differences,
        )

    if request_record.request_type == "worker":
        phone = _normalize_optional_text(detail_data.get("phone"))
        full_name = _normalize_optional_text(
            " ".join(part for part in [detail_data.get("last_name"), detail_data.get("first_name")] if part)
        )
        furigana = _normalize_optional_text(
            " ".join(part for part in [detail_data.get("last_name_furigana"), detail_data.get("first_name_furigana")] if part)
        )
        if phone:
            for row in db.query(Worker).filter(Worker.deleted_at.is_(None), Worker.phone == phone).all():
                add_candidate(
                    target_type="worker",
                    target_id=row.id,
                    display_name=row.name,
                    match_reason="電話番号一致",
                    phone=row.phone,
                    email=row.email,
                    entity_type=None,
                    notes=row.notes,
                    field_differences=build_field_differences("worker", row),
                )
        if full_name and furigana:
            for row in db.query(Worker).filter(
                Worker.deleted_at.is_(None),
                func.lower(Worker.name) == full_name.lower(),
                func.lower(func.coalesce(Worker.furigana, "")) == furigana.lower(),
            ).all():
                add_candidate(
                    target_type="worker",
                    target_id=row.id,
                    display_name=row.name,
                    match_reason="氏名+ふりがな一致",
                    phone=row.phone,
                    email=row.email,
                    entity_type=None,
                    notes=row.notes,
                    field_differences=build_field_differences("worker", row),
                )

    elif request_record.request_type in {"supplier_individual", "supplier_corporation"}:
        phone = _normalize_optional_text(detail_data.get("phone"))
        supplier_name = _first_non_empty(
            detail_data.get("trade_name"),
            detail_data.get("company_name"),
            detail_data.get("name"),
        )
        if phone:
            for row in db.query(Supplier).filter(Supplier.deleted_at.is_(None), Supplier.contact_phone == phone).all():
                add_candidate(
                    target_type="supplier",
                    target_id=row.id,
                    display_name=row.name,
                    match_reason="電話番号一致",
                    phone=row.contact_phone,
                    email=row.contact_email,
                    entity_type=row.entity_type,
                    notes=row.notes,
                    field_differences=build_field_differences("supplier", row),
                )
        if supplier_name:
            for row in db.query(Supplier).filter(
                Supplier.deleted_at.is_(None),
                func.lower(Supplier.name) == supplier_name.lower(),
            ).all():
                add_candidate(
                    target_type="supplier",
                    target_id=row.id,
                    display_name=row.name,
                    match_reason="名称一致",
                    phone=row.contact_phone,
                    email=row.contact_email,
                    entity_type=row.entity_type,
                    notes=row.notes,
                    field_differences=build_field_differences("supplier", row),
                )

    return sorted(candidates.values(), key=lambda item: (item.display_name.lower(), item.target_id))


def _registration_file_items(db: Session, request_id: str) -> list[RegistrationRequestFileItem]:
    files = (
        db.query(RegistrationRequestFile)
        .filter(
            RegistrationRequestFile.request_id == request_id,
            RegistrationRequestFile.deleted_at.is_(None),
        )
        .order_by(RegistrationRequestFile.uploaded_at.desc(), RegistrationRequestFile.id.desc())
        .all()
    )
    return [_registration_file_item(file_record) for file_record in files]


async def _store_registration_request_file(
    *,
    request_record: RegistrationRequest,
    document_type: str,
    document_part: str,
    upload_file: UploadFile,
    db: Session,
) -> RegistrationRequestFile:
    normalized_document_type = _normalize_optional_text(document_type)
    normalized_document_part = _normalize_optional_text(document_part) or "single"
    if normalized_document_type not in REGISTRATION_ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=400, detail="document_type が不正です")
    if normalized_document_part not in REGISTRATION_ALLOWED_DOCUMENT_PARTS:
        raise HTTPException(status_code=400, detail="document_part が不正です")

    file_name = _sanitize_registration_file_name(upload_file.filename)
    file_bytes = await upload_file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="アップロードファイルが空です")
    if len(file_bytes) > REGISTRATION_FILE_UPLOAD_MAX_BYTES:
        raise HTTPException(status_code=400, detail="ファイルサイズが上限を超えています")
    mime_type = (upload_file.content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream").lower()
    if mime_type not in REGISTRATION_ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="許可されていない MIME type です")

    existing_files = (
        db.query(RegistrationRequestFile)
        .filter(
            RegistrationRequestFile.request_id == request_record.id,
            RegistrationRequestFile.document_type == normalized_document_type,
            RegistrationRequestFile.document_part == normalized_document_part,
            RegistrationRequestFile.deleted_at.is_(None),
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for existing in existing_files:
        existing.deleted_at = now

    file_record = RegistrationRequestFile(
        id=generate_ulid(),
        request_id=request_record.id,
        document_type=normalized_document_type,
        document_part=normalized_document_part,
        original_filename=file_name,
        storage_key="pending",
        sha256=hashlib.sha256(file_bytes).hexdigest(),
        mime_type=mime_type,
        size_bytes=len(file_bytes),
        scan_status="pending",
        uploaded_at=now,
        delete_after=None,
    )
    file_record.storage_key = build_registration_request_file_object_key(
        request_record.id,
        file_record.id,
        now.date(),
        file_name,
    )
    _registration_file_storage().save_bytes(file_record.storage_key, file_bytes)
    db.add(file_record)
    db.flush()
    return file_record


def _apply_registration_file_retention(request_record: RegistrationRequest) -> None:
    if request_record.reviewed_at is None:
        return
    delete_after = request_record.reviewed_at + timedelta(days=180)
    for file_record in request_record.files:
        if file_record.deleted_at is None:
            file_record.delete_after = delete_after


def _compute_registration_dedupe_key(request_type: str, detail_data: dict[str, object | None]) -> str | None:
    if request_type == "worker":
        phone = _normalize_optional_text(detail_data.get("phone"))
        if phone:
            return f"worker:phone:{phone}"
        full_name = _normalize_optional_text(
            " ".join(part for part in [detail_data.get("last_name"), detail_data.get("first_name")] if part)
        )
        furigana = _normalize_optional_text(
            " ".join(part for part in [detail_data.get("last_name_furigana"), detail_data.get("first_name_furigana")] if part)
        )
        if full_name and furigana:
            return f"worker:name:{full_name}|furigana:{furigana}"
        return full_name
    if request_type in {"supplier_individual", "supplier_corporation"}:
        supplier_name = _first_non_empty(
            detail_data.get("trade_name"),
            detail_data.get("company_name"),
            detail_data.get("name"),
        )
        phone = _normalize_optional_text(detail_data.get("phone"))
        if supplier_name and phone:
            return f"supplier:name:{supplier_name}|phone:{phone}"
        if supplier_name:
            return f"supplier:name:{supplier_name}"
        if phone:
            return f"supplier:phone:{phone}"
    return None


def _upsert_registration_detail(db: Session, request_record: RegistrationRequest, payload_data: dict[str, object]) -> dict[str, object | None]:
    from src.models.master import (
        IntroducerIdentityRequestDetail,
        SupplierCorporationRequestDetail,
        SupplierIndividualRequestDetail,
        WorkerRegistrationRequestDetail,
    )

    model_map = {
        "worker": WorkerRegistrationRequestDetail,
        "supplier_individual": SupplierIndividualRequestDetail,
        "supplier_corporation": SupplierCorporationRequestDetail,
        "introducer_identity": IntroducerIdentityRequestDetail,
    }
    model = model_map.get(request_record.request_type)
    if model is None:
        raise HTTPException(status_code=400, detail="未対応の request_type です")

    detail = db.query(model).filter(model.request_id == request_record.id).first()
    if detail is None:
        detail = model(request_id=request_record.id)
        db.add(detail)

    sanitized: dict[str, object | None] = {}
    for column in detail.__table__.columns:
        if column.name in {"id", "request_id", "created_at", "updated_at"}:
            continue
        if column.name not in payload_data:
            continue
        value = payload_data[column.name]
        if isinstance(value, str):
            value = _normalize_optional_text(value)
        setattr(detail, column.name, value)
        sanitized[column.name] = value
    return sanitized


def _load_public_registration_request(db: Session, form_type: str, token: str) -> RegistrationRequest:
    request_type = _request_type_from_public_form_type(form_type)
    request_record = (
        db.query(RegistrationRequest)
        .filter(
            RegistrationRequest.deleted_at.is_(None),
            RegistrationRequest.request_type == request_type,
            RegistrationRequest.source_type == "public_form",
            RegistrationRequest.public_token_hash == _hash_public_token(token),
        )
        .first()
    )
    if request_record is None:
        raise HTTPException(status_code=404, detail="公開登録リンクが見つかりません")
    return request_record


def _verify_public_registration_access(request_record: RegistrationRequest, pin: str) -> None:
    now = datetime.now(timezone.utc)
    if request_record.locked_at is not None:
        raise HTTPException(status_code=423, detail="この公開リンクはロックされています")
    if request_record.expires_at and request_record.expires_at < now:
        raise HTTPException(status_code=410, detail="この公開リンクは期限切れです")
    if request_record.status != "link_issued":
        raise HTTPException(status_code=409, detail="この公開リンクは既に使用済みです")
    if not request_record.access_pin_hash or not verify_password(pin, request_record.access_pin_hash):
        request_record.failed_attempts += 1
        if request_record.failed_attempts >= REGISTRATION_LINK_MAX_FAILED_ATTEMPTS:
            request_record.locked_at = now
            raise HTTPException(status_code=423, detail="PIN 失敗回数が上限に達したためリンクをロックしました")
        raise HTTPException(status_code=401, detail="PIN が一致しません")
    request_record.failed_attempts = 0
    request_record.locked_at = None


def _validate_registration_approval_resolution(
    db: Session,
    request_record: RegistrationRequest,
    payload: RegistrationRequestApproveRequest,
) -> None:
    dedupe_candidates = _build_registration_dedupe_candidates(db, request_record)
    if not dedupe_candidates:
        return

    if payload.dedupe_resolution == "merge_existing":
        if not payload.approved_target_id:
            raise HTTPException(status_code=400, detail="merge_existing には approved_target_id が必要です")
        return
    if payload.dedupe_resolution == "create_new":
        if payload.approved_target_id:
            raise HTTPException(status_code=400, detail="create_new では approved_target_id を指定できません")
        return

    raise HTTPException(
        status_code=409,
        detail="重複候補があります。create_new または merge_existing を指定してください",
    )


def _submit_public_registration(
    db: Session,
    *,
    request_record: RegistrationRequest,
    payload_data: dict[str, object],
    submitted_ip: str | None,
    user_agent: str | None,
) -> PublicRegistrationSubmitResponse:
    detail_data = _upsert_registration_detail(db, request_record, payload_data)
    request_record.dedupe_key = _compute_registration_dedupe_key(request_record.request_type, detail_data)
    request_record.status = "pending"
    request_record.submitted_at = datetime.now(timezone.utc)
    request_record.submitted_ip = submitted_ip
    request_record.user_agent = user_agent
    request_record.failed_attempts = 0
    request_record.locked_at = None

    return PublicRegistrationSubmitResponse(
        request_id=request_record.id,
        request_type=request_record.request_type,
        status=request_record.status,
        submitted_at=request_record.submitted_at,
        dedupe_key=request_record.dedupe_key,
    )


def _assert_public_registration_access(db: Session, request_record: RegistrationRequest, pin: str) -> None:
    before_failed_attempts = request_record.failed_attempts
    before_locked_at = request_record.locked_at
    try:
        _verify_public_registration_access(request_record, pin)
    except HTTPException:
        if (
            request_record.failed_attempts != before_failed_attempts
            or request_record.locked_at != before_locked_at
        ):
            db.commit()
        raise


def _resolve_supplier_by_name(db: Session, supplier_name: str | None):
    from src.models.master import Supplier

    normalized_name = _normalize_optional_text(supplier_name)
    if not normalized_name:
        return None
    return (
        db.query(Supplier)
        .filter(Supplier.deleted_at.is_(None), func.lower(Supplier.name) == normalized_name.lower())
        .first()
    )


def _ensure_worker_bank_account(db: Session, worker_id: str, detail_data: dict | None) -> None:
    from src.models.master import WorkerBankAccount

    if not detail_data:
        return

    bank_name = _normalize_optional_text(detail_data.get("bank_name"))
    branch_name = _normalize_optional_text(detail_data.get("bank_branch"))
    account_type = _normalize_optional_text(detail_data.get("bank_account_type"))
    account_number = _normalize_optional_text(detail_data.get("bank_account_number"))
    account_holder = _normalize_optional_text(detail_data.get("bank_account_holder"))
    if not all([bank_name, branch_name, account_type, account_number, account_holder]):
        return

    existing = (
        db.query(WorkerBankAccount)
        .filter(
            WorkerBankAccount.deleted_at.is_(None),
            WorkerBankAccount.worker_id == worker_id,
            WorkerBankAccount.bank_name == bank_name,
            WorkerBankAccount.branch_name == branch_name,
            WorkerBankAccount.account_type == account_type,
            WorkerBankAccount.account_number == account_number,
            WorkerBankAccount.account_holder_kana == account_holder,
        )
        .first()
    )
    if existing:
        return

    has_primary = (
        db.query(WorkerBankAccount)
        .filter(
            WorkerBankAccount.deleted_at.is_(None),
            WorkerBankAccount.worker_id == worker_id,
            WorkerBankAccount.is_primary.is_(True),
        )
        .first()
        is not None
    )
    db.add(
        WorkerBankAccount(
            worker_id=worker_id,
            bank_name=bank_name,
            branch_name=branch_name,
            branch_code=_normalize_optional_text(detail_data.get("bank_branch_number")),
            account_type=account_type,
            account_number=account_number,
            account_holder_kana=account_holder,
            transfer_destination_name=None,
            effective_from=date.today(),
            effective_until=None,
            is_primary=not has_primary,
        )
    )


def _ensure_supplier_bank_account(db: Session, supplier_id: str, detail_data: dict | None) -> None:
    from src.models.master import SupplierBankAccount

    if not detail_data:
        return

    bank_name = _normalize_optional_text(detail_data.get("bank_name"))
    branch_name = _normalize_optional_text(detail_data.get("bank_branch"))
    account_type = _normalize_optional_text(detail_data.get("bank_account_type"))
    account_number = _normalize_optional_text(detail_data.get("bank_account_number"))
    account_holder = _normalize_optional_text(detail_data.get("bank_account_holder_kana"))
    if not all([bank_name, branch_name, account_type, account_number, account_holder]):
        return

    existing = (
        db.query(SupplierBankAccount)
        .filter(
            SupplierBankAccount.deleted_at.is_(None),
            SupplierBankAccount.supplier_id == supplier_id,
            SupplierBankAccount.bank_name == bank_name,
            SupplierBankAccount.branch_name == branch_name,
            SupplierBankAccount.account_type == account_type,
            SupplierBankAccount.account_number == account_number,
            SupplierBankAccount.account_holder_kana == account_holder,
        )
        .first()
    )
    if existing:
        return

    has_primary = (
        db.query(SupplierBankAccount)
        .filter(
            SupplierBankAccount.deleted_at.is_(None),
            SupplierBankAccount.supplier_id == supplier_id,
            SupplierBankAccount.is_primary.is_(True),
        )
        .first()
        is not None
    )
    db.add(
        SupplierBankAccount(
            supplier_id=supplier_id,
            bank_name=bank_name,
            branch_name=branch_name,
            branch_code=_normalize_optional_text(detail_data.get("bank_branch_number")),
            account_type=account_type,
            account_number=account_number,
            account_holder_kana=account_holder,
            transfer_destination_name=None,
            effective_from=date.today(),
            effective_until=None,
            is_primary=not has_primary,
        )
    )


def _approve_registration_request(
    db: Session,
    request_record: RegistrationRequest,
    payload: RegistrationRequestApproveRequest,
):
    from src.models.master import Supplier, Worker

    detail_data = _registration_detail_data(db, request_record) or {}
    target_type: str | None = None
    target_id: str | None = None

    if request_record.request_type == "worker":
        worker = db.get(Worker, payload.approved_target_id) if payload.approved_target_id else None
        if payload.approved_target_id and worker is None:
            raise HTTPException(status_code=404, detail="承認先の worker が見つかりません")
        if worker is None:
            worker_name = _first_non_empty(
                " ".join(
                    part for part in [detail_data.get("last_name"), detail_data.get("first_name")] if part
                ),
                detail_data.get("sole_proprietor_name"),
            )
            if not worker_name:
                raise HTTPException(status_code=400, detail="worker 申請に氏名がありません")
            worker = Worker(name=worker_name, is_active=True)
            db.add(worker)
            db.flush()

        introducer_supplier = _resolve_supplier_by_name(db, detail_data.get("introducer_supplier_name_raw"))
        worker.name = _first_non_empty(
            " ".join(
                part for part in [detail_data.get("last_name"), detail_data.get("first_name")] if part
            ),
            worker.name,
        ) or worker.name
        worker.furigana = _first_non_empty(
            " ".join(
                part for part in [detail_data.get("last_name_furigana"), detail_data.get("first_name_furigana")] if part
            ),
            worker.furigana,
        )
        worker.email = _first_non_empty(detail_data.get("email"), worker.email)
        worker.phone = _first_non_empty(detail_data.get("phone"), worker.phone)
        worker.sole_proprietor_name = _first_non_empty(detail_data.get("sole_proprietor_name"), worker.sole_proprietor_name)
        worker.gender = _first_non_empty(detail_data.get("gender"), worker.gender)
        worker.emergency_contact_name_kana = _first_non_empty(
            detail_data.get("emergency_contact_name_kana"),
            worker.emergency_contact_name_kana,
        )
        worker.emergency_contact_phone = _first_non_empty(
            detail_data.get("emergency_contact_phone"),
            worker.emergency_contact_phone,
        )
        worker.invoice_registration_status = _first_non_empty(
            detail_data.get("invoice_registration_status"),
            worker.invoice_registration_status,
        )
        worker.invoice_number = _first_non_empty(
            detail_data.get("invoice_registration_number"),
            worker.invoice_number,
        )
        worker.introducer_supplier_id = introducer_supplier.id if introducer_supplier else worker.introducer_supplier_id
        worker.notes = _append_notes(worker.notes, detail_data.get("memo"), payload.notes)
        _ensure_worker_bank_account(db, worker.id, detail_data)

        target_type = "worker"
        target_id = worker.id

    elif request_record.request_type == "supplier_individual":
        supplier = db.get(Supplier, payload.approved_target_id) if payload.approved_target_id else None
        if payload.approved_target_id and supplier is None:
            raise HTTPException(status_code=404, detail="承認先の supplier が見つかりません")
        if supplier is None:
            supplier_name = _first_non_empty(detail_data.get("trade_name"), detail_data.get("name"))
            if not supplier_name:
                raise HTTPException(status_code=400, detail="supplier 申請に名称がありません")
            supplier = Supplier(name=supplier_name, payout_terms_days=70, is_active=True)
            db.add(supplier)
            db.flush()

        supplier.name = _first_non_empty(detail_data.get("trade_name"), detail_data.get("name"), supplier.name) or supplier.name
        supplier.contact_email = _first_non_empty(detail_data.get("email"), supplier.contact_email)
        supplier.contact_phone = _first_non_empty(detail_data.get("phone"), supplier.contact_phone)
        supplier.supplier_type = _first_non_empty(detail_data.get("supplier_type"), supplier.supplier_type)
        supplier.entity_type = "individual"
        supplier.notes = _append_notes(supplier.notes, detail_data.get("memo"), payload.notes)
        _ensure_supplier_bank_account(db, supplier.id, detail_data)

        target_type = "supplier"
        target_id = supplier.id

    elif request_record.request_type == "supplier_corporation":
        supplier = db.get(Supplier, payload.approved_target_id) if payload.approved_target_id else None
        if payload.approved_target_id and supplier is None:
            raise HTTPException(status_code=404, detail="承認先の supplier が見つかりません")
        if supplier is None:
            supplier_name = _first_non_empty(detail_data.get("company_name"), detail_data.get("representative_name"))
            if not supplier_name:
                raise HTTPException(status_code=400, detail="supplier 申請に会社名がありません")
            supplier = Supplier(name=supplier_name, payout_terms_days=70, is_active=True)
            db.add(supplier)
            db.flush()

        supplier.name = _first_non_empty(detail_data.get("company_name"), supplier.name) or supplier.name
        supplier.contact_email = _first_non_empty(detail_data.get("email"), supplier.contact_email)
        supplier.contact_phone = _first_non_empty(detail_data.get("phone"), supplier.contact_phone)
        supplier.supplier_type = _first_non_empty(detail_data.get("supplier_type"), supplier.supplier_type)
        supplier.entity_type = "corporation"
        supplier.notes = _append_notes(supplier.notes, detail_data.get("memo"), payload.notes)
        _ensure_supplier_bank_account(db, supplier.id, detail_data)

        target_type = "supplier"
        target_id = supplier.id

    elif request_record.request_type == "introducer_identity":
        detail_record = _registration_detail_record(db, request_record)
        if detail_record and detail_record.related_worker_request_id:
            related_request = db.get(RegistrationRequest, detail_record.related_worker_request_id)
        elif detail_record and detail_record.related_supplier_request_id:
            related_request = db.get(RegistrationRequest, detail_record.related_supplier_request_id)
        else:
            related_request = None

        if related_request and related_request.approved_target_type and related_request.approved_target_id:
            target_type = related_request.approved_target_type
            target_id = related_request.approved_target_id
        else:
            target_type = "registration_request" if related_request else None
            target_id = related_request.id if related_request else payload.approved_target_id
    else:
        raise HTTPException(status_code=400, detail="未対応の request_type です")

    request_record.status = "approved"
    request_record.reviewed_at = datetime.now(timezone.utc)
    request_record.approved_target_type = target_type
    request_record.approved_target_id = target_id
    request_record.notes = _append_notes(request_record.notes, payload.notes)
    _apply_registration_file_retention(request_record)


def _reject_registration_request(request_record: RegistrationRequest, payload: RegistrationRequestRejectRequest) -> None:
    request_record.status = "rejected"
    request_record.reviewed_at = datetime.now(timezone.utc)
    request_record.notes = _append_notes(
        request_record.notes,
        f"却下理由: {payload.reason}",
        payload.notes,
    )
    _apply_registration_file_retention(request_record)


def _serialize_attendance_record(actual, assignment, worker_name: str, role_name: str, import_batch_file_name: str) -> AttendanceRecordResponse:
    return AttendanceRecordResponse(
        actual_id=actual.id,
        assignment_id=assignment.id,
        project_id=assignment.shift_slot.project_id,
        project_name=assignment.shift_slot.project.name,
        worker_id=assignment.worker_id,
        worker_name=worker_name,
        role_id=assignment.role_id,
        role_name=role_name,
        work_date=assignment.shift_slot.work_date,
        start_time=actual.start_time.isoformat() if actual.start_time else None,
        end_time=actual.end_time.isoformat() if actual.end_time else None,
        break_minutes_input=actual.break_minutes_input,
        calc_minutes_billable=actual.calc_minutes_billable,
        status=actual.status,
        import_batch_id=actual.import_batch_id,
        import_batch_file_name=import_batch_file_name,
        notes=actual.notes,
    )


def _serialize_worker_availability_item(entry, worker_name: str) -> WorkerAvailabilityListItem:
    return WorkerAvailabilityListItem(
        id=entry.id,
        worker_id=entry.worker_id,
        worker_name=worker_name,
        availability_date=entry.availability_date,
        status=entry.status,
        notes=entry.notes,
        updated_at=entry.updated_at,
    )


def _serialize_worker_availability_preference(entry) -> WorkerAvailabilityPreferenceResponse:
    return WorkerAvailabilityPreferenceResponse(
        worker_id=entry.worker_id,
        weekly_default_statuses=entry.weekly_default_statuses or {},
        holiday_default_status=entry.holiday_default_status,
        auto_apply_enabled=entry.auto_apply_enabled,
        updated_at=entry.updated_at,
    )


def _validate_weekly_default_statuses(value: dict[str, str]) -> dict[str, str]:
    validated: dict[str, str] = {}
    for key, status_value in value.items():
        if key not in {"0", "1", "2", "3", "4", "5", "6"}:
          raise HTTPException(status_code=400, detail="weekly_default_statuses のキーは 0-6 の曜日文字列で指定してください")
        validated[key] = _validate_availability_status(status_value)
    return validated


def _serialize_expense_list_item(expense, project_name: str, worker_name: str | None) -> ExpenseListItem:
    return ExpenseListItem(
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
        reject_reason=expense.reject_reason,
        has_receipt=bool(expense.receipt_file_key),
    )


def _load_accessible_expense(db: Session, expense_id: str, current_user: User):
    from src.models.transaction import Expense

    expense = db.get(Expense, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")

    if UserRole(current_user.role) == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        if expense.worker_id != current_user.worker_id:
            raise HTTPException(status_code=404, detail="Expense not found")

    return expense


def _create_mobile_import_batch(db: Session, assignment, current_user: User):
    from src.models.transaction import ImportBatch

    period_key = assignment.shift_slot.work_date.strftime("%Y%m")
    batch = ImportBatch(
        id=generate_ulid(),
        submitted_by=current_user.username,
        submit_channel="mobile_attendance",
        file_name=f"mobile_attendance_{assignment.shift_slot.work_date.isoformat()}_{assignment.id}.json",
        file_hash=f"mobile-{generate_ulid()}",
        project_id=assignment.shift_slot.project_id,
        period_key=period_key,
        mode=ImportMode.APPEND.value,
        scope_type=ImportScopeType.PROJECT_DAY_WORKER.value,
        status="completed",
        count_success=1,
        count_error=0,
        count_skip=0,
        count_superseded=0,
        has_row_count_warning=False,
        has_total_time_warning=False,
    )
    db.add(batch)
    db.flush()
    return batch


def _load_accessible_assignment_for_attendance(db: Session, assignment_id: str, current_user: User):
    from src.models.master import Role, Worker
    from src.models.transaction import Assignment, ShiftSlot

    stmt = (
        db.query(Assignment, Worker.name, Role.name)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .join(Worker, Assignment.worker_id == Worker.id)
        .join(Role, Assignment.role_id == Role.id)
        .filter(Assignment.id == assignment_id)
    )

    if UserRole(current_user.role) == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        stmt = stmt.filter(Assignment.worker_id == current_user.worker_id)

    row = stmt.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Assignment not found")

    assignment, worker_name, role_name = row
    if assignment.status == AssignmentStatus.CANCELED.value:
        raise HTTPException(status_code=409, detail="Canceled assignment cannot be used for attendance")

    return assignment, worker_name, role_name


def _load_attendance_actual(db: Session, assignment_id: str):
    from src.models.transaction import Actual, ImportBatch

    return (
        db.query(Actual, ImportBatch.file_name, ImportBatch.submit_channel)
        .join(ImportBatch, Actual.import_batch_id == ImportBatch.id)
        .filter(
            Actual.assignment_id == assignment_id,
            Actual.status == ActualStatus.ACTIVE.value,
        )
        .order_by(Actual.updated_at.desc(), Actual.id.desc())
        .first()
    )


def _calculate_attendance_result(project, start_time: time, end_time: time, break_minutes_input: int | None):
    return calculate_time(
        start_time=start_time,
        end_time=end_time,
        break_minutes_input=break_minutes_input,
        hours_input=None,
        rounding_unit=project.rounding_unit_minutes,
        rounding_method=project.rounding_method,
        break_rule=project.break_deduction_rule,
        time_calc_mode=project.time_calc_mode,
        night_window_start=project.night_window_start,
        night_window_end=project.night_window_end,
    )


def _store_invoice_pdf(invoice) -> str:
    pdf_bytes = PDFGenerator().generate_invoice_pdf(invoice, list(invoice.lines))
    if isinstance(pdf_bytes, str):
        pdf_bytes = Path(pdf_bytes).read_bytes()
    storage = DocumentStorage()
    object_key = invoice.pdf_object_key or build_invoice_pdf_object_key(invoice)
    invoice.pdf_object_key = storage.save_bytes(object_key, pdf_bytes)
    return invoice.pdf_object_key


def _load_invoice_pdf_bytes(invoice) -> bytes:
    if invoice.pdf_object_key:
        storage = DocumentStorage()
        if storage.exists(invoice.pdf_object_key):
            return storage.read_bytes(invoice.pdf_object_key)

    pdf_bytes = PDFGenerator().generate_invoice_pdf(invoice, list(invoice.lines))
    if isinstance(pdf_bytes, str):
        return Path(pdf_bytes).read_bytes()
    return pdf_bytes


def _serialize_invoice_line_response(line) -> InvoiceLineResponse:
    return InvoiceLineResponse(
        line_type=_status_to_str(line.line_type),
        description=line.description,
        quantity=line.quantity_snapshot,
        unit_price=line.unit_price_snapshot,
        amount=line.line_amount,
    )


def _serialize_invoice_response(invoice) -> InvoiceResponse:
    return InvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.id,
        document_type=invoice.document_type,
        client_name=invoice.client.name if invoice.client else "",
        project_name=invoice.project.name if invoice.project else "",
        period_key=invoice.period_key,
        billing_date=invoice.billing_date,
        subject=invoice.invoice_subject,
        addressee_company_name=invoice.addressee_company_name,
        addressee_name=invoice.addressee_name,
        addressee_email=invoice.addressee_email,
        addressee_address=invoice.addressee_address,
        fixed_office_fee_amount=invoice.fixed_office_fee_amount,
        total_amount=invoice.total_amount,
        status=_status_to_str(invoice.status),
        lines=[_serialize_invoice_line_response(line) for line in invoice.lines],
        issued_at=invoice.issued_at,
    )


def _store_payout_pdf(payout) -> str:
    pdf_bytes = PDFGenerator().generate_payout_pdf(payout, list(payout.lines))
    if isinstance(pdf_bytes, str):
        pdf_bytes = Path(pdf_bytes).read_bytes()
    storage = DocumentStorage()
    object_key = payout.pdf_object_key or build_payout_pdf_object_key(payout)
    payout.pdf_object_key = storage.save_bytes(object_key, pdf_bytes)
    return payout.pdf_object_key


def _load_payout_pdf_bytes(payout) -> bytes:
    if payout.pdf_object_key:
        storage = DocumentStorage()
        if storage.exists(payout.pdf_object_key):
            return storage.read_bytes(payout.pdf_object_key)

    pdf_bytes = PDFGenerator().generate_payout_pdf(payout, list(payout.lines))
    if isinstance(pdf_bytes, str):
        return Path(pdf_bytes).read_bytes()
    return pdf_bytes


def _serialize_payout_delivery_item(delivery) -> PayoutDeliveryItem:
    return PayoutDeliveryItem(
        id=delivery.id,
        payout_id=delivery.payout_id,
        recipient_email=delivery.recipient_email,
        status=delivery.status,
        provider=delivery.provider,
        delivered_by=delivery.delivered_by,
        pdf_storage_key=delivery.pdf_object_key_snapshot,
        delivery_note=delivery.delivery_note,
        internal_note=delivery.internal_note,
        error_message=delivery.error_message,
        sent_at=delivery.sent_at,
        created_at=delivery.created_at,
    )


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
    """
    return {
        "username": current_user.username,
        "display_name": current_user.display_name,
        "email": current_user.email,
        "role": getattr(current_user.role, "value", current_user.role),
        "is_active": current_user.is_active
    }


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("新しいパスワードは8文字以上にしてください")
        return v


@app.post("/api/auth/change-password", tags=["Authentication"])
async def change_password(
    payload: "ChangePasswordRequest",
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    パスワード変更（ログイン済みユーザーが自身のパスワードを変更）
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="現在のパスワードが正しくありません")

    db_user = db.query(User).filter(User.id == current_user.id).first()
    db_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()

    return {"message": "パスワードを変更しました"}


class UpdateProfileRequest(BaseModel):
    display_name: Optional[str] = None

    @field_validator("display_name")
    @classmethod
    def display_name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("表示名を空にすることはできません")
        return v.strip() if v else v


@app.put("/api/auth/profile", tags=["Authentication"])
async def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    プロフィール更新（表示名の変更）
    """
    db_user = db.query(User).filter(User.id == current_user.id).first()
    if payload.display_name is not None:
        db_user.display_name = payload.display_name
    db.commit()
    db.refresh(db_user)
    return {
        "username": db_user.username,
        "display_name": db_user.display_name,
        "email": db_user.email,
        "role": getattr(db_user.role, "value", db_user.role),
        "is_active": db_user.is_active,
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

        if summary.missing_payout_recipients:
            unprocessed_items.append(
                UnprocessedItem(
                    item_type="missing_payout_recipient",
                    count=len(summary.missing_payout_recipients),
                    details=[
                        {
                            "payout_id": p.payout_id,
                            "payee_name": p.payee_name,
                            "project_name": p.project_name,
                            "period_key": p.period_key,
                            "status": _status_to_str(p.status),
                            "default_recipient_type": p.default_recipient_type,
                            "reason": p.reason,
                        }
                        for p in summary.missing_payout_recipients
                    ],
                )
            )

        if summary.pending_assignment_responses:
            pending_assignment_response_details = [
                {
                    "assignment_id": item.assignment_id,
                    "project_id": item.project_id,
                    "project_name": item.project_name,
                    "worker_id": item.worker_id,
                    "worker_name": item.worker_name,
                    "worker_email": item.worker_email,
                    "work_date": item.work_date,
                    "shift_label": item.shift_label,
                    "worker_response_requested_at": item.worker_response_requested_at,
                    "hours_since_request": item.hours_since_request,
                    "days_until_work": item.days_until_work,
                    "escalation_level": item.escalation_level,
                    "escalation_reasons": item.escalation_reasons,
                    "reason": item.reason,
                }
                for item in summary.pending_assignment_responses
            ]
            unprocessed_items.append(
                UnprocessedItem(
                    item_type="pending_assignment_response",
                    count=len(summary.pending_assignment_responses),
                    details=pending_assignment_response_details,
                )
            )

            escalated_assignment_response_details = [
                item for item in pending_assignment_response_details if item["escalation_level"] == "escalate"
            ]
            if escalated_assignment_response_details:
                unprocessed_items.append(
                    UnprocessedItem(
                        item_type="escalated_assignment_response",
                        count=len(escalated_assignment_response_details),
                        details=escalated_assignment_response_details,
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


@app.post("/api/assignments/{assignment_id}/check-in", response_model=AttendanceRecordResponse, tags=["Attendance"])
async def check_in_assignment(
    assignment_id: str,
    request: AttendanceActionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサインに対して出勤打刻する"""
    try:
        check_permission(current_user, Permission.ACTUAL_WRITE)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.transaction import Actual

    assignment, worker_name, role_name = _load_accessible_assignment_for_attendance(db, assignment_id, current_user)
    actual_row = _load_attendance_actual(db, assignment_id)
    actual_time = _parse_attendance_time(request.action_time)

    if actual_row is not None:
        actual, import_batch_file_name, submit_channel = actual_row
        if submit_channel != "mobile_attendance":
            raise HTTPException(status_code=409, detail="Attendance already exists from another source")
        actual.start_time = actual_time
        if actual.end_time:
            result = _calculate_attendance_result(
                assignment.shift_slot.project,
                actual.start_time,
                actual.end_time,
                request.break_minutes_input if request.break_minutes_input is not None else actual.break_minutes_input,
            )
            actual.break_minutes_input = request.break_minutes_input if request.break_minutes_input is not None else actual.break_minutes_input
            actual.calc_minutes_total = result.minutes_total
            actual.calc_minutes_break = result.minutes_break
            actual.calc_minutes_billable = result.minutes_billable
            actual.calc_minutes_night = result.minutes_night
            actual.calc_rounding_unit = result.rounding_unit
            actual.calc_rounding_method = result.rounding_method
            actual.calc_break_rule = result.break_rule
            actual.needs_review = result.needs_review
            actual.review_reason = result.review_reason
        if request.notes is not None:
            actual.notes = request.notes
    else:
        batch = _create_mobile_import_batch(db, assignment, current_user)
        price_sales = resolve_sales_price(db, assignment, assignment.shift_slot.work_date) or Decimal("0")
        price_outsource = resolve_outsource_price(db, assignment, assignment.shift_slot.work_date) or Decimal("0")
        actual = Actual(
            id=generate_ulid(),
            project_id=assignment.shift_slot.project_id,
            worker_id=assignment.worker_id,
            role_id=assignment.role_id,
            assignment_id=assignment.id,
            import_batch_id=batch.id,
            work_date=assignment.shift_slot.work_date,
            period_key=assignment.shift_slot.work_date.strftime("%Y%m"),
            status=ActualStatus.ACTIVE.value,
            start_time=actual_time,
            end_time=None,
            break_minutes_input=request.break_minutes_input,
            hours_input=None,
            calc_minutes_total=0,
            calc_minutes_break=0,
            calc_minutes_billable=0,
            calc_minutes_night=0,
            calc_rounding_unit=assignment.shift_slot.project.rounding_unit_minutes,
            calc_rounding_method=assignment.shift_slot.project.rounding_method,
            calc_break_rule=assignment.shift_slot.project.break_deduction_rule,
            applied_price_sales=price_sales,
            applied_price_outsource=price_outsource,
            needs_review=False,
            review_reason=None,
            notes=request.notes,
        )
        db.add(actual)
        import_batch_file_name = batch.file_name

    AuditService(db).log(
        AuditAction.ATTENDANCE_CHECKED_IN,
        target_type="actual",
        target_id=actual.id,
        actor=current_user.username,
        actor_role=current_user.role,
        after_value={
            "assignment_id": assignment.id,
            "work_date": assignment.shift_slot.work_date.isoformat(),
            "start_time": actual.start_time.isoformat() if actual.start_time else None,
        },
    )
    db.commit()
    db.refresh(actual)

    return _serialize_attendance_record(actual, assignment, worker_name, role_name, import_batch_file_name)


@app.post("/api/assignments/{assignment_id}/check-out", response_model=AttendanceRecordResponse, tags=["Attendance"])
async def check_out_assignment(
    assignment_id: str,
    request: AttendanceActionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサインに対して退勤打刻する"""
    try:
        check_permission(current_user, Permission.ACTUAL_WRITE)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    assignment, worker_name, role_name = _load_accessible_assignment_for_attendance(db, assignment_id, current_user)
    actual_row = _load_attendance_actual(db, assignment_id)
    if actual_row is None:
        raise HTTPException(status_code=409, detail="Check-in is required before check-out")

    actual, import_batch_file_name, submit_channel = actual_row
    if submit_channel != "mobile_attendance":
        raise HTTPException(status_code=409, detail="Attendance already exists from another source")
    if actual.start_time is None:
        raise HTTPException(status_code=409, detail="Check-in is required before check-out")

    actual.end_time = _parse_attendance_time(request.action_time)
    result = _calculate_attendance_result(
        assignment.shift_slot.project,
        actual.start_time,
        actual.end_time,
        request.break_minutes_input,
    )
    actual.break_minutes_input = request.break_minutes_input
    actual.calc_minutes_total = result.minutes_total
    actual.calc_minutes_break = result.minutes_break
    actual.calc_minutes_billable = result.minutes_billable
    actual.calc_minutes_night = result.minutes_night
    actual.calc_rounding_unit = result.rounding_unit
    actual.calc_rounding_method = result.rounding_method
    actual.calc_break_rule = result.break_rule
    actual.needs_review = result.needs_review
    actual.review_reason = result.review_reason
    if request.notes is not None:
        actual.notes = request.notes

    AuditService(db).log(
        AuditAction.ATTENDANCE_CHECKED_OUT,
        target_type="actual",
        target_id=actual.id,
        actor=current_user.username,
        actor_role=current_user.role,
        after_value={
            "assignment_id": assignment.id,
            "work_date": assignment.shift_slot.work_date.isoformat(),
            "end_time": actual.end_time.isoformat() if actual.end_time else None,
            "calc_minutes_billable": actual.calc_minutes_billable,
        },
    )
    db.commit()
    db.refresh(actual)

    return _serialize_attendance_record(actual, assignment, worker_name, role_name, import_batch_file_name)


@app.get("/api/worker-availability", response_model=WorkerAvailabilityListResponse, tags=["Worker Availability"])
async def list_worker_availability(
    query: WorkerAvailabilityListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働可否一覧取得"""
    try:
        check_permission(current_user, Permission.AVAILABILITY_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker
    from src.models.transaction import WorkerAvailability

    sort_map = {
        "availability_date": WorkerAvailability.availability_date,
        "status": WorkerAvailability.status,
        "updated_at": WorkerAvailability.updated_at,
        "worker_name": Worker.name,
    }
    sort_column = sort_map.get(query.sort_by or "availability_date", WorkerAvailability.availability_date)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = db.query(WorkerAvailability, Worker.name).join(Worker, WorkerAvailability.worker_id == Worker.id)

    if query.worker_id:
        stmt = stmt.filter(WorkerAvailability.worker_id == query.worker_id)
    if query.availability_date_from:
        stmt = stmt.filter(WorkerAvailability.availability_date >= query.availability_date_from)
    if query.availability_date_to:
        stmt = stmt.filter(WorkerAvailability.availability_date <= query.availability_date_to)
    if query.status:
        stmt = stmt.filter(WorkerAvailability.status == query.status)

    if UserRole(current_user.role) == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        stmt = stmt.filter(WorkerAvailability.worker_id == current_user.worker_id)

    total = stmt.count()
    rows = stmt.order_by(sort_expression, WorkerAvailability.id.desc()).offset(query.offset).limit(query.limit).all()

    return WorkerAvailabilityListResponse(
        items=[_serialize_worker_availability_item(entry, worker_name) for entry, worker_name in rows],
        total=total,
        offset=query.offset,
        limit=query.limit,
    )


@app.post("/api/worker-availability", response_model=WorkerAvailabilityListItem, tags=["Worker Availability"])
async def upsert_worker_availability(
    request: WorkerAvailabilityUpsertRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働可否を登録・更新する"""
    try:
        check_permission(current_user, Permission.AVAILABILITY_WRITE)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker
    from src.models.transaction import WorkerAvailability

    target_worker_id = request.worker_id
    if UserRole(current_user.role) == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        target_worker_id = current_user.worker_id

    if not target_worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")

    worker = db.get(Worker, target_worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    status_value = _validate_availability_status(request.status)
    entry = (
        db.query(WorkerAvailability)
        .filter(
            WorkerAvailability.worker_id == target_worker_id,
            WorkerAvailability.availability_date == request.availability_date,
        )
        .first()
    )

    if entry is None:
        entry = WorkerAvailability(
            id=generate_ulid(),
            worker_id=target_worker_id,
            availability_date=request.availability_date,
            status=status_value,
            notes=request.notes.strip() if request.notes else None,
        )
        db.add(entry)
    else:
        entry.status = status_value
        entry.notes = request.notes.strip() if request.notes else None

    AuditService(db).log(
        AuditAction.AVAILABILITY_UPDATED,
        target_type="worker_availability",
        target_id=entry.id,
        actor=current_user.username,
        actor_role=current_user.role,
        after_value={
            "worker_id": target_worker_id,
            "availability_date": request.availability_date.isoformat(),
            "status": status_value,
            "notes": entry.notes,
        },
    )
    db.commit()
    db.refresh(entry)

    return _serialize_worker_availability_item(entry, worker.name)


@app.get("/api/worker-availability/preferences", response_model=WorkerAvailabilityPreferenceResponse, tags=["Worker Availability"])
async def get_worker_availability_preferences(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者の基本スケジュール設定を取得する"""
    try:
        check_permission(current_user, Permission.AVAILABILITY_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if not current_user.worker_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")

    from src.models.master import WorkerAvailabilityPreference

    entry = db.query(WorkerAvailabilityPreference).filter(WorkerAvailabilityPreference.worker_id == current_user.worker_id).first()
    if entry is None:
        return WorkerAvailabilityPreferenceResponse(worker_id=current_user.worker_id)

    return _serialize_worker_availability_preference(entry)


@app.get("/api/workers/{worker_id}/availability-preferences", response_model=WorkerAvailabilityPreferenceResponse, tags=["Master"])
async def get_worker_availability_preferences_for_admin(
    worker_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """管理画面向けに稼働者の基本スケジュール設定を取得する"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker, WorkerAvailabilityPreference

    worker = db.get(Worker, worker_id)
    if worker is None or worker.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Worker not found")

    entry = db.query(WorkerAvailabilityPreference).filter(WorkerAvailabilityPreference.worker_id == worker_id).first()
    if entry is None:
        return WorkerAvailabilityPreferenceResponse(worker_id=worker_id)

    return _serialize_worker_availability_preference(entry)


@app.put("/api/worker-availability/preferences", response_model=WorkerAvailabilityPreferenceResponse, tags=["Worker Availability"])
async def upsert_worker_availability_preferences(
    request: WorkerAvailabilityPreferenceUpsertRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者の基本スケジュール設定を登録・更新する"""
    try:
        check_permission(current_user, Permission.AVAILABILITY_WRITE)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if not current_user.worker_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")

    from src.models.master import WorkerAvailabilityPreference

    weekly_default_statuses = _validate_weekly_default_statuses(request.weekly_default_statuses)
    holiday_default_status = _validate_availability_status(request.holiday_default_status) if request.holiday_default_status else None

    entry = db.query(WorkerAvailabilityPreference).filter(WorkerAvailabilityPreference.worker_id == current_user.worker_id).first()
    if entry is None:
        entry = WorkerAvailabilityPreference(
            id=generate_ulid(),
            worker_id=current_user.worker_id,
            weekly_default_statuses=weekly_default_statuses,
            holiday_default_status=holiday_default_status,
            auto_apply_enabled=request.auto_apply_enabled,
        )
        db.add(entry)
    else:
        entry.weekly_default_statuses = weekly_default_statuses
        entry.holiday_default_status = holiday_default_status
        entry.auto_apply_enabled = request.auto_apply_enabled

    AuditService(db).log(
        AuditAction.STAFF_AVAILABILITY_PREFERENCES_UPDATED,
        target_type="worker_availability_preferences",
        target_id=entry.id,
        actor=current_user.username,
        actor_role=current_user.role,
        after_value={
            "worker_id": current_user.worker_id,
            "weekly_default_statuses": weekly_default_statuses,
            "holiday_default_status": holiday_default_status,
            "auto_apply_enabled": request.auto_apply_enabled,
        },
    )
    db.commit()
    db.refresh(entry)

    return _serialize_worker_availability_preference(entry)


# ===========================
# 出勤可能日カレンダーエンドポイント
# ===========================

@app.get("/api/availability-calendar", response_model=AvailabilityCalendarResponse, tags=["Worker Availability"])
async def get_availability_calendar(
    date_from: date = Query(..., description="表示開始日"),
    date_to: date = Query(..., description="表示終了日"),
    is_active: bool = Query(True, description="有効スタッフのみ"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """出勤可能日カレンダー（スタッフ×日付マトリクス）を返す"""
    try:
        check_permission(current_user, Permission.AVAILABILITY_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if (date_to - date_from).days > 60:
        raise HTTPException(status_code=400, detail="date range exceeds 60 days")

    from datetime import timedelta
    from src.models.master import Worker, Role
    from src.models.transaction import Assignment, ShiftSlot, WorkerAvailability
    from src.models.transaction import Project

    # 稼働者一覧
    workers_q = db.query(Worker).filter(Worker.deleted_at.is_(None))
    if is_active:
        workers_q = workers_q.filter(Worker.is_active == True)  # noqa: E712
    workers = workers_q.order_by(Worker.name).all()

    if not workers:
        return AvailabilityCalendarResponse(date_from=date_from, date_to=date_to, workers=[])

    worker_ids = [w.id for w in workers]

    # 出勤可否レコード（まとめて取得）
    avail_rows = (
        db.query(WorkerAvailability)
        .filter(
            WorkerAvailability.worker_id.in_(worker_ids),
            WorkerAvailability.availability_date >= date_from,
            WorkerAvailability.availability_date <= date_to,
        )
        .all()
    )
    avail_map: dict[str, dict[str, WorkerAvailability]] = {}
    for row in avail_rows:
        avail_map.setdefault(row.worker_id, {})[row.availability_date.isoformat()] = row

    # 配置一覧（まとめて取得）- project_id を ShiftSlot から取得
    assign_rows = (
        db.query(
            Assignment,
            Project.id.label("proj_id"),
            Project.name.label("proj_name"),
            ShiftSlot.work_date,
            ShiftSlot.shift_label,
            Role.name.label("role_name"),
        )
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .join(Project, ShiftSlot.project_id == Project.id)
        .join(Role, Assignment.role_id == Role.id)
        .filter(
            Assignment.worker_id.in_(worker_ids),
            ShiftSlot.work_date >= date_from,
            ShiftSlot.work_date <= date_to,
            Assignment.status != "canceled",
        )
        .all()
    )
    assign_map: dict[str, dict[str, list[CalendarDayAssignment]]] = {}
    for asgn, proj_id, proj_name, work_date, shift_label, role_name in assign_rows:
        date_str = work_date.isoformat()
        assign_map.setdefault(asgn.worker_id, {}).setdefault(date_str, []).append(
            CalendarDayAssignment(
                id=asgn.id,
                project_id=proj_id,
                project_name=proj_name,
                shift_slot_id=asgn.shift_slot_id,
                shift_label=shift_label,
                status=asgn.status,
                role_name=role_name,
            )
        )

    # 組み立て
    worker_rows = []
    for w in workers:
        days: dict[str, CalendarDayInfo] = {}
        av = avail_map.get(w.id, {})
        am = assign_map.get(w.id, {})
        cur = date_from
        while cur <= date_to:
            ds = cur.isoformat()
            av_rec = av.get(ds)
            days[ds] = CalendarDayInfo(
                availability_status=av_rec.status if av_rec else None,
                availability_notes=av_rec.notes if av_rec else None,
                assignments=am.get(ds, []),
            )
            cur += timedelta(days=1)

        worker_rows.append(
            CalendarWorkerRow(
                id=w.id,
                name=w.name,
                is_active=w.is_active,
                smoking_area_ok=w.smoking_area_ok,
                has_p_shirt=w.has_p_shirt,
                has_best=w.has_best,
                stores_training_done=w.stores_training_done,
                pioneer_training_done=w.pioneer_training_done,
                p_shirt_count=w.p_shirt_count,
                license_type=w.license_type,
                days=days,
            )
        )

    return AvailabilityCalendarResponse(date_from=date_from, date_to=date_to, workers=worker_rows)


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
    from src.services.dashboard import build_assignment_response_monitoring

    sort_map = {
        "work_date": ShiftSlot.work_date,
        "worker_name": Worker.name,
        "project_name": Project.name,
        "status": Assignment.status,
    }
    sort_column = sort_map.get(query.sort_by or "work_date", ShiftSlot.work_date)
    sort_expression = sort_column.asc() if query.sort_order == "asc" else sort_column.desc()

    stmt = (
        db.query(Assignment, Project.name, ShiftSlot.work_date, ShiftSlot.shift_label, Worker.name, Worker.email, Role.name)
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
    if query.response_status:
        stmt = stmt.filter(Assignment.worker_response_status == query.response_status)
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

    apply_monitoring_filters = bool(query.monitoring_status or query.missing_email_only)
    total = stmt.count()
    ordered_stmt = stmt.order_by(sort_expression, Assignment.id.desc())
    rows = ordered_stmt.all() if apply_monitoring_filters else ordered_stmt.offset(query.offset).limit(query.limit).all()

    filtered_items: list[AssignmentListItem] = []
    for assignment, project_name, work_date, shift_label, worker_name, worker_email, role_name in rows:
        monitoring_status = None
        monitoring_reasons: list[str] = []
        hours_since_response_request = None
        days_until_work = None

        if assignment.worker_response_status == AssignmentWorkerResponseStatus.PENDING.value:
            monitoring = build_assignment_response_monitoring(
                work_date=work_date,
                worker_email=worker_email,
                worker_response_requested_at=assignment.worker_response_requested_at,
            )
            monitoring_status = monitoring.escalation_level
            monitoring_reasons = monitoring.escalation_reasons
            hours_since_response_request = monitoring.hours_since_request
            days_until_work = monitoring.days_until_work

        if query.monitoring_status and monitoring_status != query.monitoring_status:
            continue
        if query.missing_email_only and worker_email and worker_email.strip():
            continue

        filtered_items.append(
            AssignmentListItem(
                id=assignment.id,
                shift_slot_id=assignment.shift_slot_id,
                project_id=assignment.shift_slot.project_id,
                project_name=project_name,
                work_date=work_date,
                shift_label=shift_label,
                worker_id=assignment.worker_id,
                worker_name=worker_name,
                worker_email=worker_email,
                role_id=assignment.role_id,
                role_name=role_name,
                status=assignment.status,
                cancel_reason=assignment.cancel_reason,
                worker_response_status=assignment.worker_response_status,
                worker_response_requested_at=assignment.worker_response_requested_at,
                worker_response_at=assignment.worker_response_at,
                worker_response_note=assignment.worker_response_note,
                monitoring_status=monitoring_status,
                monitoring_reasons=monitoring_reasons,
                hours_since_response_request=hours_since_response_request,
                days_until_work=days_until_work,
                locked_price_sales=assignment.locked_price_sales,
                locked_price_outsource=assignment.locked_price_outsource,
            )
        )

    if apply_monitoring_filters:
        total = len(filtered_items)
        filtered_items = filtered_items[query.offset: query.offset + query.limit]

    return AssignmentListResponse(items=filtered_items, total=total, offset=query.offset, limit=query.limit)


def _to_period_key_from_date(value: date) -> str:
    return f"{value.year}{value.month:02d}"


def _load_accessible_assignment_selection_rows(db: Session, current_user: User, assignment_ids: list[str]):
    from src.models.transaction import Assignment, Project, ShiftSlot

    if not assignment_ids:
        return []

    stmt = (
        db.query(
            Assignment.id,
            ShiftSlot.work_date,
            Project.id.label("project_id"),
            Project.name.label("project_name"),
        )
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .join(Project, ShiftSlot.project_id == Project.id)
        .filter(Assignment.id.in_(assignment_ids))
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
    elif role == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        stmt = stmt.filter(Assignment.worker_id == current_user.worker_id)

    return stmt.all()


@app.get("/api/assignments/selection-sets", response_model=AssignmentSelectionSetListResponse, tags=["Assignments"])
async def list_assignment_selection_sets(
    query: AssignmentSelectionSetListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン選択セット一覧取得"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.transaction import AssignmentSelectionSet

    rows = (
        db.query(AssignmentSelectionSet, User.username)
        .join(User, AssignmentSelectionSet.created_by_user_id == User.id)
        .filter(
            AssignmentSelectionSet.deleted_at.is_(None),
            AssignmentSelectionSet.period_key == query.period_key,
            or_(
                AssignmentSelectionSet.created_by_user_id == current_user.id,
                AssignmentSelectionSet.is_shared.is_(True),
            ),
        )
        .order_by(AssignmentSelectionSet.is_shared.desc(), AssignmentSelectionSet.created_at.desc())
        .all()
    )

    all_assignment_ids: list[str] = []
    for selection_set, _ in rows:
        all_assignment_ids.extend(selection_set.assignment_ids or [])
    visible_assignment_ids = {
        row.id for row in _load_accessible_assignment_selection_rows(db, current_user, list(dict.fromkeys(all_assignment_ids)))
    }

    items: list[AssignmentSelectionSetItem] = []
    for selection_set, creator_name in rows:
        assignment_ids = [assignment_id for assignment_id in (selection_set.assignment_ids or []) if assignment_id in visible_assignment_ids]
        if not assignment_ids:
            continue
        items.append(
            AssignmentSelectionSetItem(
                id=selection_set.id,
                name=selection_set.name,
                period_key=selection_set.period_key,
                assignment_ids=assignment_ids,
                total_assignment_count=len(selection_set.assignment_ids or []),
                available_assignment_count=len(assignment_ids),
                is_shared=selection_set.is_shared,
                created_at=selection_set.created_at,
                created_by=creator_name,
                editable=selection_set.created_by_user_id == current_user.id or current_user.role == UserRole.ADMIN.value,
            )
        )

    return AssignmentSelectionSetListResponse(items=items)


@app.post("/api/assignments/selection-sets", response_model=AssignmentSelectionSetItem, tags=["Assignments"])
async def create_assignment_selection_set(
    request: AssignmentSelectionSetCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン選択セット作成"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if request.is_shared and not has_permission(current_user, Permission.ASSIGNMENT_WRITE):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="共有選択セットの保存権限がありません")

    from src.models.transaction import AssignmentSelectionSet

    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="選択セット名は必須です")

    assignment_ids = list(dict.fromkeys(request.assignment_ids))
    rows = _load_accessible_assignment_selection_rows(db, current_user, assignment_ids)
    if len(rows) != len(assignment_ids):
        raise HTTPException(status_code=400, detail="対象アサインにアクセスできない、または存在しないIDが含まれています")

    for row in rows:
        if _to_period_key_from_date(row.work_date) != request.period_key:
            raise HTTPException(status_code=400, detail="選択セットには対象月以外のアサインを含められません")

    selection_set = AssignmentSelectionSet(
        name=name,
        period_key=request.period_key,
        created_by_user_id=current_user.id,
        is_shared=request.is_shared,
        assignment_ids=assignment_ids,
    )
    db.add(selection_set)
    db.flush()

    AuditService(db).log(
        AuditAction.ASSIGNMENT_SELECTION_SET_SAVED,
        target_type="assignment_selection_set",
        target_id=selection_set.id,
        actor=current_user.username,
        actor_role=current_user.role,
        after_value={
            "name": name,
            "period_key": request.period_key,
            "assignment_count": len(assignment_ids),
            "is_shared": request.is_shared,
        },
        extra_metadata={
            "assignment_ids": assignment_ids,
        },
    )

    db.commit()

    return AssignmentSelectionSetItem(
        id=selection_set.id,
        name=selection_set.name,
        period_key=selection_set.period_key,
        assignment_ids=assignment_ids,
        total_assignment_count=len(assignment_ids),
        available_assignment_count=len(assignment_ids),
        is_shared=selection_set.is_shared,
        created_at=selection_set.created_at,
        created_by=current_user.username,
        editable=True,
    )


@app.delete("/api/assignments/selection-sets/{selection_set_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Assignments"])
async def delete_assignment_selection_set(
    selection_set_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン選択セット削除"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.transaction import AssignmentSelectionSet

    selection_set = db.get(AssignmentSelectionSet, selection_set_id)
    if not selection_set or selection_set.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Selection set not found")

    if selection_set.created_by_user_id != current_user.id and current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="選択セットを削除する権限がありません")

    selection_set.deleted_at = datetime.now(timezone.utc)
    AuditService(db).log(
        AuditAction.ASSIGNMENT_SELECTION_SET_DELETED,
        target_type="assignment_selection_set",
        target_id=selection_set.id,
        actor=current_user.username,
        actor_role=current_user.role,
        before_value={
            "name": selection_set.name,
            "period_key": selection_set.period_key,
            "assignment_count": len(selection_set.assignment_ids or []),
            "is_shared": selection_set.is_shared,
        },
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _load_accessible_assignments_by_ids(db: Session, current_user: User, assignment_ids: list[str]):
    from src.models.transaction import Assignment, Project, ShiftSlot

    if not assignment_ids:
        return []

    stmt = (
        db.query(Assignment)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .join(Project, ShiftSlot.project_id == Project.id)
        .filter(Assignment.id.in_(assignment_ids))
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
    elif role == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        stmt = stmt.filter(Assignment.worker_id == current_user.worker_id)

    return stmt.all()


def _build_assignment_monitoring_snapshot(assignment) -> dict[str, object]:
    monitoring = build_assignment_response_monitoring(
        work_date=assignment.shift_slot.work_date,
        worker_email=assignment.worker.email,
        worker_response_requested_at=assignment.worker_response_requested_at,
    )
    return {
        "assignment_id": assignment.id,
        "project_id": assignment.shift_slot.project.id,
        "project_name": assignment.shift_slot.project.name,
        "worker_id": assignment.worker_id,
        "worker_name": assignment.worker.name,
        "worker_email": monitoring.worker_email,
        "work_date": assignment.shift_slot.work_date,
        "shift_label": assignment.shift_slot.shift_label,
        "reason": monitoring.reason,
        "monitoring_status": monitoring.escalation_level,
        "monitoring_reasons": monitoring.escalation_reasons,
    }


def _resolve_assignment_escalation_recipients(db: Session) -> list[tuple[str, str]]:
    override = os.getenv("ASSIGNMENT_RESPONSE_ESCALATION_EMAILS", "").strip()
    if override:
        recipients: list[tuple[str, str]] = []
        for raw_email in override.split(","):
            email = raw_email.strip()
            if not email:
                continue
            recipients.append((email.split("@")[0], email))
        return recipients

    rows = (
        db.query(User.username, User.email)
        .filter(
            User.deleted_at.is_(None),
            User.is_active.is_(True),
            User.role.in_([
                UserRole.ADMIN.value,
                UserRole.OPS.value,
                UserRole.ACCOUNTING.value,
            ]),
        )
        .order_by(User.role.asc(), User.username.asc())
        .all()
    )
    seen: set[str] = set()
    recipients: list[tuple[str, str]] = []
    for username, email in rows:
        if not email or email in seen:
            continue
        seen.add(email)
        recipients.append((username, email))
    return recipients


@app.post("/api/assignments/reminders/send", response_model=AssignmentReminderSendResponse, tags=["Assignments"])
async def send_assignment_response_reminders(
    request: AssignmentReminderSendRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """選択した未回答アサインに予定確認催促を送信"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)

        assignment_ids = list(dict.fromkeys(request.assignment_ids))
        if not assignment_ids:
            raise HTTPException(status_code=400, detail="assignment_ids is required")

        assignments = _load_accessible_assignments_by_ids(db, current_user, assignment_ids)
        if len(assignments) != len(assignment_ids):
            raise HTTPException(status_code=400, detail="対象アサインにアクセスできない、または存在しないIDが含まれています")

        scheduler_service = SchedulerService()
        try:
            dispatch_result = scheduler_service.send_assignment_response_reminders(
                db,
                actor=current_user.username,
                actor_role=current_user.role,
                assignment_ids=assignment_ids,
                dry_run=request.dry_run,
            )
            db.commit()
        finally:
            scheduler_service.shutdown()

        return AssignmentReminderSendResponse(
            requested_assignment_count=len(assignment_ids),
            eligible_assignment_count=dispatch_result.eligible_assignment_count,
            recipient_count=dispatch_result.recipient_count,
            sent_count=dispatch_result.sent_count,
            failed_count=dispatch_result.failed_count,
            skipped_missing_email_count=dispatch_result.skipped_missing_email_count,
            dry_run=dispatch_result.dry_run,
            worker_results=[
                AssignmentReminderSendWorkerResult(
                    worker_id=result.worker_id,
                    worker_name=result.worker_name,
                    worker_email=result.worker_email,
                    assignment_ids=result.assignment_ids,
                    assignment_count=result.assignment_count,
                    status=result.status,
                )
                for result in dispatch_result.worker_results
            ],
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="予定確認催促の送信に失敗しました")


@app.post("/api/assignments/reminders/history", response_model=AssignmentReminderHistoryResponse, tags=["Assignments"])
async def get_assignment_response_reminder_history(
    request: AssignmentReminderHistoryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """選択したアサインに紐づく予定確認催促履歴を返す"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)
        from src.models.transaction import AuditLog

        assignment_ids = list(dict.fromkeys(request.assignment_ids))
        assignments = _load_accessible_assignments_by_ids(db, current_user, assignment_ids)
        if len(assignments) != len(assignment_ids):
            raise HTTPException(status_code=400, detail="対象アサインにアクセスできない、または存在しないIDが含まれています")

        assignment_map = {assignment.id: assignment for assignment in assignments}
        logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.action.in_(
                    [
                        AuditAction.ASSIGNMENT_RESPONSE_REMINDER_SENT.value,
                        AuditAction.ASSIGNMENT_RESPONSE_REMINDER_FAILED.value,
                    ]
                ),
                AuditLog.target_type.in_(["assignment", "assignments"]),
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(200)
            .all()
        )

        items: list[AssignmentReminderHistoryItem] = []
        for log in logs:
            logged_assignment_ids = [
                assignment_id
                for assignment_id in ((log.extra_metadata or {}).get("assignment_ids") or [])
                if assignment_id in assignment_map
            ]
            if not logged_assignment_ids:
                continue

            worker_id = (log.after_value or {}).get("worker_id") if isinstance(log.after_value, dict) else None
            assignment = assignment_map.get(logged_assignment_ids[0])
            worker_name = assignment.worker.name if assignment else worker_id or "-"
            worker_email = (log.after_value or {}).get("worker_email") if isinstance(log.after_value, dict) else None
            items.append(
                AssignmentReminderHistoryItem(
                    audit_log_id=log.id,
                    created_at=log.created_at,
                    actor=log.actor,
                    actor_role=log.actor_role,
                    worker_id=worker_id,
                    worker_name=worker_name,
                    worker_email=worker_email,
                    status="sent" if log.action == AuditAction.ASSIGNMENT_RESPONSE_REMINDER_SENT.value else "failed",
                    dry_run=bool((log.after_value or {}).get("dry_run")) if isinstance(log.after_value, dict) else False,
                    assignment_ids=logged_assignment_ids,
                    assignment_count=len(logged_assignment_ids),
                )
            )
            if len(items) >= request.limit:
                break

        return AssignmentReminderHistoryResponse(items=items)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="予定確認催促履歴の取得に失敗しました")


@app.post("/api/assignments/reminders/escalate", response_model=AssignmentEscalationSendResponse, tags=["Assignments"])
async def send_assignment_response_escalation(
    request: AssignmentEscalationSendRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """選択した要エスカレーション assignment を管理者へ通知する"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)

        assignment_ids = list(dict.fromkeys(request.assignment_ids))
        assignments = _load_accessible_assignments_by_ids(db, current_user, assignment_ids)
        if len(assignments) != len(assignment_ids):
            raise HTTPException(status_code=400, detail="対象アサインにアクセスできない、または存在しないIDが含まれています")

        escalated_items = []
        for assignment in assignments:
            if assignment.status == AssignmentStatus.CANCELED.value:
                continue
            if assignment.worker_response_status != AssignmentWorkerResponseStatus.PENDING.value:
                continue
            snapshot = _build_assignment_monitoring_snapshot(assignment)
            if snapshot["monitoring_status"] != "escalate":
                continue
            escalated_items.append(snapshot)

        dry_run = request.dry_run if request.dry_run is not None else os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
        recipients = _resolve_assignment_escalation_recipients(db)
        if not recipients:
            raise HTTPException(status_code=400, detail="エスカレーション通知先が設定されていません")

        if not escalated_items:
            return AssignmentEscalationSendResponse(
                requested_assignment_count=len(assignment_ids),
                eligible_assignment_count=0,
                recipient_count=len(recipients),
                sent_count=0,
                failed_count=0,
                dry_run=dry_run,
                recipient_results=[],
            )

        period_start = min(item["work_date"] for item in escalated_items)
        period_end = max(item["work_date"] for item in escalated_items)
        sender = get_default_sender(provider=os.getenv("EMAIL_PROVIDER", "gmail"))
        template_service = EmailTemplateService()
        sent_count = 0
        failed_count = 0
        recipient_results: list[AssignmentEscalationRecipientResult] = []

        for recipient_name, recipient_email in recipients:
            template = template_service.assignment_response_escalation_summary(
                admin_name=recipient_name,
                admin_email=recipient_email,
                period_start=period_start,
                period_end=period_end,
                escalated_assignments=escalated_items,
            )
            sent = sender.send_email(template, dry_run=dry_run)
            if sent:
                sent_count += 1
            else:
                failed_count += 1

            AuditService(db).log(
                AuditAction.ASSIGNMENT_RESPONSE_ESCALATION_SENT if sent else AuditAction.ASSIGNMENT_RESPONSE_ESCALATION_FAILED,
                target_type="assignment",
                actor=current_user.username,
                actor_role=current_user.role,
                after_value={
                    "recipient_email": recipient_email,
                    "recipient_name": recipient_name,
                    "assignment_count": len(escalated_items),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                    "dry_run": dry_run,
                },
                extra_metadata={
                    "assignment_ids": [str(item["assignment_id"]) for item in escalated_items],
                },
            )

            recipient_results.append(
                AssignmentEscalationRecipientResult(
                    recipient_email=recipient_email,
                    recipient_name=recipient_name,
                    escalated_assignment_count=len(escalated_items),
                    status="sent" if sent else "failed",
                )
            )

        db.commit()
        return AssignmentEscalationSendResponse(
            requested_assignment_count=len(assignment_ids),
            eligible_assignment_count=len(escalated_items),
            recipient_count=len(recipients),
            sent_count=sent_count,
            failed_count=failed_count,
            dry_run=dry_run,
            recipient_results=recipient_results,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="予定確認エスカレーション通知の送信に失敗しました")


@app.post("/api/assignments/reminders/escalations/history", response_model=AssignmentEscalationHistoryResponse, tags=["Assignments"])
async def get_assignment_response_escalation_history(
    request: AssignmentEscalationHistoryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """選択したアサインに紐づく予定確認エスカレーション履歴を返す"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)
        from src.models.transaction import AuditLog

        assignment_ids = list(dict.fromkeys(request.assignment_ids))
        assignments = _load_accessible_assignments_by_ids(db, current_user, assignment_ids)
        if len(assignments) != len(assignment_ids):
            raise HTTPException(status_code=400, detail="対象アサインにアクセスできない、または存在しないIDが含まれています")

        assignment_map = {assignment.id: assignment for assignment in assignments}
        logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.action.in_(
                    [
                        AuditAction.ASSIGNMENT_RESPONSE_ESCALATION_SENT.value,
                        AuditAction.ASSIGNMENT_RESPONSE_ESCALATION_FAILED.value,
                    ]
                ),
                AuditLog.target_type.in_(["assignment", "assignments"]),
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(200)
            .all()
        )

        items: list[AssignmentEscalationHistoryItem] = []
        for log in logs:
            logged_assignment_ids = [
                assignment_id
                for assignment_id in ((log.extra_metadata or {}).get("assignment_ids") or [])
                if assignment_id in assignment_map
            ]
            if not logged_assignment_ids:
                continue

            after_value = log.after_value if isinstance(log.after_value, dict) else {}
            items.append(
                AssignmentEscalationHistoryItem(
                    audit_log_id=log.id,
                    created_at=log.created_at,
                    actor=log.actor,
                    actor_role=log.actor_role,
                    recipient_name=str(after_value.get("recipient_name") or "-"),
                    recipient_email=str(after_value.get("recipient_email") or "-"),
                    status="sent" if log.action == AuditAction.ASSIGNMENT_RESPONSE_ESCALATION_SENT.value else "failed",
                    dry_run=bool(after_value.get("dry_run")),
                    assignment_ids=logged_assignment_ids,
                    assignment_count=len(logged_assignment_ids),
                )
            )
            if len(items) >= request.limit:
                break

        return AssignmentEscalationHistoryResponse(items=items)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="予定確認エスカレーション履歴の取得に失敗しました")


@app.get("/api/assignments/cancellation-history", response_model=AssignmentCancellationHistoryResponse, tags=["Assignments"])
async def list_assignment_cancellation_history(
    query: AssignmentCancellationHistoryQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン取消履歴取得"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Role, Worker
    from src.models.transaction import Assignment, AuditLog, Project, ShiftSlot

    sort_expression = AuditLog.created_at.asc() if query.sort_order == "asc" else AuditLog.created_at.desc()

    stmt = (
        db.query(AuditLog, Assignment, Project.name, ShiftSlot.work_date, ShiftSlot.shift_label, Worker.name, Role.name)
        .join(Assignment, AuditLog.target_id == Assignment.id)
        .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
        .join(Project, ShiftSlot.project_id == Project.id)
        .join(Worker, Assignment.worker_id == Worker.id)
        .join(Role, Assignment.role_id == Role.id)
        .filter(
            AuditLog.action == AuditAction.ASSIGNMENT_CANCELED.value,
            AuditLog.target_type.in_(["assignment", "assignments"]),
        )
    )

    if query.project_id:
        stmt = stmt.filter(Project.id == query.project_id)
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
    rows = stmt.order_by(sort_expression, AuditLog.id.desc()).offset(query.offset).limit(query.limit).all()

    assignment_ids = [assignment.id for _, assignment, *_ in rows]
    reopen_logs_by_assignment: dict[str, list] = {}
    if assignment_ids:
        reopen_logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == AuditAction.ASSIGNMENT_STATUS_CHANGED.value,
                AuditLog.target_type.in_(["assignment", "assignments"]),
                AuditLog.target_id.in_(assignment_ids),
            )
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
            .all()
        )
        for reopen_log in reopen_logs:
            before_status = (reopen_log.before_value or {}).get("status")
            after_status = (reopen_log.after_value or {}).get("status")
            if before_status != "canceled" or after_status == "canceled":
                continue
            reopen_logs_by_assignment.setdefault(reopen_log.target_id, []).append(reopen_log)

    items = []
    for audit_log, assignment, project_name, work_date, shift_label, worker_name, role_name in rows:
        matched_reopen_log = None
        for reopen_log in reopen_logs_by_assignment.get(assignment.id, []):
            if reopen_log.created_at > audit_log.created_at:
                matched_reopen_log = reopen_log
                break

        items.append(
            AssignmentCancellationHistoryItem(
                audit_log_id=audit_log.id,
                assignment_id=assignment.id,
                project_id=assignment.shift_slot.project_id,
                project_name=project_name,
                work_date=work_date,
                shift_label=shift_label,
                worker_id=assignment.worker_id,
                worker_name=worker_name,
                role_id=assignment.role_id,
                role_name=role_name,
                canceled_at=audit_log.created_at,
                canceled_by=audit_log.actor,
                cancel_reason=audit_log.reason,
                reopened_at=matched_reopen_log.created_at if matched_reopen_log else None,
                reopened_by=matched_reopen_log.actor if matched_reopen_log else None,
                reopen_reason=matched_reopen_log.reason if matched_reopen_log else None,
                current_status=assignment.status,
            )
        )

    return AssignmentCancellationHistoryResponse(
        items=items,
        total=total,
        offset=query.offset,
        limit=query.limit,
    )


def _serialize_assignment_item(assignment) -> AssignmentListItem:
    return AssignmentListItem(
        id=assignment.id,
        shift_slot_id=assignment.shift_slot_id,
        project_id=assignment.shift_slot.project_id,
        project_name=assignment.shift_slot.project.name,
        work_date=assignment.shift_slot.work_date,
        shift_label=assignment.shift_slot.shift_label,
        worker_id=assignment.worker_id,
        worker_name=assignment.worker.name,
        role_id=assignment.role_id,
        role_name=assignment.role.name,
        status=assignment.status,
        cancel_reason=assignment.cancel_reason,
        worker_response_status=assignment.worker_response_status,
        worker_response_requested_at=assignment.worker_response_requested_at,
        worker_response_at=assignment.worker_response_at,
        worker_response_note=assignment.worker_response_note,
        locked_price_sales=assignment.locked_price_sales,
        locked_price_outsource=assignment.locked_price_outsource,
    )


def _activate_assignment_worker_response(assignment) -> None:
    assignment.worker_response_status = AssignmentWorkerResponseStatus.PENDING.value
    assignment.worker_response_requested_at = datetime.now(timezone.utc)
    assignment.worker_response_at = None
    assignment.worker_response_note = None


def _clear_assignment_worker_response(assignment) -> None:
    assignment.worker_response_status = None
    assignment.worker_response_requested_at = None
    assignment.worker_response_at = None
    assignment.worker_response_note = None


def _apply_assignment_status_change(
    db: Session,
    assignment,
    target_status: str,
    cancel_reason: str | None,
    reopen_reason: str | None,
    current_user: User,
) -> None:
    from src.models.enums import ActualStatus, AuditAction
    from src.models.transaction import Actual

    if target_status == "canceled":
        reason = (cancel_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="取消理由は必須です")

        active_actual_exists = (
            db.query(Actual)
            .filter(Actual.assignment_id == assignment.id, Actual.status == ActualStatus.ACTIVE.value)
            .count()
        )
        if active_actual_exists:
            raise HTTPException(status_code=400, detail="active な実績があるため取消できません")

        assignment.status = target_status
        assignment.cancel_reason = reason
        _clear_assignment_worker_response(assignment)
        AuditService(db).log_assignment_canceled(
            assignment_id=assignment.id,
            reason=reason,
            actuals_invalidated=None,
            actor=current_user.username,
        )
        return

    before_status = assignment.status
    reason = None
    if before_status == "canceled":
        reason = (reopen_reason or "").strip()
        if not reason:
            raise HTTPException(status_code=400, detail="復帰理由は必須です")

    assignment.status = target_status
    assignment.cancel_reason = None
    if before_status != target_status:
        _activate_assignment_worker_response(assignment)
    AuditService(db).log(
        AuditAction.ASSIGNMENT_STATUS_CHANGED,
        target_type="assignment",
        target_id=assignment.id,
        actor=current_user.username,
        actor_role=current_user.role,
        before_value={"status": before_status},
        after_value={"status": assignment.status},
        reason=reason,
    )


@app.post("/api/assignments", response_model=AssignmentListItem, tags=["Assignments"])
async def create_assignment(
    request: AssignmentCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン作成"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_WRITE)

        from src.models.master import Role, Worker
        from src.models.transaction import Assignment, ShiftSlot

        shift_slot = db.get(ShiftSlot, request.shift_slot_id)
        if not shift_slot:
            raise HTTPException(status_code=404, detail="Shift slot not found")

        worker = db.get(Worker, request.worker_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        role = db.get(Role, request.role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        if request.status == "canceled" and not (request.cancel_reason or "").strip():
            raise HTTPException(status_code=400, detail="取消理由は必須です")

        existing = (
            db.query(Assignment)
            .filter(Assignment.shift_slot_id == request.shift_slot_id, Assignment.worker_id == request.worker_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="同一シフト枠に同じ稼働者のアサインが既に存在します")

        assignment = Assignment(
            shift_slot_id=request.shift_slot_id,
            worker_id=request.worker_id,
            role_id=request.role_id,
            status=request.status,
            cancel_reason=request.cancel_reason.strip() if request.cancel_reason else None,
            locked_price_sales=request.locked_price_sales,
            locked_price_outsource=request.locked_price_outsource,
        )
        if assignment.status == AssignmentStatus.CANCELED.value:
            _clear_assignment_worker_response(assignment)
        else:
            _activate_assignment_worker_response(assignment)
        db.add(assignment)

        AuditService(db).log(
            "assignment_created",
            target_type="assignment",
            target_id=assignment.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "shift_slot_id": assignment.shift_slot_id,
                "worker_id": assignment.worker_id,
                "role_id": assignment.role_id,
                "status": assignment.status,
            },
        )
        db.commit()
        db.refresh(assignment)

        return _serialize_assignment_item(assignment)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="アサイン作成に失敗しました")


@app.put("/api/assignments/{assignment_id}", response_model=AssignmentListItem, tags=["Assignments"])
async def update_assignment(
    assignment_id: str,
    request: AssignmentUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン編集"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_WRITE)

        from src.models.enums import ActualStatus
        from src.models.master import Role, Worker
        from src.models.transaction import Actual, Assignment, ShiftSlot

        assignment = db.get(Assignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        shift_slot = db.get(ShiftSlot, request.shift_slot_id)
        if not shift_slot:
            raise HTTPException(status_code=404, detail="Shift slot not found")

        worker = db.get(Worker, request.worker_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        role = db.get(Role, request.role_id)
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")

        duplicate = (
            db.query(Assignment)
            .filter(
                Assignment.id != assignment.id,
                Assignment.shift_slot_id == request.shift_slot_id,
                Assignment.worker_id == request.worker_id,
            )
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="同一シフト枠に同じ稼働者のアサインが既に存在します")

        structure_changed = any(
            (
                assignment.shift_slot_id != request.shift_slot_id,
                assignment.worker_id != request.worker_id,
                assignment.role_id != request.role_id,
            )
        )
        if structure_changed:
            active_actual_exists = (
                db.query(Actual)
                .filter(Actual.assignment_id == assignment.id, Actual.status == ActualStatus.ACTIVE.value)
                .count()
            )
            if active_actual_exists:
                raise HTTPException(status_code=400, detail="active な実績があるため枠・稼働者・役割は変更できません")

        before_value = {
            "shift_slot_id": assignment.shift_slot_id,
            "worker_id": assignment.worker_id,
            "role_id": assignment.role_id,
            "locked_price_sales": str(assignment.locked_price_sales) if assignment.locked_price_sales is not None else None,
            "locked_price_outsource": str(assignment.locked_price_outsource) if assignment.locked_price_outsource is not None else None,
        }

        assignment.shift_slot_id = request.shift_slot_id
        assignment.worker_id = request.worker_id
        assignment.role_id = request.role_id
        assignment.locked_price_sales = request.locked_price_sales
        assignment.locked_price_outsource = request.locked_price_outsource
        if structure_changed and assignment.status != AssignmentStatus.CANCELED.value:
            _activate_assignment_worker_response(assignment)

        AuditService(db).log(
            "assignment_updated",
            target_type="assignment",
            target_id=assignment.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "shift_slot_id": assignment.shift_slot_id,
                "worker_id": assignment.worker_id,
                "role_id": assignment.role_id,
                "locked_price_sales": str(assignment.locked_price_sales) if assignment.locked_price_sales is not None else None,
                "locked_price_outsource": str(assignment.locked_price_outsource) if assignment.locked_price_outsource is not None else None,
            },
        )

        db.commit()
        db.refresh(assignment)
        return _serialize_assignment_item(assignment)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="アサイン更新に失敗しました")


@app.post("/api/assignments/status/bulk", response_model=AssignmentBulkMutationResponse, tags=["Assignments"])
async def bulk_update_assignment_status(
    request: AssignmentBulkStatusUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン状態の一括更新"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_WRITE)

        from src.models.transaction import Assignment

        assignment_ids = list(dict.fromkeys(request.assignment_ids))
        assignments = db.query(Assignment).filter(Assignment.id.in_(assignment_ids)).all()
        assignments_by_id = {assignment.id: assignment for assignment in assignments}

        missing_ids = [assignment_id for assignment_id in assignment_ids if assignment_id not in assignments_by_id]
        if missing_ids:
            raise HTTPException(status_code=404, detail="一部のアサインが見つかりません")

        for assignment_id in assignment_ids:
            _apply_assignment_status_change(
                db,
                assignments_by_id[assignment_id],
                request.status,
                request.cancel_reason,
                request.reopen_reason,
                current_user,
            )

        db.commit()
        return AssignmentBulkMutationResponse(
            updated_count=len(assignment_ids),
            assignment_ids=assignment_ids,
            status=request.status,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="アサイン一括状態更新に失敗しました")


@app.post("/api/assignments/{assignment_id}/status", response_model=AssignmentListItem, tags=["Assignments"])
async def update_assignment_status(
    assignment_id: str,
    request: AssignmentStatusUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """アサイン状態更新"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_WRITE)

        from src.models.transaction import Assignment

        assignment = db.get(Assignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        _apply_assignment_status_change(db, assignment, request.status, request.cancel_reason, request.reopen_reason, current_user)

        db.commit()
        db.refresh(assignment)

        return _serialize_assignment_item(assignment)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="アサイン状態更新に失敗しました")


@app.post("/api/assignments/{assignment_id}/worker-response", response_model=AssignmentListItem, tags=["Assignments"])
async def update_assignment_worker_response(
    assignment_id: str,
    request: AssignmentWorkerResponseUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者による予定確認応答を更新"""
    try:
        check_permission(current_user, Permission.ASSIGNMENT_RESPONSE)

        from src.models.transaction import Assignment

        assignment = db.get(Assignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if not current_user.worker_id:
            raise HTTPException(status_code=403, detail="Worker is not linked to worker record")
        if assignment.worker_id != current_user.worker_id:
            raise HTTPException(status_code=403, detail="Assignment access denied")
        if assignment.status == AssignmentStatus.CANCELED.value:
            raise HTTPException(status_code=400, detail="取消済みアサインには回答できません")

        note = request.note.strip() if request.note else None
        before_value = {
            "worker_response_status": assignment.worker_response_status,
            "worker_response_requested_at": assignment.worker_response_requested_at.isoformat() if assignment.worker_response_requested_at else None,
            "worker_response_at": assignment.worker_response_at.isoformat() if assignment.worker_response_at else None,
            "worker_response_note": assignment.worker_response_note,
        }

        assignment.worker_response_status = request.response_status
        assignment.worker_response_at = datetime.now(timezone.utc)
        if assignment.worker_response_requested_at is None:
            assignment.worker_response_requested_at = assignment.worker_response_at
        assignment.worker_response_note = note

        AuditService(db).log(
            AuditAction.ASSIGNMENT_WORKER_RESPONSE_UPDATED,
            target_type="assignment",
            target_id=assignment.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "worker_response_status": assignment.worker_response_status,
                "worker_response_requested_at": assignment.worker_response_requested_at.isoformat() if assignment.worker_response_requested_at else None,
                "worker_response_at": assignment.worker_response_at.isoformat() if assignment.worker_response_at else None,
                "worker_response_note": assignment.worker_response_note,
            },
            reason=note,
        )

        db.commit()
        db.refresh(assignment)
        return _serialize_assignment_item(assignment)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="予定確認の更新に失敗しました")


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

    from src.models.master import Client, ProjectType, Site, VanzaiStaff
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
        db.query(Project, Client.name, Site.name, ProjectType.name, VanzaiStaff.name)
        .join(Client, Project.client_id == Client.id)
        .outerjoin(Site, Project.site_id == Site.id)
        .outerjoin(ProjectType, Project.project_type_id == ProjectType.id)
        .outerjoin(VanzaiStaff, Project.vanzai_manager_id == VanzaiStaff.id)
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
            client_id=project.client_id,
            client_name=client_name,
            site_id=project.site_id,
            site_name=site_name or "",
            project_type_id=project.project_type_id,
            project_type_name=project_type_name or "",
            start_date=project.start_date,
            end_date=project.end_date,
            primary_manager_id=project.primary_manager_id,
            secondary_manager_id=project.secondary_manager_id,
            vanzai_manager_id=project.vanzai_manager_id,
            vanzai_manager_name=vanzai_staff_name or None,
            notes=project.notes,
            is_active=project.is_active,
        )
        for project, client_name, site_name, project_type_name, vanzai_staff_name in rows
    ]

    return ProjectListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/projects", response_model=ProjectListItem, tags=["Projects"])
async def create_project(
    request: ProjectCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """案件作成"""
    try:
        check_permission(current_user, Permission.PROJECT_WRITE)

        from src.models.master import Client, ProjectType, Site, Worker, VanzaiStaff
        from src.models.transaction import Project

        client = db.get(Client, request.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        site = None
        if request.site_id:
            site = db.get(Site, request.site_id)
            if not site:
                raise HTTPException(status_code=404, detail="Site not found")

        project_type = None
        if request.project_type_id:
            project_type = db.get(ProjectType, request.project_type_id)
            if not project_type:
                raise HTTPException(status_code=404, detail="Project type not found")
        if request.vanzai_manager_id and not db.get(VanzaiStaff, request.vanzai_manager_id):
            raise HTTPException(status_code=404, detail="Vanzai manager not found")

        if request.primary_manager_id and not db.get(Worker, request.primary_manager_id):
            raise HTTPException(status_code=404, detail="Primary manager not found")
        if request.secondary_manager_id and not db.get(Worker, request.secondary_manager_id):
            raise HTTPException(status_code=404, detail="Secondary manager not found")
        if request.start_date and request.end_date and request.start_date > request.end_date:
            raise HTTPException(status_code=400, detail="開始日が終了日を超えています")
        if request.code and db.query(Project).filter(Project.code == request.code.strip()).first():
            raise HTTPException(status_code=400, detail="案件コードが重複しています")

        project = Project(
            name=request.name.strip(),
            code=request.code.strip() if request.code else None,
            client_id=request.client_id,
            site_id=request.site_id,
            project_type_id=request.project_type_id,
            primary_manager_id=request.primary_manager_id,
            secondary_manager_id=request.secondary_manager_id,
            vanzai_manager_id=request.vanzai_manager_id,
            start_date=request.start_date,
            end_date=request.end_date,
            notes=request.notes,
            is_active=request.is_active,
        )
        db.add(project)

        AuditService(db).log(
            "project_created",
            target_type="project",
            target_id=project.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "name": project.name,
                "code": project.code,
                "client_id": project.client_id,
                "site_id": project.site_id,
                "project_type_id": project.project_type_id,
                "vanzai_manager_id": project.vanzai_manager_id,
                "start_date": project.start_date.isoformat() if project.start_date else None,
                "end_date": project.end_date.isoformat() if project.end_date else None,
                "is_active": project.is_active,
            },
        )
        db.commit()
        db.refresh(project)

        return ProjectListItem(
            id=project.id,
            code=project.code,
            name=project.name,
            client_id=project.client_id,
            client_name=client.name,
            site_id=project.site_id,
            site_name=site.name if site else "",
            project_type_id=project.project_type_id,
            project_type_name=project_type.name if project_type else "",
            start_date=project.start_date,
            end_date=project.end_date,
            primary_manager_id=project.primary_manager_id,
            secondary_manager_id=project.secondary_manager_id,
            vanzai_manager_id=project.vanzai_manager_id,
            vanzai_manager_name=(db.get(VanzaiStaff, project.vanzai_manager_id).name if project.vanzai_manager_id else None),
            notes=project.notes,
            is_active=project.is_active,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="案件作成に失敗しました")


@app.put("/api/projects/{project_id}", response_model=ProjectListItem, tags=["Projects"])
async def update_project(
    project_id: str,
    request: ProjectUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """案件更新"""
    try:
        check_permission(current_user, Permission.PROJECT_WRITE)

        from src.models.master import Client, ProjectType, Site, Worker, VanzaiStaff
        from src.models.transaction import Project

        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        client = db.get(Client, request.client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        site = None
        if request.site_id:
            site = db.get(Site, request.site_id)
            if not site:
                raise HTTPException(status_code=404, detail="Site not found")

        project_type = None
        if request.project_type_id:
            project_type = db.get(ProjectType, request.project_type_id)
            if not project_type:
                raise HTTPException(status_code=404, detail="Project type not found")
        if request.vanzai_manager_id and not db.get(VanzaiStaff, request.vanzai_manager_id):
            raise HTTPException(status_code=404, detail="Vanzai manager not found")

        if request.primary_manager_id and not db.get(Worker, request.primary_manager_id):
            raise HTTPException(status_code=404, detail="Primary manager not found")
        if request.secondary_manager_id and not db.get(Worker, request.secondary_manager_id):
            raise HTTPException(status_code=404, detail="Secondary manager not found")
        if request.start_date and request.end_date and request.start_date > request.end_date:
            raise HTTPException(status_code=400, detail="開始日が終了日を超えています")
        if request.code:
            duplicated = db.query(Project).filter(Project.code == request.code.strip(), Project.id != project.id).first()
            if duplicated:
                raise HTTPException(status_code=400, detail="案件コードが重複しています")

        before_value = {
            "name": project.name,
            "code": project.code,
            "client_id": project.client_id,
            "site_id": project.site_id,
            "project_type_id": project.project_type_id,
            "primary_manager_id": project.primary_manager_id,
            "secondary_manager_id": project.secondary_manager_id,
            "vanzai_manager_id": project.vanzai_manager_id,
            "start_date": project.start_date.isoformat() if project.start_date else None,
            "end_date": project.end_date.isoformat() if project.end_date else None,
            "notes": project.notes,
            "is_active": project.is_active,
        }

        project.name = request.name.strip()
        project.code = request.code.strip() if request.code else None
        project.client_id = request.client_id
        project.site_id = request.site_id
        project.project_type_id = request.project_type_id
        project.primary_manager_id = request.primary_manager_id
        project.secondary_manager_id = request.secondary_manager_id
        project.vanzai_manager_id = request.vanzai_manager_id
        project.start_date = request.start_date
        project.end_date = request.end_date
        project.notes = request.notes
        project.is_active = request.is_active

        AuditService(db).log(
            "project_updated",
            target_type="project",
            target_id=project.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "name": project.name,
                "code": project.code,
                "client_id": project.client_id,
                "site_id": project.site_id,
                "project_type_id": project.project_type_id,
                "primary_manager_id": project.primary_manager_id,
                "secondary_manager_id": project.secondary_manager_id,
                "vanzai_manager_id": project.vanzai_manager_id,
                "start_date": project.start_date.isoformat() if project.start_date else None,
                "end_date": project.end_date.isoformat() if project.end_date else None,
                "notes": project.notes,
                "is_active": project.is_active,
            },
        )
        db.commit()
        db.refresh(project)

        return ProjectListItem(
            id=project.id,
            code=project.code,
            name=project.name,
            client_id=project.client_id,
            client_name=client.name,
            site_id=project.site_id,
            site_name=site.name if site else "",
            project_type_id=project.project_type_id,
            project_type_name=project_type.name if project_type else "",
            start_date=project.start_date,
            end_date=project.end_date,
            primary_manager_id=project.primary_manager_id,
            secondary_manager_id=project.secondary_manager_id,
            vanzai_manager_id=project.vanzai_manager_id,
            vanzai_manager_name=(db.get(VanzaiStaff, project.vanzai_manager_id).name if project.vanzai_manager_id else None),
            notes=project.notes,
            is_active=project.is_active,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="案件更新に失敗しました")


@app.patch("/api/projects/{project_id}/notes", response_model=ProjectListItem, tags=["Projects"])
async def update_project_notes(
    project_id: str,
    request: ProjectNotesUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """案件運用メモ更新"""
    try:
        check_permission(current_user, Permission.PROJECT_WRITE)

        from src.models.master import Client, ProjectType, Site
        from src.models.transaction import Project

        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        before_notes = project.notes
        project.notes = request.notes.strip() if request.notes is not None else None

        client = db.get(Client, project.client_id)
        site = db.get(Site, project.site_id) if project.site_id else None
        project_type = db.get(ProjectType, project.project_type_id) if project.project_type_id else None

        AuditService(db).log(
            "project_updated",
            target_type="project",
            target_id=project.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value={"notes": before_notes},
            after_value={"notes": project.notes},
        )
        db.commit()
        db.refresh(project)

        return ProjectListItem(
            id=project.id,
            code=project.code,
            name=project.name,
            client_id=project.client_id,
            client_name=client.name if client else "",
            site_id=project.site_id,
            site_name=site.name if site else "",
            project_type_id=project.project_type_id,
            project_type_name=project_type.name if project_type else "",
            start_date=project.start_date,
            end_date=project.end_date,
            primary_manager_id=project.primary_manager_id,
            secondary_manager_id=project.secondary_manager_id,
            notes=project.notes,
            is_active=project.is_active,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="案件運用メモの更新に失敗しました")


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


@app.post("/api/shift-slots", response_model=ShiftSlotListItem, tags=["Shift Slots"])
async def create_shift_slot(
    request: ShiftSlotCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """シフト枠作成"""
    try:
        check_permission(current_user, Permission.SHIFT_WRITE)

        from src.models.transaction import Assignment, Project, ShiftSlot

        project = db.get(Project, request.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        slot = ShiftSlot(
            project_id=request.project_id,
            work_date=request.work_date,
            start_time=_parse_optional_time(request.start_time),
            end_time=_parse_optional_time(request.end_time),
            shift_label=request.shift_label,
            required_count=request.required_count,
            notes=request.notes,
        )
        db.add(slot)

        AuditService(db).log(
            "shift_slot_created",
            target_type="shift_slot",
            target_id=slot.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "project_id": slot.project_id,
                "work_date": slot.work_date.isoformat(),
                "start_time": slot.start_time.isoformat() if slot.start_time else None,
                "end_time": slot.end_time.isoformat() if slot.end_time else None,
                "shift_label": slot.shift_label,
                "required_count": slot.required_count,
            },
        )
        db.commit()
        db.refresh(slot)

        return ShiftSlotListItem(
            id=slot.id,
            project_id=slot.project_id,
            project_name=project.name,
            work_date=slot.work_date,
            start_time=slot.start_time.isoformat() if slot.start_time else None,
            end_time=slot.end_time.isoformat() if slot.end_time else None,
            shift_label=slot.shift_label,
            required_count=slot.required_count,
            assigned_count=0,
            notes=slot.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError:
        raise HTTPException(status_code=400, detail="時刻形式が不正です")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="シフト枠作成に失敗しました")


@app.put("/api/shift-slots/{shift_slot_id}", response_model=ShiftSlotListItem, tags=["Shift Slots"])
async def update_shift_slot(
    shift_slot_id: str,
    request: ShiftSlotUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """シフト枠更新"""
    try:
        check_permission(current_user, Permission.SHIFT_WRITE)

        from src.models.transaction import Assignment, Project, ShiftSlot

        slot = db.get(ShiftSlot, shift_slot_id)
        if not slot:
            raise HTTPException(status_code=404, detail="Shift slot not found")

        project = db.get(Project, request.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        assigned_count = (
            db.query(func.count(Assignment.id))
            .filter(Assignment.shift_slot_id == slot.id)
            .scalar()
            or 0
        )
        if assigned_count > 0 and request.project_id != slot.project_id:
            raise HTTPException(status_code=400, detail="アサイン済みのシフト枠は案件を変更できません")
        if request.required_count < assigned_count:
            raise HTTPException(status_code=400, detail="必要人数を確定人数未満にはできません")

        before_value = {
            "project_id": slot.project_id,
            "work_date": slot.work_date.isoformat(),
            "start_time": slot.start_time.isoformat() if slot.start_time else None,
            "end_time": slot.end_time.isoformat() if slot.end_time else None,
            "shift_label": slot.shift_label,
            "required_count": slot.required_count,
            "notes": slot.notes,
        }

        slot.project_id = request.project_id
        slot.work_date = request.work_date
        slot.start_time = _parse_optional_time(request.start_time)
        slot.end_time = _parse_optional_time(request.end_time)
        slot.shift_label = request.shift_label
        slot.required_count = request.required_count
        slot.notes = request.notes

        AuditService(db).log(
            "shift_slot_updated",
            target_type="shift_slot",
            target_id=slot.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "project_id": slot.project_id,
                "work_date": slot.work_date.isoformat(),
                "start_time": slot.start_time.isoformat() if slot.start_time else None,
                "end_time": slot.end_time.isoformat() if slot.end_time else None,
                "shift_label": slot.shift_label,
                "required_count": slot.required_count,
                "notes": slot.notes,
            },
        )
        db.commit()
        db.refresh(slot)

        return ShiftSlotListItem(
            id=slot.id,
            project_id=slot.project_id,
            project_name=project.name,
            work_date=slot.work_date,
            start_time=slot.start_time.isoformat() if slot.start_time else None,
            end_time=slot.end_time.isoformat() if slot.end_time else None,
            shift_label=slot.shift_label,
            required_count=slot.required_count,
            assigned_count=assigned_count,
            notes=slot.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError:
        raise HTTPException(status_code=400, detail="時刻形式が不正です")
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="シフト枠更新に失敗しました")


@app.patch("/api/shift-slots/{shift_slot_id}/notes", response_model=ShiftSlotListItem, tags=["Shift Slots"])
async def update_shift_slot_notes(
    shift_slot_id: str,
    request: ShiftSlotNotesUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """シフト枠運用メモ更新"""
    try:
        check_permission(current_user, Permission.SHIFT_WRITE)

        from src.models.transaction import Assignment, Project, ShiftSlot

        slot = db.get(ShiftSlot, shift_slot_id)
        if not slot:
            raise HTTPException(status_code=404, detail="Shift slot not found")

        project = db.get(Project, slot.project_id)
        before_notes = slot.notes
        slot.notes = request.notes.strip() if request.notes is not None else None

        assigned_count = (
            db.query(func.count(Assignment.id))
            .filter(Assignment.shift_slot_id == slot.id)
            .scalar()
            or 0
        )

        AuditService(db).log(
            "shift_slot_updated",
            target_type="shift_slot",
            target_id=slot.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value={"notes": before_notes},
            after_value={"notes": slot.notes},
        )
        db.commit()
        db.refresh(slot)

        return ShiftSlotListItem(
            id=slot.id,
            project_id=slot.project_id,
            project_name=project.name if project else "",
            work_date=slot.work_date,
            start_time=slot.start_time.isoformat() if slot.start_time else None,
            end_time=slot.end_time.isoformat() if slot.end_time else None,
            shift_label=slot.shift_label,
            required_count=slot.required_count,
            assigned_count=assigned_count,
            notes=slot.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="シフト枠運用メモの更新に失敗しました")


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

    role = UserRole(current_user.role)
    if role == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        stmt = stmt.filter(Expense.worker_id == current_user.worker_id)

    total = stmt.count()
    rows = stmt.order_by(sort_expression, Expense.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [_serialize_expense_list_item(expense, project_name, worker_name) for expense, project_name, worker_name in rows]

    return ExpenseListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/expenses", response_model=ExpenseSubmissionResponse, tags=["Expenses"])
async def submit_expense(
    project_id: str = Form(...),
    expense_date: date = Form(...),
    category: str = Form(...),
    amount: str = Form(...),
    description: str | None = Form(None),
    worker_id: str | None = Form(None),
    receipt: UploadFile | None = File(None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """経費申請を作成する"""
    try:
        check_permission(current_user, Permission.EXPENSE_SUBMIT)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker
    from src.models.transaction import Assignment, Expense, Project, ShiftSlot

    submitter_role = UserRole(current_user.role)
    effective_worker_id = worker_id
    if submitter_role == UserRole.WORKER:
        if not current_user.worker_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Worker is not linked to worker record")
        effective_worker_id = current_user.worker_id

    if not effective_worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")

    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    worker = db.get(Worker, effective_worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")

    if submitter_role == UserRole.WORKER:
        has_assignment = (
            db.query(Assignment)
            .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
            .filter(
                Assignment.worker_id == effective_worker_id,
                ShiftSlot.project_id == project_id,
            )
            .first()
        )
        if has_assignment is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project access denied")

    expense = Expense(
        id=generate_ulid(),
        project_id=project_id,
        worker_id=effective_worker_id,
        expense_date=expense_date,
        category=category.strip(),
        amount=_parse_decimal_form_value(amount, "amount"),
        description=description.strip() if description else None,
        status=ExpenseStatus.PENDING.value,
        target_invoice=False,
        target_payout=True,
    )
    db.add(expense)
    db.flush()

    if receipt is not None and receipt.filename:
        expense.receipt_file_key = await _store_receipt_upload(expense.id, expense.expense_date, receipt)

    AuditService(db).log(
        AuditAction.EXPENSE_SUBMITTED,
        target_type="expense",
        target_id=expense.id,
        actor=current_user.username,
        actor_role=current_user.role,
        after_value={
            "project_id": project_id,
            "worker_id": effective_worker_id,
            "expense_date": expense_date.isoformat(),
            "category": expense.category,
            "amount": str(expense.amount),
            "has_receipt": bool(expense.receipt_file_key),
        },
    )
    db.commit()
    db.refresh(expense)

    return ExpenseSubmissionResponse(
        id=expense.id,
        expense_date=expense.expense_date,
        project_id=expense.project_id,
        project_name=project.name,
        worker_id=expense.worker_id,
        worker_name=worker.name,
        category=expense.category,
        amount=expense.amount,
        description=expense.description,
        status=expense.status,
        reject_reason=expense.reject_reason,
        has_receipt=bool(expense.receipt_file_key),
    )


@app.post("/api/expenses/{expense_id}/approve", response_model=ExpenseListItem, tags=["Expenses"])
async def approve_expense(
    expense_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """経費を承認する"""
    try:
        check_permission(current_user, Permission.EXPENSE_APPROVE)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker
    from src.models.transaction import Expense, Project

    expense = _load_accessible_expense(db, expense_id, current_user)
    if expense.status != ExpenseStatus.PENDING.value:
        raise HTTPException(status_code=409, detail="Pending expense only can be approved")

    expense.status = ExpenseStatus.APPROVED.value
    expense.approved_by = current_user.username
    expense.approved_at = datetime.now(timezone.utc)
    expense.reject_reason = None

    AuditService(db).log(
        AuditAction.EXPENSE_APPROVED,
        target_type="expense",
        target_id=expense.id,
        actor=current_user.username,
        actor_role=current_user.role,
        after_value={
            "status": expense.status,
            "approved_by": expense.approved_by,
            "approved_at": expense.approved_at.isoformat() if expense.approved_at else None,
        },
    )
    db.commit()

    row = (
        db.query(Expense, Project.name, Worker.name)
        .join(Project, Expense.project_id == Project.id)
        .outerjoin(Worker, Expense.worker_id == Worker.id)
        .filter(Expense.id == expense.id)
        .one()
    )
    return _serialize_expense_list_item(*row)


@app.post("/api/expenses/{expense_id}/reject", response_model=ExpenseListItem, tags=["Expenses"])
async def reject_expense(
    expense_id: str,
    request: ExpenseActionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """経費を却下する"""
    try:
        check_permission(current_user, Permission.EXPENSE_APPROVE)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if not request.reject_reason or not request.reject_reason.strip():
        raise HTTPException(status_code=400, detail="reject_reason is required")

    from src.models.master import Worker
    from src.models.transaction import Expense, Project

    expense = _load_accessible_expense(db, expense_id, current_user)
    if expense.status != ExpenseStatus.PENDING.value:
        raise HTTPException(status_code=409, detail="Pending expense only can be rejected")

    expense.status = ExpenseStatus.REJECTED.value
    expense.approved_by = current_user.username
    expense.approved_at = datetime.now(timezone.utc)
    expense.reject_reason = request.reject_reason.strip()

    AuditService(db).log(
        AuditAction.EXPENSE_REJECTED,
        target_type="expense",
        target_id=expense.id,
        actor=current_user.username,
        actor_role=current_user.role,
        reason=expense.reject_reason,
        after_value={
            "status": expense.status,
            "approved_by": expense.approved_by,
            "approved_at": expense.approved_at.isoformat() if expense.approved_at else None,
            "reject_reason": expense.reject_reason,
        },
    )
    db.commit()

    row = (
        db.query(Expense, Project.name, Worker.name)
        .join(Project, Expense.project_id == Project.id)
        .outerjoin(Worker, Expense.worker_id == Worker.id)
        .filter(Expense.id == expense.id)
        .one()
    )
    return _serialize_expense_list_item(*row)


@app.get("/api/expenses/{expense_id}/receipt", response_class=FileResponse, tags=["Expenses"])
async def download_expense_receipt(
    expense_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """領収書ファイルをダウンロードする"""
    try:
        check_permission(current_user, Permission.EXPENSE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    expense = _load_accessible_expense(db, expense_id, current_user)
    if not expense.receipt_file_key:
        raise HTTPException(status_code=404, detail="Receipt not found")

    storage = _receipt_storage()
    if not storage.exists(expense.receipt_file_key):
        raise HTTPException(status_code=404, detail="Receipt file not found")

    receipt_path = storage.resolve_path(expense.receipt_file_key)
    media_type, _ = mimetypes.guess_type(receipt_path.name)
    return FileResponse(
        path=receipt_path,
        filename=PurePath(expense.receipt_file_key).name,
        media_type=media_type or "application/octet-stream",
    )


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
            conditions=rule.conditions,
            sales_price=rule.sales_price,
            outsource_price=rule.outsource_price,
            valid_from=rule.valid_from,
            valid_to=rule.valid_to,
            is_active=rule.is_active,
            notes=rule.notes,
        )
        for rule in rows
    ]

    return PriceRuleListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/price-rules", response_model=PriceRuleListItem, tags=["Price Rules"])
async def create_price_rule(
    request: PriceRuleCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """単価ルール作成"""
    try:
        check_permission(current_user, Permission.PRICE_WRITE)

        from src.models.master import PriceRule

        rule = PriceRule(
            name=request.name.strip(),
            priority=request.priority,
            conditions=request.conditions,
            sales_price=request.sales_price,
            outsource_price=request.outsource_price,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            is_active=request.is_active,
            notes=request.notes.strip() if request.notes else None,
        )
        db.add(rule)

        AuditService(db).log(
            "price_rule_created",
            target_type="price_rule",
            target_id=rule.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "name": rule.name,
                "priority": rule.priority,
                "conditions": rule.conditions,
                "sales_price": str(rule.sales_price) if rule.sales_price is not None else None,
                "outsource_price": str(rule.outsource_price) if rule.outsource_price is not None else None,
                "is_active": rule.is_active,
            },
        )
        db.commit()
        db.refresh(rule)

        return PriceRuleListItem(
            id=rule.id,
            name=rule.name,
            priority=rule.priority,
            conditions=rule.conditions,
            sales_price=rule.sales_price,
            outsource_price=rule.outsource_price,
            valid_from=rule.valid_from,
            valid_to=rule.valid_to,
            is_active=rule.is_active,
            notes=rule.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="単価ルール作成に失敗しました")


@app.put("/api/price-rules/{price_rule_id}", response_model=PriceRuleListItem, tags=["Price Rules"])
async def update_price_rule(
    price_rule_id: str,
    request: PriceRuleUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """単価ルール更新"""
    try:
        check_permission(current_user, Permission.PRICE_WRITE)

        from src.models.master import PriceRule

        rule = db.get(PriceRule, price_rule_id)
        if not rule or rule.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Price rule not found")

        before_value = {
            "name": rule.name,
            "priority": rule.priority,
            "conditions": rule.conditions,
            "sales_price": str(rule.sales_price) if rule.sales_price is not None else None,
            "outsource_price": str(rule.outsource_price) if rule.outsource_price is not None else None,
            "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
            "valid_to": rule.valid_to.isoformat() if rule.valid_to else None,
            "is_active": rule.is_active,
            "notes": rule.notes,
        }

        rule.name = request.name.strip()
        rule.priority = request.priority
        rule.conditions = request.conditions
        rule.sales_price = request.sales_price
        rule.outsource_price = request.outsource_price
        rule.valid_from = request.valid_from
        rule.valid_to = request.valid_to
        rule.is_active = request.is_active
        rule.notes = request.notes.strip() if request.notes else None

        AuditService(db).log(
            "price_rule_updated",
            target_type="price_rule",
            target_id=rule.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "name": rule.name,
                "priority": rule.priority,
                "conditions": rule.conditions,
                "sales_price": str(rule.sales_price) if rule.sales_price is not None else None,
                "outsource_price": str(rule.outsource_price) if rule.outsource_price is not None else None,
                "valid_from": rule.valid_from.isoformat() if rule.valid_from else None,
                "valid_to": rule.valid_to.isoformat() if rule.valid_to else None,
                "is_active": rule.is_active,
                "notes": rule.notes,
            },
        )
        db.commit()
        db.refresh(rule)

        return PriceRuleListItem(
            id=rule.id,
            name=rule.name,
            priority=rule.priority,
            conditions=rule.conditions,
            sales_price=rule.sales_price,
            outsource_price=rule.outsource_price,
            valid_from=rule.valid_from,
            valid_to=rule.valid_to,
            is_active=rule.is_active,
            notes=rule.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="単価ルール更新に失敗しました")


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
            notes=price.notes,
        )
        for price, project_name, role_name, client_name in rows
    ]

    return PriceSalesListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/price-sales", response_model=PriceSalesListItem, tags=["Price"])
async def create_price_sales(
    request: PriceSalesCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """売上単価作成"""
    try:
        check_permission(current_user, Permission.PRICE_WRITE)

        from src.models.master import Client, PriceSales, Role
        from src.models.transaction import Project

        project_name = ""
        role_name = ""
        client_name = ""
        if request.project_id:
            project = db.get(Project, request.project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            project_name = project.name
        if request.role_id:
            role = db.get(Role, request.role_id)
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")
            role_name = role.name
        if request.client_id:
            client = db.get(Client, request.client_id)
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
            client_name = client.name

        price = PriceSales(
            project_id=request.project_id,
            role_id=request.role_id,
            client_id=request.client_id,
            unit_price=request.unit_price,
            unit_type=request.unit_type,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            is_default=request.is_default,
            notes=request.notes.strip() if request.notes else None,
        )
        db.add(price)

        AuditService(db).log(
            "price_sales_created",
            target_type="price_sales",
            target_id=price.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "project_id": price.project_id,
                "role_id": price.role_id,
                "client_id": price.client_id,
                "unit_price": str(price.unit_price),
                "unit_type": price.unit_type,
                "is_default": price.is_default,
            },
        )
        db.commit()
        db.refresh(price)

        return PriceSalesListItem(
            id=price.id,
            project_id=price.project_id,
            project_name=project_name,
            role_id=price.role_id,
            role_name=role_name,
            client_id=price.client_id,
            client_name=client_name,
            unit_price=price.unit_price,
            unit_type=price.unit_type,
            valid_from=price.valid_from,
            valid_to=price.valid_to,
            is_default=price.is_default,
            notes=price.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="売上単価作成に失敗しました")


@app.put("/api/price-sales/{price_sales_id}", response_model=PriceSalesListItem, tags=["Price"])
async def update_price_sales(
    price_sales_id: str,
    request: PriceSalesUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """売上単価更新"""
    try:
        check_permission(current_user, Permission.PRICE_WRITE)

        from src.models.master import Client, PriceSales, Role
        from src.models.transaction import Project

        price = db.get(PriceSales, price_sales_id)
        if not price or price.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Price sales not found")

        project_name = ""
        role_name = ""
        client_name = ""
        if request.project_id:
            project = db.get(Project, request.project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            project_name = project.name
        if request.role_id:
            role = db.get(Role, request.role_id)
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")
            role_name = role.name
        if request.client_id:
            client = db.get(Client, request.client_id)
            if not client:
                raise HTTPException(status_code=404, detail="Client not found")
            client_name = client.name

        before_value = {
            "project_id": price.project_id,
            "role_id": price.role_id,
            "client_id": price.client_id,
            "unit_price": str(price.unit_price),
            "unit_type": price.unit_type,
            "valid_from": price.valid_from.isoformat() if price.valid_from else None,
            "valid_to": price.valid_to.isoformat() if price.valid_to else None,
            "is_default": price.is_default,
            "notes": price.notes,
        }

        price.project_id = request.project_id
        price.role_id = request.role_id
        price.client_id = request.client_id
        price.unit_price = request.unit_price
        price.unit_type = request.unit_type
        price.valid_from = request.valid_from
        price.valid_to = request.valid_to
        price.is_default = request.is_default
        price.notes = request.notes.strip() if request.notes else None

        AuditService(db).log(
            "price_sales_updated",
            target_type="price_sales",
            target_id=price.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "project_id": price.project_id,
                "role_id": price.role_id,
                "client_id": price.client_id,
                "unit_price": str(price.unit_price),
                "unit_type": price.unit_type,
                "valid_from": price.valid_from.isoformat() if price.valid_from else None,
                "valid_to": price.valid_to.isoformat() if price.valid_to else None,
                "is_default": price.is_default,
                "notes": price.notes,
            },
        )
        db.commit()
        db.refresh(price)

        return PriceSalesListItem(
            id=price.id,
            project_id=price.project_id,
            project_name=project_name,
            role_id=price.role_id,
            role_name=role_name,
            client_id=price.client_id,
            client_name=client_name,
            unit_price=price.unit_price,
            unit_type=price.unit_type,
            valid_from=price.valid_from,
            valid_to=price.valid_to,
            is_default=price.is_default,
            notes=price.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="売上単価更新に失敗しました")


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
            notes=price.notes,
        )
        for price, project_name, worker_name, role_name in rows
    ]

    return PriceOutsourceListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/price-outsource", response_model=PriceOutsourceListItem, tags=["Price"])
async def create_price_outsource(
    request: PriceOutsourceCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """外注単価作成"""
    try:
        check_permission(current_user, Permission.PRICE_WRITE)

        from src.models.master import PriceOutsource, Role, Worker
        from src.models.transaction import Project

        project_name = ""
        worker_name = ""
        role_name = ""
        if request.project_id:
            project = db.get(Project, request.project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            project_name = project.name
        if request.worker_id:
            worker = db.get(Worker, request.worker_id)
            if not worker:
                raise HTTPException(status_code=404, detail="Worker not found")
            worker_name = worker.name
        if request.role_id:
            role = db.get(Role, request.role_id)
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")
            role_name = role.name

        price = PriceOutsource(
            project_id=request.project_id,
            worker_id=request.worker_id,
            role_id=request.role_id,
            unit_price=request.unit_price,
            unit_type=request.unit_type,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            is_default=request.is_default,
            notes=request.notes.strip() if request.notes else None,
        )
        db.add(price)

        AuditService(db).log(
            "price_outsource_created",
            target_type="price_outsource",
            target_id=price.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "project_id": price.project_id,
                "worker_id": price.worker_id,
                "role_id": price.role_id,
                "unit_price": str(price.unit_price),
                "unit_type": price.unit_type,
                "is_default": price.is_default,
            },
        )
        db.commit()
        db.refresh(price)

        return PriceOutsourceListItem(
            id=price.id,
            project_id=price.project_id,
            project_name=project_name,
            worker_id=price.worker_id,
            worker_name=worker_name,
            role_id=price.role_id,
            role_name=role_name,
            unit_price=price.unit_price,
            unit_type=price.unit_type,
            valid_from=price.valid_from,
            valid_to=price.valid_to,
            is_default=price.is_default,
            notes=price.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="外注単価作成に失敗しました")


@app.put("/api/price-outsource/{price_outsource_id}", response_model=PriceOutsourceListItem, tags=["Price"])
async def update_price_outsource(
    price_outsource_id: str,
    request: PriceOutsourceUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """外注単価更新"""
    try:
        check_permission(current_user, Permission.PRICE_WRITE)

        from src.models.master import PriceOutsource, Role, Worker
        from src.models.transaction import Project

        price = db.get(PriceOutsource, price_outsource_id)
        if not price or price.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Price outsource not found")

        project_name = ""
        worker_name = ""
        role_name = ""
        if request.project_id:
            project = db.get(Project, request.project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            project_name = project.name
        if request.worker_id:
            worker = db.get(Worker, request.worker_id)
            if not worker:
                raise HTTPException(status_code=404, detail="Worker not found")
            worker_name = worker.name
        if request.role_id:
            role = db.get(Role, request.role_id)
            if not role:
                raise HTTPException(status_code=404, detail="Role not found")
            role_name = role.name

        before_value = {
            "project_id": price.project_id,
            "worker_id": price.worker_id,
            "role_id": price.role_id,
            "unit_price": str(price.unit_price),
            "unit_type": price.unit_type,
            "valid_from": price.valid_from.isoformat() if price.valid_from else None,
            "valid_to": price.valid_to.isoformat() if price.valid_to else None,
            "is_default": price.is_default,
            "notes": price.notes,
        }

        price.project_id = request.project_id
        price.worker_id = request.worker_id
        price.role_id = request.role_id
        price.unit_price = request.unit_price
        price.unit_type = request.unit_type
        price.valid_from = request.valid_from
        price.valid_to = request.valid_to
        price.is_default = request.is_default
        price.notes = request.notes.strip() if request.notes else None

        AuditService(db).log(
            "price_outsource_updated",
            target_type="price_outsource",
            target_id=price.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "project_id": price.project_id,
                "worker_id": price.worker_id,
                "role_id": price.role_id,
                "unit_price": str(price.unit_price),
                "unit_type": price.unit_type,
                "valid_from": price.valid_from.isoformat() if price.valid_from else None,
                "valid_to": price.valid_to.isoformat() if price.valid_to else None,
                "is_default": price.is_default,
                "notes": price.notes,
            },
        )
        db.commit()
        db.refresh(price)

        return PriceOutsourceListItem(
            id=price.id,
            project_id=price.project_id,
            project_name=project_name,
            worker_id=price.worker_id,
            worker_name=worker_name,
            role_id=price.role_id,
            role_name=role_name,
            unit_price=price.unit_price,
            unit_type=price.unit_type,
            valid_from=price.valid_from,
            valid_to=price.valid_to,
            is_default=price.is_default,
            notes=price.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="外注単価更新に失敗しました")


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
            billing_date=invoice.billing_date,
            document_type=invoice.document_type,
            subject=invoice.invoice_subject,
            addressee_company_name=invoice.addressee_company_name,
            addressee_name=invoice.addressee_name,
            fixed_office_fee_amount=invoice.fixed_office_fee_amount,
            version=invoice.version,
            status=invoice.status,
            total_amount=invoice.total_amount,
            issued_at=invoice.issued_at,
            has_pdf=bool(invoice.pdf_object_key),
            pdf_storage_key=invoice.pdf_object_key,
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

    from src.models.master import Supplier, Worker, VanzaiStaff
    from src.models.transaction import Payout, PayoutDelivery, Project

    payee_name_expr = func.coalesce(Payout.payee_name_snapshot, Worker.name, Supplier.name, VanzaiStaff.name)

    latest_delivery_status_subquery = (
        select(PayoutDelivery.status)
        .where(PayoutDelivery.payout_id == Payout.id)
        .order_by(PayoutDelivery.sent_at.desc(), PayoutDelivery.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )

    sort_map = {
        "period_key": Payout.period_key,
        "payee_name": payee_name_expr,
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
        db.query(Payout, Worker.name, Worker.email, Supplier.name, Supplier.contact_email, VanzaiStaff.name, VanzaiStaff.email, Project.name)
        .outerjoin(Worker, Payout.worker_id == Worker.id)
        .outerjoin(Supplier, Payout.supplier_id == Supplier.id)
        .outerjoin(VanzaiStaff, and_(Payout.recipient_type == "vanzai_staff", Payout.recipient_id == VanzaiStaff.id))
        .outerjoin(Project, Payout.project_id == Project.id)
    )

    if query.period_key:
        stmt = stmt.filter(Payout.period_key == query.period_key)
    if query.worker_id:
        stmt = stmt.filter(Payout.worker_id == query.worker_id)
    if query.supplier_id:
        stmt = stmt.filter(Payout.supplier_id == query.supplier_id)
    if query.recipient_type:
        stmt = stmt.filter(Payout.recipient_type == query.recipient_type)
    if query.recipient_id:
        stmt = stmt.filter(Payout.recipient_id == query.recipient_id)
    if query.project_id:
        stmt = stmt.filter(Payout.project_id == query.project_id)
    if query.status:
        stmt = stmt.filter(Payout.status == query.status)
    if query.missing_default_recipient_only:
        stmt = stmt.filter(
            or_(
                and_(
                    Payout.worker_id.is_not(None),
                    or_(Worker.email.is_(None), func.trim(Worker.email) == ""),
                ),
                and_(
                    Payout.supplier_id.is_not(None),
                    or_(Supplier.contact_email.is_(None), func.trim(Supplier.contact_email) == ""),
                ),
                and_(
                    Payout.recipient_type == "vanzai_staff",
                    or_(VanzaiStaff.email.is_(None), func.trim(VanzaiStaff.email) == ""),
                ),
                and_(Payout.worker_id.is_(None), Payout.supplier_id.is_(None)),
            )
        )
    if query.delivery_state == "unsent":
        stmt = stmt.filter(latest_delivery_status_subquery.is_(None))
    if query.delivery_state == "failed":
        stmt = stmt.filter(latest_delivery_status_subquery == "failed")

    total = stmt.count()
    rows = (
        stmt.order_by(sort_expression, Payout.id.desc())
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )

    payout_ids = [payout.id for payout, *_ in rows]
    latest_deliveries_by_payout: dict[str, object] = {}
    if payout_ids:
        deliveries = (
            db.query(PayoutDelivery)
            .filter(PayoutDelivery.payout_id.in_(payout_ids))
            .order_by(PayoutDelivery.sent_at.desc(), PayoutDelivery.created_at.desc())
            .all()
        )
        for delivery in deliveries:
            latest_deliveries_by_payout.setdefault(delivery.payout_id, delivery)

    items = []
    for payout, worker_name, worker_email, supplier_name, supplier_email, vanzai_staff_name, vanzai_staff_email, project_name in rows:
        payee_name = payout.payee_name_snapshot or worker_name or supplier_name or vanzai_staff_name or ""
        payee_type = payout.recipient_type or ("worker" if payout.worker_id else "supplier" if payout.supplier_id else "unknown")
        if payee_type == "worker":
            default_recipient_email = worker_email
        elif payee_type == "supplier":
            default_recipient_email = supplier_email
        elif payee_type == "vanzai_staff":
            default_recipient_email = vanzai_staff_email
        else:
            default_recipient_email = None
        latest_delivery = latest_deliveries_by_payout.get(payout.id)
        items.append(
            PayoutListItem(
                id=payout.id,
                payout_number=payout.id,
                payee_name=payee_name,
                payee_type=payee_type,
                recipient_type=payout.recipient_type,
                recipient_id=payout.recipient_id,
                payee_name_snapshot=payout.payee_name_snapshot,
                project_id=payout.project_id,
                project_name=project_name or "",
                period_key=payout.period_key,
                version=payout.version,
                status=payout.status,
                total_amount=payout.total_amount,
                approved_at=payout.approved_at,
                paid_at=payout.paid_at,
                has_pdf=bool(payout.pdf_object_key),
                pdf_storage_key=payout.pdf_object_key,
                default_recipient_email=default_recipient_email,
                last_delivery_status=latest_delivery.status if latest_delivery else None,
                last_delivered_at=latest_delivery.sent_at if latest_delivery else None,
                last_delivery_recipient=latest_delivery.recipient_email if latest_delivery else None,
            )
        )

    return PayoutListResponse(
        items=items,
        total=total,
        offset=query.offset,
        limit=query.limit,
    )


# ===========================
# マスタ一覧エンドポイント
# ===========================

@app.get("/api/workers", response_model=WorkerListResponse, tags=["Master"])
async def list_workers(
    query: WorkerListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者一覧取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker, Supplier

    sort_map = {
        "name": Worker.name,
        "furigana": Worker.furigana,
        "email": Worker.email,
        "created_at": Worker.created_at,
    }
    default_sort = Worker.name
    sort_col = sort_map.get(query.sort_by or "", default_sort) if query.sort_by else default_sort
    sort_expression = sort_col.desc() if query.sort_order == "desc" else sort_col.asc()

    stmt = (
        db.query(Worker, Supplier.name.label("supplier_name"))
        .outerjoin(Supplier, Worker.introducer_supplier_id == Supplier.id)
        .filter(Worker.deleted_at.is_(None))
    )
    if query.is_active is not None:
        stmt = stmt.filter(Worker.is_active == query.is_active)
    if query.supplier_id:
        stmt = stmt.filter(Worker.introducer_supplier_id == query.supplier_id)
    if query.search:
        pattern = f"%{query.search}%"
        stmt = stmt.filter(
            Worker.name.ilike(pattern)
            | Worker.furigana.ilike(pattern)
            | Worker.email.ilike(pattern)
            | Worker.phone.ilike(pattern)
        )

    total = stmt.count()
    rows = stmt.order_by(sort_expression, Worker.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        WorkerListItem(
            id=w.id,
            name=w.name,
            furigana=w.furigana,
            email=w.email,
            phone=w.phone,
            sole_proprietor_name=w.sole_proprietor_name,
            emergency_contact_name_kana=w.emergency_contact_name_kana,
            emergency_contact_phone=w.emergency_contact_phone,
            gender=w.gender,
            invoice_registration_status=w.invoice_registration_status,
            invoice_number=w.invoice_number,
            is_active=w.is_active,
            introducer_supplier_id=w.introducer_supplier_id,
            introducer_supplier_name=supplier_name,
            notes=w.notes,
            smoking_area_ok=w.smoking_area_ok,
            has_p_shirt=w.has_p_shirt,
            has_best=w.has_best,
            stores_training_done=w.stores_training_done,
            pioneer_training_done=w.pioneer_training_done,
            p_shirt_count=w.p_shirt_count,
            license_type=w.license_type,
        )
        for w, supplier_name in rows
    ]
    return WorkerListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/workers", response_model=WorkerListItem, tags=["Master"])
async def create_worker_master(
    request: WorkerCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者作成"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import Supplier, Worker

        supplier_name = None
        if request.introducer_supplier_id:
            supplier = db.get(Supplier, request.introducer_supplier_id)
            if not supplier or supplier.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Supplier not found")
            supplier_name = supplier.name

        worker = Worker(
            name=request.name.strip(),
            furigana=request.furigana.strip() if request.furigana else None,
            email=request.email.strip() if request.email else None,
            phone=request.phone.strip() if request.phone else None,
            sole_proprietor_name=request.sole_proprietor_name.strip() if request.sole_proprietor_name else None,
            emergency_contact_name_kana=request.emergency_contact_name_kana.strip() if request.emergency_contact_name_kana else None,
            emergency_contact_phone=request.emergency_contact_phone.strip() if request.emergency_contact_phone else None,
            gender=request.gender.strip() if request.gender else None,
            invoice_registration_status=request.invoice_registration_status.strip() if request.invoice_registration_status else None,
            invoice_number=request.invoice_number.strip() if request.invoice_number else None,
            introducer_supplier_id=request.introducer_supplier_id,
            notes=request.notes.strip() if request.notes else None,
            is_active=request.is_active,
            smoking_area_ok=request.smoking_area_ok,
            has_p_shirt=request.has_p_shirt,
            has_best=request.has_best,
            stores_training_done=request.stores_training_done,
            pioneer_training_done=request.pioneer_training_done,
            p_shirt_count=request.p_shirt_count,
            license_type=request.license_type,
        )
        db.add(worker)

        AuditService(db).log(
            "worker_created",
            target_type="worker",
            target_id=worker.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "name": worker.name,
                "furigana": worker.furigana,
                "email": worker.email,
                "introducer_supplier_id": worker.introducer_supplier_id,
                "is_active": worker.is_active,
            },
        )
        db.commit()
        db.refresh(worker)

        return WorkerListItem(
            id=worker.id,
            name=worker.name,
            furigana=worker.furigana,
            email=worker.email,
            phone=worker.phone,
            sole_proprietor_name=worker.sole_proprietor_name,
            emergency_contact_name_kana=worker.emergency_contact_name_kana,
            emergency_contact_phone=worker.emergency_contact_phone,
            gender=worker.gender,
            invoice_registration_status=worker.invoice_registration_status,
            invoice_number=worker.invoice_number,
            is_active=worker.is_active,
            introducer_supplier_id=worker.introducer_supplier_id,
            introducer_supplier_name=supplier_name,
            notes=worker.notes,
            smoking_area_ok=worker.smoking_area_ok,
            has_p_shirt=worker.has_p_shirt,
            has_best=worker.has_best,
            stores_training_done=worker.stores_training_done,
            pioneer_training_done=worker.pioneer_training_done,
            p_shirt_count=worker.p_shirt_count,
            license_type=worker.license_type,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="稼働者作成に失敗しました")


@app.put("/api/workers/{worker_id}", response_model=WorkerListItem, tags=["Master"])
async def update_worker_master(
    worker_id: str,
    request: WorkerUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者更新"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import Supplier, Worker

        worker = db.get(Worker, worker_id)
        if not worker or worker.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Worker not found")

        supplier_name = None
        if request.introducer_supplier_id:
            supplier = db.get(Supplier, request.introducer_supplier_id)
            if not supplier or supplier.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Supplier not found")
            supplier_name = supplier.name

        before_value = {
            "name": worker.name,
            "furigana": worker.furigana,
            "email": worker.email,
            "phone": worker.phone,
            "sole_proprietor_name": worker.sole_proprietor_name,
            "emergency_contact_name_kana": worker.emergency_contact_name_kana,
            "emergency_contact_phone": worker.emergency_contact_phone,
            "gender": worker.gender,
            "invoice_registration_status": worker.invoice_registration_status,
            "invoice_number": worker.invoice_number,
            "introducer_supplier_id": worker.introducer_supplier_id,
            "notes": worker.notes,
            "is_active": worker.is_active,
        }

        worker.name = request.name.strip()
        worker.furigana = request.furigana.strip() if request.furigana else None
        worker.email = request.email.strip() if request.email else None
        worker.phone = request.phone.strip() if request.phone else None
        worker.sole_proprietor_name = request.sole_proprietor_name.strip() if request.sole_proprietor_name else None
        worker.emergency_contact_name_kana = request.emergency_contact_name_kana.strip() if request.emergency_contact_name_kana else None
        worker.emergency_contact_phone = request.emergency_contact_phone.strip() if request.emergency_contact_phone else None
        worker.gender = request.gender.strip() if request.gender else None
        worker.invoice_registration_status = request.invoice_registration_status.strip() if request.invoice_registration_status else None
        worker.invoice_number = request.invoice_number.strip() if request.invoice_number else None
        worker.introducer_supplier_id = request.introducer_supplier_id
        worker.notes = request.notes.strip() if request.notes else None
        worker.is_active = request.is_active
        worker.smoking_area_ok = request.smoking_area_ok
        worker.has_p_shirt = request.has_p_shirt
        worker.has_best = request.has_best
        worker.stores_training_done = request.stores_training_done
        worker.pioneer_training_done = request.pioneer_training_done
        worker.p_shirt_count = request.p_shirt_count
        worker.license_type = request.license_type

        AuditService(db).log(
            "worker_updated",
            target_type="worker",
            target_id=worker.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "name": worker.name,
                "furigana": worker.furigana,
                "email": worker.email,
                "phone": worker.phone,
                "sole_proprietor_name": worker.sole_proprietor_name,
                "emergency_contact_name_kana": worker.emergency_contact_name_kana,
                "emergency_contact_phone": worker.emergency_contact_phone,
                "gender": worker.gender,
                "invoice_registration_status": worker.invoice_registration_status,
                "invoice_number": worker.invoice_number,
                "introducer_supplier_id": worker.introducer_supplier_id,
                "notes": worker.notes,
                "is_active": worker.is_active,
            },
        )
        db.commit()
        db.refresh(worker)

        return WorkerListItem(
            id=worker.id,
            name=worker.name,
            furigana=worker.furigana,
            email=worker.email,
            phone=worker.phone,
            sole_proprietor_name=worker.sole_proprietor_name,
            emergency_contact_name_kana=worker.emergency_contact_name_kana,
            emergency_contact_phone=worker.emergency_contact_phone,
            gender=worker.gender,
            invoice_registration_status=worker.invoice_registration_status,
            invoice_number=worker.invoice_number,
            is_active=worker.is_active,
            introducer_supplier_id=worker.introducer_supplier_id,
            introducer_supplier_name=supplier_name,
            notes=worker.notes,
            smoking_area_ok=worker.smoking_area_ok,
            has_p_shirt=worker.has_p_shirt,
            has_best=worker.has_best,
            stores_training_done=worker.stores_training_done,
            pioneer_training_done=worker.pioneer_training_done,
            p_shirt_count=worker.p_shirt_count,
            license_type=worker.license_type,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="稼働者更新に失敗しました")


@app.patch("/api/workers/{worker_id}/quals", response_model=WorkerListItem, tags=["Master"])
async def patch_worker_quals(
    worker_id: str,
    request: WorkerQualsUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者資格情報のみ更新"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)
        from src.models.master import Worker
        worker = db.get(Worker, worker_id)
        if not worker or worker.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Worker not found")

        worker.smoking_area_ok = request.smoking_area_ok
        worker.p_shirt_count = request.p_shirt_count
        worker.has_best = request.has_best
        worker.stores_training_done = request.stores_training_done
        worker.pioneer_training_done = request.pioneer_training_done
        worker.license_type = request.license_type

        AuditService(db).log(
            "worker_quals_updated",
            target_type="worker",
            target_id=worker.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "smoking_area_ok": worker.smoking_area_ok,
                "p_shirt_count": worker.p_shirt_count,
                "has_best": worker.has_best,
                "stores_training_done": worker.stores_training_done,
                "pioneer_training_done": worker.pioneer_training_done,
                "license_type": worker.license_type,
            },
        )
        db.commit()
        db.refresh(worker)

        supplier_name = None
        if worker.introducer_supplier_id:
            from src.models.master import Supplier
            sup = db.get(Supplier, worker.introducer_supplier_id)
            if sup:
                supplier_name = sup.name

        return WorkerListItem(
            id=worker.id,
            name=worker.name,
            furigana=worker.furigana,
            email=worker.email,
            phone=worker.phone,
            sole_proprietor_name=worker.sole_proprietor_name,
            emergency_contact_name_kana=worker.emergency_contact_name_kana,
            emergency_contact_phone=worker.emergency_contact_phone,
            gender=worker.gender,
            invoice_registration_status=worker.invoice_registration_status,
            invoice_number=worker.invoice_number,
            is_active=worker.is_active,
            introducer_supplier_id=worker.introducer_supplier_id,
            introducer_supplier_name=supplier_name,
            notes=worker.notes,
            smoking_area_ok=worker.smoking_area_ok,
            has_p_shirt=worker.has_p_shirt,
            has_best=worker.has_best,
            stores_training_done=worker.stores_training_done,
            pioneer_training_done=worker.pioneer_training_done,
            p_shirt_count=worker.p_shirt_count,
            license_type=worker.license_type,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="稼働者資格更新に失敗しました")


@app.delete("/api/workers/{worker_id}", status_code=204, tags=["Master"])
async def delete_worker_master(
    worker_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者削除（論理削除）"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import Worker

        worker = db.get(Worker, worker_id)
        if not worker or worker.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Worker not found")

        from datetime import datetime

        worker.deleted_at = datetime.utcnow()

        AuditService(db).log(
            "worker_deleted",
            target_type="worker",
            target_id=worker.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value={"name": worker.name, "email": worker.email},
        )
        db.commit()
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="稼働者削除に失敗しました")


@app.get("/api/suppliers", response_model=SupplierListResponse, tags=["Master"])
async def list_suppliers(
    query: SupplierListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """下請け一覧取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Supplier

    sort_map = {
        "name": Supplier.name,
        "created_at": Supplier.created_at,
    }
    default_sort = Supplier.name
    sort_col = sort_map.get(query.sort_by or "", default_sort) if query.sort_by else default_sort
    sort_expression = sort_col.desc() if query.sort_order == "desc" else sort_col.asc()

    stmt = db.query(Supplier).filter(Supplier.deleted_at.is_(None))
    if query.is_active is not None:
        stmt = stmt.filter(Supplier.is_active == query.is_active)
    if query.search:
        pattern = f"%{query.search}%"
        stmt = stmt.filter(Supplier.name.ilike(pattern))

    total = stmt.count()
    rows = stmt.order_by(sort_expression, Supplier.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        SupplierListItem(
            id=s.id,
            name=s.name,
            contact_email=s.contact_email,
            contact_phone=s.contact_phone,
            supplier_type=s.supplier_type,
            entity_type=s.entity_type,
            payout_terms_days=s.payout_terms_days,
            default_daily_price=s.default_daily_price,
            is_active=s.is_active,
            notes=s.notes,
        )
        for s in rows
    ]
    return SupplierListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/suppliers", response_model=SupplierListItem, tags=["Master"])
async def create_supplier_master(
    request: SupplierCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """下請け作成"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import Supplier

        supplier = Supplier(
            name=request.name.strip(),
            contact_email=request.contact_email.strip() if request.contact_email else None,
            contact_phone=request.contact_phone.strip() if request.contact_phone else None,
            supplier_type=request.supplier_type.strip() if request.supplier_type else None,
            entity_type=request.entity_type.strip() if request.entity_type else None,
            payout_terms_days=request.payout_terms_days,
            default_daily_price=request.default_daily_price,
            is_active=request.is_active,
            notes=request.notes.strip() if request.notes else None,
        )
        db.add(supplier)

        AuditService(db).log(
            "supplier_created",
            target_type="supplier",
            target_id=supplier.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "name": supplier.name,
                "contact_email": supplier.contact_email,
                "supplier_type": supplier.supplier_type,
                "entity_type": supplier.entity_type,
                "payout_terms_days": supplier.payout_terms_days,
                "default_daily_price": str(supplier.default_daily_price) if supplier.default_daily_price is not None else None,
                "is_active": supplier.is_active,
            },
        )
        db.commit()
        db.refresh(supplier)

        return SupplierListItem(
            id=supplier.id,
            name=supplier.name,
            contact_email=supplier.contact_email,
            contact_phone=supplier.contact_phone,
            supplier_type=supplier.supplier_type,
            entity_type=supplier.entity_type,
            payout_terms_days=supplier.payout_terms_days,
            default_daily_price=supplier.default_daily_price,
            is_active=supplier.is_active,
            notes=supplier.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="下請け作成に失敗しました")


@app.put("/api/suppliers/{supplier_id}", response_model=SupplierListItem, tags=["Master"])
async def update_supplier_master(
    supplier_id: str,
    request: SupplierUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """下請け更新"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import Supplier

        supplier = db.get(Supplier, supplier_id)
        if not supplier or supplier.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Supplier not found")

        before_value = {
            "name": supplier.name,
            "contact_email": supplier.contact_email,
            "contact_phone": supplier.contact_phone,
            "supplier_type": supplier.supplier_type,
            "entity_type": supplier.entity_type,
            "payout_terms_days": supplier.payout_terms_days,
            "default_daily_price": str(supplier.default_daily_price) if supplier.default_daily_price is not None else None,
            "is_active": supplier.is_active,
            "notes": supplier.notes,
        }

        supplier.name = request.name.strip()
        supplier.contact_email = request.contact_email.strip() if request.contact_email else None
        supplier.contact_phone = request.contact_phone.strip() if request.contact_phone else None
        supplier.supplier_type = request.supplier_type.strip() if request.supplier_type else None
        supplier.entity_type = request.entity_type.strip() if request.entity_type else None
        supplier.payout_terms_days = request.payout_terms_days
        supplier.default_daily_price = request.default_daily_price
        supplier.is_active = request.is_active
        supplier.notes = request.notes.strip() if request.notes else None

        AuditService(db).log(
            "supplier_updated",
            target_type="supplier",
            target_id=supplier.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "name": supplier.name,
                "contact_email": supplier.contact_email,
                "contact_phone": supplier.contact_phone,
                "supplier_type": supplier.supplier_type,
                "entity_type": supplier.entity_type,
                "payout_terms_days": supplier.payout_terms_days,
                "default_daily_price": str(supplier.default_daily_price) if supplier.default_daily_price is not None else None,
                "is_active": supplier.is_active,
                "notes": supplier.notes,
            },
        )
        db.commit()
        db.refresh(supplier)

        return SupplierListItem(
            id=supplier.id,
            name=supplier.name,
            contact_email=supplier.contact_email,
            contact_phone=supplier.contact_phone,
            supplier_type=supplier.supplier_type,
            entity_type=supplier.entity_type,
            payout_terms_days=supplier.payout_terms_days,
            default_daily_price=supplier.default_daily_price,
            is_active=supplier.is_active,
            notes=supplier.notes,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="下請け更新に失敗しました")


@app.get("/api/clients", response_model=ClientListResponse, tags=["Master"])
async def list_clients(
    query: ClientListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """クライアント一覧取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Client

    sort_map = {
        "name": Client.name,
        "code": Client.code,
    }
    default_sort = Client.name
    sort_col = sort_map.get(query.sort_by or "", default_sort) if query.sort_by else default_sort
    sort_expression = sort_col.desc() if query.sort_order == "desc" else sort_col.asc()

    stmt = db.query(Client).filter(Client.deleted_at.is_(None))
    if query.search:
        pattern = f"%{query.search}%"
        stmt = stmt.filter(Client.name.ilike(pattern) | Client.code.ilike(pattern))

    total = stmt.count()
    rows = stmt.order_by(sort_expression, Client.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        ClientListItem(
            id=c.id,
            name=c.name,
            code=c.code,
            contact_name=c.contact_name,
            contact_email=c.contact_email,
        )
        for c in rows
    ]
    return ClientListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/clients", response_model=ClientListItem, tags=["Master"])
async def create_client(
    request: ClientCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """クライアント作成"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import Client

        normalized_code = request.code.strip() if request.code else None
        if normalized_code:
            existing = (
                db.query(Client)
                .filter(Client.deleted_at.is_(None), func.lower(Client.code) == normalized_code.lower())
                .first()
            )
            if existing:
                raise HTTPException(status_code=400, detail="同じコードのクライアントが既に存在します")

        client = Client(
            name=request.name.strip(),
            code=normalized_code,
            address=request.address.strip() if request.address else None,
            contact_name=request.contact_name.strip() if request.contact_name else None,
            contact_email=request.contact_email.strip() if request.contact_email else None,
        )
        db.add(client)

        AuditService(db).log(
            "client_created",
            target_type="client",
            target_id=client.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "name": client.name,
                "code": client.code,
                "contact_name": client.contact_name,
                "contact_email": client.contact_email,
            },
        )
        db.commit()
        db.refresh(client)

        return ClientListItem(
            id=client.id,
            name=client.name,
            code=client.code,
            contact_name=client.contact_name,
            contact_email=client.contact_email,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="クライアント作成に失敗しました")


@app.get("/api/sites", response_model=SiteListResponse, tags=["Master"])
async def list_sites(
    query: SiteListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """現場一覧取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Site

    sort_map = {
        "name": Site.name,
        "code": Site.code,
    }
    default_sort = Site.name
    sort_col = sort_map.get(query.sort_by or "", default_sort) if query.sort_by else default_sort
    sort_expression = sort_col.desc() if query.sort_order == "desc" else sort_col.asc()

    stmt = db.query(Site).filter(Site.deleted_at.is_(None))
    if query.search:
        pattern = f"%{query.search}%"
        stmt = stmt.filter(Site.name.ilike(pattern) | Site.code.ilike(pattern))

    total = stmt.count()
    rows = stmt.order_by(sort_expression, Site.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        SiteListItem(
            id=s.id,
            name=s.name,
            code=s.code,
            address=s.address,
        )
        for s in rows
    ]
    return SiteListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/sites", response_model=SiteListItem, tags=["Master"])
async def create_site(
    request: SiteCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """現場作成"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import Site

        normalized_code = request.code.strip() if request.code else None
        if normalized_code:
            existing = (
                db.query(Site)
                .filter(Site.deleted_at.is_(None), func.lower(Site.code) == normalized_code.lower())
                .first()
            )
            if existing:
                raise HTTPException(status_code=400, detail="同じコードの現場が既に存在します")

        site = Site(
            name=request.name.strip(),
            code=normalized_code,
            address=request.address.strip() if request.address else None,
        )
        db.add(site)

        AuditService(db).log(
            "site_created",
            target_type="site",
            target_id=site.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "name": site.name,
                "code": site.code,
                "address": site.address,
            },
        )
        db.commit()
        db.refresh(site)

        return SiteListItem(
            id=site.id,
            name=site.name,
            code=site.code,
            address=site.address,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="現場作成に失敗しました")


@app.get("/api/project-types", response_model=ProjectTypeListResponse, tags=["Master"])
async def list_project_types(
    query: ProjectTypeListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """案件種別一覧取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import ProjectType

    sort_map = {
        "name": ProjectType.name,
        "code": ProjectType.code,
    }
    default_sort = ProjectType.name
    sort_col = sort_map.get(query.sort_by or "", default_sort) if query.sort_by else default_sort
    sort_expression = sort_col.desc() if query.sort_order == "desc" else sort_col.asc()

    stmt = db.query(ProjectType).filter(ProjectType.deleted_at.is_(None))
    if query.search:
        pattern = f"%{query.search}%"
        stmt = stmt.filter(ProjectType.name.ilike(pattern) | ProjectType.code.ilike(pattern))
    if query.category_level:
        stmt = stmt.filter(ProjectType.category_level == query.category_level)
    if query.parent_id:
        stmt = stmt.filter(ProjectType.parent_id == query.parent_id)
    if query.selectable_only:
        stmt = stmt.filter(ProjectType.category_level == "minor")

    total = stmt.count()
    rows = stmt.order_by(sort_expression, ProjectType.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        ProjectTypeListItem(
            id=pt.id,
            name=pt.name,
            code=pt.code,
            category_level=pt.category_level,
            parent_id=pt.parent_id,
            description=pt.description,
        )
        for pt in rows
    ]
    return ProjectTypeListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/project-types", response_model=ProjectTypeListItem, tags=["Master"])
async def create_project_type(
    request: ProjectTypeCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """案件種別作成"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import ProjectType

        normalized_code = request.code.strip() if request.code else None
        if normalized_code:
            existing = (
                db.query(ProjectType)
                .filter(ProjectType.deleted_at.is_(None), func.lower(ProjectType.code) == normalized_code.lower())
                .first()
            )
            if existing:
                raise HTTPException(status_code=400, detail="同じコードの案件種別が既に存在します")

        parent_id = request.parent_id
        if request.category_level == "major":
            parent_id = None
        elif parent_id:
            parent = db.get(ProjectType, parent_id)
            if not parent or parent.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Parent project type not found")

        project_type = ProjectType(
            name=request.name.strip(),
            code=normalized_code,
            category_level=request.category_level,
            parent_id=parent_id,
            description=request.description.strip() if request.description else None,
        )
        db.add(project_type)

        AuditService(db).log(
            "project_type_created",
            target_type="project_type",
            target_id=project_type.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "name": project_type.name,
                "code": project_type.code,
                "category_level": project_type.category_level,
                "parent_id": project_type.parent_id,
                "description": project_type.description,
            },
        )
        db.commit()
        db.refresh(project_type)

        return ProjectTypeListItem(
            id=project_type.id,
            name=project_type.name,
            code=project_type.code,
            category_level=project_type.category_level,
            parent_id=project_type.parent_id,
            description=project_type.description,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="案件種別作成に失敗しました")


@app.get("/api/project-types/tree", response_model=ProjectTypeTreeResponse, tags=["Master"])
async def list_project_type_tree(
    selectable_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """案件種別ツリー取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import ProjectType

    rows = (
        db.query(ProjectType)
        .filter(ProjectType.deleted_at.is_(None))
        .order_by(ProjectType.name.asc(), ProjectType.id.asc())
        .all()
    )

    children_by_parent: dict[str | None, list[ProjectType]] = {}
    for row in rows:
        children_by_parent.setdefault(row.parent_id, []).append(row)

    def build_node(row: ProjectType) -> ProjectTypeTreeItem | None:
        child_nodes = [node for child in children_by_parent.get(row.id, []) if (node := build_node(child)) is not None]
        selectable = row.category_level == "minor"
        if selectable_only and not selectable and not child_nodes:
            return None
        return ProjectTypeTreeItem(
            id=row.id,
            name=row.name,
            code=row.code,
            category_level=row.category_level,
            parent_id=row.parent_id,
            description=row.description,
            selectable=selectable,
            children=child_nodes,
        )

    items = [node for root in children_by_parent.get(None, []) if (node := build_node(root)) is not None]
    return ProjectTypeTreeResponse(items=items)


@app.post("/api/registration-links", response_model=RegistrationLinkResponse, tags=["Registration Requests"])
async def create_registration_link(
    payload: RegistrationLinkCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """公開登録リンク作成"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        request_record = RegistrationRequest(
            id=generate_ulid(),
            request_type=payload.request_type,
            status="draft",
            source_type="public_form",
        )
        db.add(request_record)
        token, pin = _issue_registration_link(
            request_record,
            request_type=payload.request_type,
            expires_in_days=payload.expires_in_days,
            notes=payload.notes,
        )

        AuditService(db).log(
            "registration_link_created",
            target_type="registration_request",
            target_id=request_record.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "request_type": request_record.request_type,
                "status": request_record.status,
                "expires_at": request_record.expires_at.isoformat() if request_record.expires_at else None,
            },
        )
        db.commit()
        db.refresh(request_record)
        return _build_registration_link_response(request_record, token, pin)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="公開登録リンク作成に失敗しました")


@app.post("/api/registration-links/{request_id}/reset-pin-lock", response_model=RegistrationRequestDetailResponse, tags=["Registration Requests"])
async def reset_registration_link_pin_lock(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """公開登録リンクの PIN ロック解除"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        request_record = db.get(RegistrationRequest, request_id)
        if not request_record or request_record.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Registration request not found")
        if request_record.source_type != "public_form":
            raise HTTPException(status_code=400, detail="公開登録リンクではありません")

        before_value = {
            "failed_attempts": request_record.failed_attempts,
            "locked_at": request_record.locked_at.isoformat() if request_record.locked_at else None,
        }
        request_record.failed_attempts = 0
        request_record.locked_at = None

        AuditService(db).log(
            "registration_link_pin_lock_reset",
            target_type="registration_request",
            target_id=request_record.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={"failed_attempts": 0, "locked_at": None},
        )
        db.commit()
        db.refresh(request_record)
        return _registration_detail_response(db, request_record)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="公開登録リンクのロック解除に失敗しました")


@app.post("/api/registration-links/{request_id}/reissue", response_model=RegistrationLinkResponse, tags=["Registration Requests"])
async def reissue_registration_link(
    request_id: str,
    payload: RegistrationLinkCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """公開登録リンク再発行"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        request_record = db.get(RegistrationRequest, request_id)
        if not request_record or request_record.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Registration request not found")
        if request_record.source_type != "public_form":
            raise HTTPException(status_code=400, detail="公開登録リンクではありません")
        if request_record.request_type != payload.request_type:
            raise HTTPException(status_code=400, detail="request_type は既存リンクと一致させてください")
        if request_record.status != "link_issued":
            raise HTTPException(status_code=409, detail="未送信リンクのみ再発行できます")

        token, pin = _issue_registration_link(
            request_record,
            request_type=request_record.request_type,
            expires_in_days=payload.expires_in_days,
            notes=payload.notes,
        )

        AuditService(db).log(
            "registration_link_reissued",
            target_type="registration_request",
            target_id=request_record.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "request_type": request_record.request_type,
                "status": request_record.status,
                "expires_at": request_record.expires_at.isoformat() if request_record.expires_at else None,
            },
        )
        db.commit()
        db.refresh(request_record)
        return _build_registration_link_response(request_record, token, pin)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="公開登録リンク再発行に失敗しました")


@app.get("/public/registrations/{form_type}", response_model=PublicRegistrationAccessResponse, tags=["Public Registrations"])
async def access_public_registration(
    form_type: str,
    token: str = Query(..., min_length=8),
    pin: str = Query(..., min_length=4),
    db: Session = Depends(get_db),
):
    """公開登録フォームアクセス"""
    request_record = _load_public_registration_request(db, form_type, token)
    _assert_public_registration_access(db, request_record, pin)
    db.commit()
    db.refresh(request_record)
    return PublicRegistrationAccessResponse(
        request_id=request_record.id,
        request_type=request_record.request_type,
        status=request_record.status,
        expires_at=request_record.expires_at,
        failed_attempts=request_record.failed_attempts,
        detail_data=_registration_detail_data(db, request_record),
        files=_registration_file_items(db, request_record.id),
    )


@app.post("/public/registrations/{form_type}/files", response_model=PublicRegistrationFileUploadResponse, tags=["Public Registrations"])
async def upload_public_registration_file(
    form_type: str,
    token: str = Form(...),
    pin: str = Form(...),
    document_type: str = Form(...),
    document_part: str = Form("single"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """公開登録フォームの添付ファイルアップロード"""
    try:
        request_record = _load_public_registration_request(db, form_type, token)
        _assert_public_registration_access(db, request_record, pin)
        file_record = await _store_registration_request_file(
            request_record=request_record,
            document_type=document_type,
            document_part=document_part,
            upload_file=file,
            db=db,
        )
        AuditService(db).log(
            "registration_request_file_uploaded",
            target_type="registration_request_file",
            target_id=file_record.id,
            after_value={
                "request_id": request_record.id,
                "document_type": file_record.document_type,
                "document_part": file_record.document_part,
                "mime_type": file_record.mime_type,
                "size_bytes": file_record.size_bytes,
            },
            extra_metadata={"request_type": request_record.request_type, "source_type": request_record.source_type},
        )
        db.commit()
        db.refresh(file_record)
        return PublicRegistrationFileUploadResponse(
            file=_registration_file_item(file_record),
            files=_registration_file_items(db, request_record.id),
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="添付ファイルのアップロードに失敗しました")


@app.post("/public/registrations/worker", response_model=PublicRegistrationSubmitResponse, tags=["Public Registrations"])
async def submit_public_worker_registration(
    payload: PublicWorkerRegistrationSubmitRequest,
    raw_request: Request,
    db: Session = Depends(get_db),
):
    """稼働者公開登録フォーム送信"""
    try:
        request_record = _load_public_registration_request(db, "worker", payload.token)
        _assert_public_registration_access(db, request_record, payload.pin)
        response = _submit_public_registration(
            db,
            request_record=request_record,
            payload_data=payload.model_dump(exclude={"token", "pin"}),
            submitted_ip=raw_request.client.host if raw_request.client else None,
            user_agent=raw_request.headers.get("user-agent"),
        )
        AuditService(db).log(
            "registration_request_submitted",
            target_type="registration_request",
            target_id=request_record.id,
            after_value={"status": response.status, "dedupe_key": response.dedupe_key},
            extra_metadata={"request_type": request_record.request_type, "source_type": request_record.source_type},
        )
        db.commit()
        return response
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="公開登録フォーム送信に失敗しました")


@app.post("/public/registrations/supplier-individual", response_model=PublicRegistrationSubmitResponse, tags=["Public Registrations"])
async def submit_public_supplier_individual_registration(
    payload: PublicSupplierIndividualRegistrationSubmitRequest,
    raw_request: Request,
    db: Session = Depends(get_db),
):
    """個人下請け公開登録フォーム送信"""
    try:
        request_record = _load_public_registration_request(db, "supplier-individual", payload.token)
        _assert_public_registration_access(db, request_record, payload.pin)
        response = _submit_public_registration(
            db,
            request_record=request_record,
            payload_data=payload.model_dump(exclude={"token", "pin"}),
            submitted_ip=raw_request.client.host if raw_request.client else None,
            user_agent=raw_request.headers.get("user-agent"),
        )
        AuditService(db).log(
            "registration_request_submitted",
            target_type="registration_request",
            target_id=request_record.id,
            after_value={"status": response.status, "dedupe_key": response.dedupe_key},
            extra_metadata={"request_type": request_record.request_type, "source_type": request_record.source_type},
        )
        db.commit()
        return response
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="公開登録フォーム送信に失敗しました")


@app.post("/public/registrations/supplier-corporation", response_model=PublicRegistrationSubmitResponse, tags=["Public Registrations"])
async def submit_public_supplier_corporation_registration(
    payload: PublicSupplierCorporationRegistrationSubmitRequest,
    raw_request: Request,
    db: Session = Depends(get_db),
):
    """法人下請け公開登録フォーム送信"""
    try:
        request_record = _load_public_registration_request(db, "supplier-corporation", payload.token)
        _assert_public_registration_access(db, request_record, payload.pin)
        response = _submit_public_registration(
            db,
            request_record=request_record,
            payload_data=payload.model_dump(exclude={"token", "pin"}),
            submitted_ip=raw_request.client.host if raw_request.client else None,
            user_agent=raw_request.headers.get("user-agent"),
        )
        AuditService(db).log(
            "registration_request_submitted",
            target_type="registration_request",
            target_id=request_record.id,
            after_value={"status": response.status, "dedupe_key": response.dedupe_key},
            extra_metadata={"request_type": request_record.request_type, "source_type": request_record.source_type},
        )
        db.commit()
        return response
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="公開登録フォーム送信に失敗しました")


@app.post("/public/registrations/introducer-identity", response_model=PublicRegistrationSubmitResponse, tags=["Public Registrations"])
async def submit_public_introducer_identity_registration(
    payload: PublicIntroducerIdentityRegistrationSubmitRequest,
    raw_request: Request,
    db: Session = Depends(get_db),
):
    """紹介者本人確認公開フォーム送信"""
    try:
        request_record = _load_public_registration_request(db, "introducer-identity", payload.token)
        _assert_public_registration_access(db, request_record, payload.pin)
        response = _submit_public_registration(
            db,
            request_record=request_record,
            payload_data=payload.model_dump(exclude={"token", "pin"}),
            submitted_ip=raw_request.client.host if raw_request.client else None,
            user_agent=raw_request.headers.get("user-agent"),
        )
        AuditService(db).log(
            "registration_request_submitted",
            target_type="registration_request",
            target_id=request_record.id,
            after_value={"status": response.status, "dedupe_key": response.dedupe_key},
            extra_metadata={"request_type": request_record.request_type, "source_type": request_record.source_type},
        )
        db.commit()
        return response
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="公開登録フォーム送信に失敗しました")


@app.get("/api/registration-requests", response_model=RegistrationRequestListResponse, tags=["Registration Requests"])
async def list_registration_requests(
    query: RegistrationRequestListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """登録申請一覧取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    sort_map = {
        "submitted_at": RegistrationRequest.submitted_at,
        "reviewed_at": RegistrationRequest.reviewed_at,
        "created_at": RegistrationRequest.created_at,
        "status": RegistrationRequest.status,
        "request_type": RegistrationRequest.request_type,
    }
    default_sort = RegistrationRequest.created_at
    sort_col = sort_map.get(query.sort_by or "", default_sort) if query.sort_by else default_sort
    sort_expression = sort_col.desc() if query.sort_order == "desc" else sort_col.asc()

    stmt = db.query(RegistrationRequest).filter(RegistrationRequest.deleted_at.is_(None))
    if query.request_type:
        stmt = stmt.filter(RegistrationRequest.request_type == query.request_type)
    if query.status:
        stmt = stmt.filter(RegistrationRequest.status == query.status)
    if query.source_type:
        stmt = stmt.filter(RegistrationRequest.source_type == query.source_type)
    if query.search:
        pattern = f"%{query.search}%"
        stmt = stmt.filter(
            or_(
                RegistrationRequest.dedupe_key.ilike(pattern),
                RegistrationRequest.notes.ilike(pattern),
                RegistrationRequest.request_type.ilike(pattern),
            )
        )

    total = stmt.count()
    rows = stmt.order_by(sort_expression, RegistrationRequest.id.desc()).offset(query.offset).limit(query.limit).all()
    items = [_registration_list_item(db, row) for row in rows]
    return RegistrationRequestListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.get("/api/registration-requests/{request_id}", response_model=RegistrationRequestDetailResponse, tags=["Registration Requests"])
async def get_registration_request(
    request_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """登録申請詳細取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    request_record = db.get(RegistrationRequest, request_id)
    if not request_record or request_record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Registration request not found")

    return _registration_detail_response(db, request_record)


@app.post("/api/registration-requests/{request_id}/approve", response_model=RegistrationRequestDetailResponse, tags=["Registration Requests"])
async def approve_registration_request(
    request_id: str,
    payload: RegistrationRequestApproveRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """登録申請承認"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        request_record = db.get(RegistrationRequest, request_id)
        if not request_record or request_record.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Registration request not found")
        if request_record.superseded_by_request_id:
            raise HTTPException(status_code=409, detail="この申請は後続申請により superseded 済みです")
        if request_record.status == "approved":
            raise HTTPException(status_code=409, detail="この申請は既に承認済みです")
        if request_record.status == "rejected":
            raise HTTPException(status_code=409, detail="この申請は既に却下済みです")

        before_value = {
            "status": request_record.status,
            "approved_target_type": request_record.approved_target_type,
            "approved_target_id": request_record.approved_target_id,
            "notes": request_record.notes,
        }

        _validate_registration_approval_resolution(db, request_record, payload)
        _approve_registration_request(db, request_record, payload)
        request_record.reviewed_by = current_user.id

        AuditService(db).log(
            "registration_request_approved",
            target_type="registration_request",
            target_id=request_record.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "status": request_record.status,
                "approved_target_type": request_record.approved_target_type,
                "approved_target_id": request_record.approved_target_id,
                "reviewed_by": request_record.reviewed_by,
                "reviewed_at": request_record.reviewed_at.isoformat() if request_record.reviewed_at else None,
            },
            extra_metadata={
                "request_type": request_record.request_type,
                "source_type": request_record.source_type,
            },
        )
        db.commit()
        db.refresh(request_record)
        return _registration_detail_response(db, request_record)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="登録申請承認に失敗しました")


@app.post("/api/registration-requests/{request_id}/reject", response_model=RegistrationRequestDetailResponse, tags=["Registration Requests"])
async def reject_registration_request(
    request_id: str,
    payload: RegistrationRequestRejectRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """登録申請却下"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        request_record = db.get(RegistrationRequest, request_id)
        if not request_record or request_record.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Registration request not found")
        if request_record.status == "approved":
            raise HTTPException(status_code=409, detail="承認済み申請は却下できません")
        if request_record.status == "rejected":
            raise HTTPException(status_code=409, detail="この申請は既に却下済みです")

        before_value = {
            "status": request_record.status,
            "notes": request_record.notes,
        }

        _reject_registration_request(request_record, payload)
        request_record.reviewed_by = current_user.id

        AuditService(db).log(
            "registration_request_rejected",
            target_type="registration_request",
            target_id=request_record.id,
            actor=current_user.username,
            actor_role=current_user.role,
            before_value=before_value,
            after_value={
                "status": request_record.status,
                "reviewed_by": request_record.reviewed_by,
                "reviewed_at": request_record.reviewed_at.isoformat() if request_record.reviewed_at else None,
                "notes": request_record.notes,
            },
            reason=payload.reason,
            extra_metadata={
                "request_type": request_record.request_type,
                "source_type": request_record.source_type,
            },
        )
        db.commit()
        db.refresh(request_record)
        return _registration_detail_response(db, request_record)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="登録申請却下に失敗しました")


@app.get("/api/registration-requests/{request_id}/files/{file_id}", response_class=FileResponse, tags=["Registration Requests"])
async def download_registration_request_file(
    request_id: str,
    file_id: str,
    reason: str = Query(..., min_length=1, max_length=500),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """登録申請添付ファイルをダウンロードする"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    request_record = db.get(RegistrationRequest, request_id)
    if not request_record or request_record.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Registration request not found")

    file_record = db.get(RegistrationRequestFile, file_id)
    if not file_record or file_record.request_id != request_id:
        raise HTTPException(status_code=404, detail="Registration request file not found")
    if file_record.deleted_at is not None:
        raise HTTPException(status_code=410, detail="Registration request file already deleted")

    storage = _registration_file_storage()
    if not storage.exists(file_record.storage_key):
        raise HTTPException(status_code=404, detail="Stored file not found")

    AuditService(db).log(
        "registration_request_file_downloaded",
        target_type="registration_request_file",
        target_id=file_record.id,
        actor=current_user.username,
        actor_role=current_user.role,
        reason=reason.strip(),
        after_value={
            "request_id": request_id,
            "document_type": file_record.document_type,
            "document_part": file_record.document_part,
            "original_filename": file_record.original_filename,
        },
    )
    db.commit()

    file_path = storage.resolve_path(file_record.storage_key)
    media_type, _ = mimetypes.guess_type(file_record.original_filename)
    return FileResponse(
        path=file_path,
        filename=file_record.original_filename,
        media_type=media_type or file_record.mime_type or "application/octet-stream",
    )


@app.get("/api/roles", response_model=RoleListResponse, tags=["Master"])
async def list_roles(
    query: RoleListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """役割一覧取得"""
    try:
        check_permission(current_user, Permission.MASTER_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Role

    sort_map = {
        "name": Role.name,
        "code": Role.code,
    }
    default_sort = Role.name
    sort_col = sort_map.get(query.sort_by or "", default_sort) if query.sort_by else default_sort
    sort_expression = sort_col.desc() if query.sort_order == "desc" else sort_col.asc()

    stmt = db.query(Role).filter(Role.deleted_at.is_(None))
    if query.search:
        pattern = f"%{query.search}%"
        stmt = stmt.filter(Role.name.ilike(pattern) | Role.code.ilike(pattern))

    total = stmt.count()
    rows = stmt.order_by(sort_expression, Role.id.desc()).offset(query.offset).limit(query.limit).all()

    items = [
        RoleListItem(
            id=r.id,
            name=r.name,
            code=r.code,
            description=r.description,
        )
        for r in rows
    ]
    return RoleListResponse(items=items, total=total, offset=query.offset, limit=query.limit)


@app.post("/api/roles", response_model=RoleListItem, tags=["Master"])
async def create_role_master(
    request: RoleCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """役割作成"""
    try:
        check_permission(current_user, Permission.MASTER_WRITE)

        from src.models.master import Role

        normalized_code = request.code.strip() if request.code else None
        if normalized_code:
            existing = (
                db.query(Role)
                .filter(Role.deleted_at.is_(None), func.lower(Role.code) == normalized_code.lower())
                .first()
            )
            if existing:
                raise HTTPException(status_code=400, detail="同じコードの役割が既に存在します")

        role = Role(
            name=request.name.strip(),
            code=normalized_code,
            description=request.description.strip() if request.description else None,
        )
        db.add(role)

        AuditService(db).log(
            "role_created",
            target_type="role",
            target_id=role.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "name": role.name,
                "code": role.code,
                "description": role.description,
            },
        )
        db.commit()
        db.refresh(role)

        return RoleListItem(
            id=role.id,
            name=role.name,
            code=role.code,
            description=role.description,
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="役割作成に失敗しました")


# ===========================
# VANZAI担当者エンドポイント
# ===========================

@app.get("/api/vanzai-staff", response_model=VanzaiStaffListResponse, tags=["Master"])
async def list_vanzai_staff(
    query: VanzaiStaffListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """VANZAI担当者一覧"""
    check_permission(current_user, Permission.MASTER_READ)
    q = (
        db.query(VanzaiStaff, Worker.name.label("linked_worker_name"))
        .outerjoin(Worker, VanzaiStaff.linked_worker_id == Worker.id)
        .filter(VanzaiStaff.deleted_at.is_(None))
    )
    if query.search:
        like = f"%{query.search}%"
        q = q.filter(VanzaiStaff.name.ilike(like) | VanzaiStaff.email.ilike(like))
    if query.is_active is not None:
        q = q.filter(VanzaiStaff.is_active == query.is_active)
    total = q.count()
    items = q.order_by(VanzaiStaff.name).offset((query.page - 1) * query.limit).limit(query.limit).all()
    return VanzaiStaffListResponse(
        items=[VanzaiStaffItem(
            id=staff.id,
            name=staff.name,
            role=staff.role,
            linked_worker_id=staff.linked_worker_id,
            linked_worker_name=linked_worker_name,
            playing_manager_fee_type=staff.playing_manager_fee_type,
            playing_manager_fixed_fee=staff.playing_manager_fixed_fee,
            phone=staff.phone,
            email=staff.email,
            is_active=staff.is_active,
            notes=staff.notes,
        ) for staff, linked_worker_name in items],
        total=total, page=query.page, limit=query.limit,
    )


@app.post("/api/vanzai-staff", response_model=VanzaiStaffItem, status_code=201, tags=["Master"])
async def create_vanzai_staff(
    body: VanzaiStaffCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """VANZAI担当者作成"""
    check_permission(current_user, Permission.MASTER_WRITE)
    linked_worker = None
    if body.linked_worker_id:
        linked_worker = db.get(Worker, body.linked_worker_id)
        if not linked_worker or linked_worker.deleted_at is not None:
            raise HTTPException(status_code=400, detail="対応する稼働者が見つかりません")
    staff = VanzaiStaff(
        id=generate_ulid(), name=body.name, role=body.role, linked_worker_id=body.linked_worker_id,
        playing_manager_fee_type=body.playing_manager_fee_type,
        playing_manager_fixed_fee=body.playing_manager_fixed_fee,
        phone=body.phone, email=body.email, is_active=body.is_active, notes=body.notes,
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return VanzaiStaffItem(
        id=staff.id, name=staff.name, role=staff.role, linked_worker_id=staff.linked_worker_id,
        linked_worker_name=linked_worker.name if linked_worker else None,
        playing_manager_fee_type=staff.playing_manager_fee_type,
        playing_manager_fixed_fee=staff.playing_manager_fixed_fee,
        phone=staff.phone,
        email=staff.email, is_active=staff.is_active, notes=staff.notes,
    )


@app.put("/api/vanzai-staff/{staff_id}", response_model=VanzaiStaffItem, tags=["Master"])
async def update_vanzai_staff(
    staff_id: str,
    body: VanzaiStaffUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """VANZAI担当者更新"""
    check_permission(current_user, Permission.MASTER_WRITE)
    staff = db.query(VanzaiStaff).filter(VanzaiStaff.id == staff_id, VanzaiStaff.deleted_at.is_(None)).first()
    if not staff:
        raise HTTPException(status_code=404, detail="VANZAI担当者が見つかりません")
    linked_worker = None
    if body.linked_worker_id:
        linked_worker = db.get(Worker, body.linked_worker_id)
        if not linked_worker or linked_worker.deleted_at is not None:
            raise HTTPException(status_code=400, detail="対応する稼働者が見つかりません")
    staff.name = body.name
    staff.role = body.role
    staff.linked_worker_id = body.linked_worker_id
    staff.playing_manager_fee_type = body.playing_manager_fee_type
    staff.playing_manager_fixed_fee = body.playing_manager_fixed_fee
    staff.phone = body.phone
    staff.email = body.email
    staff.is_active = body.is_active
    staff.notes = body.notes
    db.commit()
    db.refresh(staff)
    return VanzaiStaffItem(
        id=staff.id, name=staff.name, role=staff.role, linked_worker_id=staff.linked_worker_id,
        linked_worker_name=linked_worker.name if linked_worker else None,
        playing_manager_fee_type=staff.playing_manager_fee_type,
        playing_manager_fixed_fee=staff.playing_manager_fixed_fee,
        phone=staff.phone,
        email=staff.email, is_active=staff.is_active, notes=staff.notes,
    )


# ===========================
# クライアント担当者エンドポイント
# ===========================

@app.get("/api/clients/{client_id}/staff", response_model=ClientStaffListResponse, tags=["Master"])
async def list_client_staff(
    client_id: str,
    query: ClientStaffListQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """クライアント担当者一覧"""
    check_permission(current_user, Permission.MASTER_READ)
    q = db.query(ClientStaff).filter(
        ClientStaff.client_id == client_id,
        ClientStaff.deleted_at.is_(None),
    )
    if query.is_active is not None:
        q = q.filter(ClientStaff.is_active == query.is_active)
    total = q.count()
    items = q.order_by(ClientStaff.name).offset((query.page - 1) * query.limit).limit(query.limit).all()
    return ClientStaffListResponse(
        items=[ClientStaffItem(
            id=r.id, client_id=r.client_id, name=r.name, role=r.role,
            phone=r.phone, email=r.email, is_active=r.is_active, notes=r.notes,
        ) for r in items],
        total=total, page=query.page, limit=query.limit,
    )


@app.post("/api/clients/{client_id}/staff", response_model=ClientStaffItem, status_code=201, tags=["Master"])
async def create_client_staff(
    client_id: str,
    body: ClientStaffCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """クライアント担当者作成"""
    check_permission(current_user, Permission.MASTER_WRITE)
    from src.models.master import Client
    client = db.query(Client).filter(Client.id == client_id, Client.deleted_at.is_(None)).first()
    if not client:
        raise HTTPException(status_code=404, detail="クライアントが見つかりません")
    staff = ClientStaff(
        id=generate_ulid(), client_id=client_id, name=body.name, role=body.role,
        phone=body.phone, email=body.email, is_active=body.is_active, notes=body.notes,
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return ClientStaffItem(
        id=staff.id, client_id=staff.client_id, name=staff.name, role=staff.role,
        phone=staff.phone, email=staff.email, is_active=staff.is_active, notes=staff.notes,
    )


@app.put("/api/clients/{client_id}/staff/{staff_member_id}", response_model=ClientStaffItem, tags=["Master"])
async def update_client_staff(
    client_id: str,
    staff_member_id: str,
    body: ClientStaffUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """クライアント担当者更新"""
    check_permission(current_user, Permission.MASTER_WRITE)
    staff = db.query(ClientStaff).filter(
        ClientStaff.id == staff_member_id,
        ClientStaff.client_id == client_id,
        ClientStaff.deleted_at.is_(None),
    ).first()
    if not staff:
        raise HTTPException(status_code=404, detail="クライアント担当者が見つかりません")
    staff.name = body.name
    staff.role = body.role
    staff.phone = body.phone
    staff.email = body.email
    staff.is_active = body.is_active
    staff.notes = body.notes
    db.commit()
    db.refresh(staff)
    return ClientStaffItem(
        id=staff.id, client_id=staff.client_id, name=staff.name, role=staff.role,
        phone=staff.phone, email=staff.email, is_active=staff.is_active, notes=staff.notes,
    )


# ===========================
# 稼働者口座エンドポイント
# ===========================

@app.get("/api/workers/{worker_id}/bank-accounts", response_model=WorkerBankAccountListResponse, tags=["Master"])
async def list_worker_bank_accounts(
    worker_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者の振込先口座一覧"""
    check_permission(current_user, Permission.MASTER_READ)
    items = db.query(WorkerBankAccount).filter(
        WorkerBankAccount.worker_id == worker_id,
        WorkerBankAccount.deleted_at.is_(None),
    ).order_by(WorkerBankAccount.effective_from.desc()).all()
    return WorkerBankAccountListResponse(
        items=[WorkerBankAccountItem(
            id=r.id, worker_id=r.worker_id, bank_name=r.bank_name,
            branch_name=r.branch_name, branch_code=r.branch_code,
            account_type=r.account_type, account_number=r.account_number,
            account_holder_kana=r.account_holder_kana,
            transfer_destination_name=r.transfer_destination_name,
            effective_from=r.effective_from, effective_until=r.effective_until,
            is_primary=r.is_primary,
        ) for r in items],
        total=len(items),
    )


@app.post("/api/workers/{worker_id}/bank-accounts", response_model=WorkerBankAccountItem, status_code=201, tags=["Master"])
async def create_worker_bank_account(
    worker_id: str,
    body: WorkerBankAccountCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者の振込先口座登録"""
    check_permission(current_user, Permission.MASTER_WRITE)
    from src.models.master import Worker
    worker = db.query(Worker).filter(Worker.id == worker_id, Worker.deleted_at.is_(None)).first()
    if not worker:
        raise HTTPException(status_code=404, detail="稼働者が見つかりません")
    account = WorkerBankAccount(
        id=generate_ulid(), worker_id=worker_id, bank_name=body.bank_name,
        branch_name=body.branch_name, branch_code=body.branch_code,
        account_type=body.account_type, account_number=body.account_number,
        account_holder_kana=body.account_holder_kana,
        transfer_destination_name=body.transfer_destination_name,
        effective_from=body.effective_from, effective_until=body.effective_until,
        is_primary=body.is_primary,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return WorkerBankAccountItem(
        id=account.id, worker_id=account.worker_id, bank_name=account.bank_name,
        branch_name=account.branch_name, branch_code=account.branch_code,
        account_type=account.account_type, account_number=account.account_number,
        account_holder_kana=account.account_holder_kana,
        transfer_destination_name=account.transfer_destination_name,
        effective_from=account.effective_from, effective_until=account.effective_until,
        is_primary=account.is_primary,
    )


@app.put("/api/workers/{worker_id}/bank-accounts/{account_id}", response_model=WorkerBankAccountItem, tags=["Master"])
async def update_worker_bank_account(
    worker_id: str,
    account_id: str,
    body: WorkerBankAccountUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """稼働者の振込先口座更新"""
    check_permission(current_user, Permission.MASTER_WRITE)
    account = db.query(WorkerBankAccount).filter(
        WorkerBankAccount.id == account_id,
        WorkerBankAccount.worker_id == worker_id,
        WorkerBankAccount.deleted_at.is_(None),
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="口座情報が見つかりません")
    account.bank_name = body.bank_name
    account.branch_name = body.branch_name
    account.branch_code = body.branch_code
    account.account_type = body.account_type
    account.account_number = body.account_number
    account.account_holder_kana = body.account_holder_kana
    account.transfer_destination_name = body.transfer_destination_name
    account.effective_from = body.effective_from
    account.effective_until = body.effective_until
    account.is_primary = body.is_primary
    db.commit()
    db.refresh(account)
    return WorkerBankAccountItem(
        id=account.id, worker_id=account.worker_id, bank_name=account.bank_name,
        branch_name=account.branch_name, branch_code=account.branch_code,
        account_type=account.account_type, account_number=account.account_number,
        account_holder_kana=account.account_holder_kana,
        transfer_destination_name=account.transfer_destination_name,
        effective_from=account.effective_from, effective_until=account.effective_until,
        is_primary=account.is_primary,
    )


# ===========================
# 下請け口座エンドポイント
# ===========================

@app.get("/api/suppliers/{supplier_id}/bank-accounts", response_model=SupplierBankAccountListResponse, tags=["Master"])
async def list_supplier_bank_accounts(
    supplier_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """下請けの振込先口座一覧"""
    check_permission(current_user, Permission.MASTER_READ)
    items = db.query(SupplierBankAccount).filter(
        SupplierBankAccount.supplier_id == supplier_id,
        SupplierBankAccount.deleted_at.is_(None),
    ).order_by(SupplierBankAccount.effective_from.desc()).all()
    return SupplierBankAccountListResponse(
        items=[SupplierBankAccountItem(
            id=r.id, supplier_id=r.supplier_id, bank_name=r.bank_name,
            branch_name=r.branch_name, branch_code=r.branch_code,
            account_type=r.account_type, account_number=r.account_number,
            account_holder_kana=r.account_holder_kana,
            transfer_destination_name=r.transfer_destination_name,
            effective_from=r.effective_from, effective_until=r.effective_until,
            is_primary=r.is_primary,
        ) for r in items],
        total=len(items),
    )


@app.post("/api/suppliers/{supplier_id}/bank-accounts", response_model=SupplierBankAccountItem, status_code=201, tags=["Master"])
async def create_supplier_bank_account(
    supplier_id: str,
    body: SupplierBankAccountCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """下請けの振込先口座登録"""
    check_permission(current_user, Permission.MASTER_WRITE)
    from src.models.master import Supplier
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id, Supplier.deleted_at.is_(None)).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="下請けが見つかりません")
    account = SupplierBankAccount(
        id=generate_ulid(), supplier_id=supplier_id, bank_name=body.bank_name,
        branch_name=body.branch_name, branch_code=body.branch_code,
        account_type=body.account_type, account_number=body.account_number,
        account_holder_kana=body.account_holder_kana,
        transfer_destination_name=body.transfer_destination_name,
        effective_from=body.effective_from, effective_until=body.effective_until,
        is_primary=body.is_primary,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return SupplierBankAccountItem(
        id=account.id, supplier_id=account.supplier_id, bank_name=account.bank_name,
        branch_name=account.branch_name, branch_code=account.branch_code,
        account_type=account.account_type, account_number=account.account_number,
        account_holder_kana=account.account_holder_kana,
        transfer_destination_name=account.transfer_destination_name,
        effective_from=account.effective_from, effective_until=account.effective_until,
        is_primary=account.is_primary,
    )


@app.put("/api/suppliers/{supplier_id}/bank-accounts/{account_id}", response_model=SupplierBankAccountItem, tags=["Master"])
async def update_supplier_bank_account(
    supplier_id: str,
    account_id: str,
    body: SupplierBankAccountUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """下請けの振込先口座更新"""
    check_permission(current_user, Permission.MASTER_WRITE)
    account = db.query(SupplierBankAccount).filter(
        SupplierBankAccount.id == account_id,
        SupplierBankAccount.supplier_id == supplier_id,
        SupplierBankAccount.deleted_at.is_(None),
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="口座情報が見つかりません")
    account.bank_name = body.bank_name
    account.branch_name = body.branch_name
    account.branch_code = body.branch_code
    account.account_type = body.account_type
    account.account_number = body.account_number
    account.account_holder_kana = body.account_holder_kana
    account.transfer_destination_name = body.transfer_destination_name
    account.effective_from = body.effective_from
    account.effective_until = body.effective_until
    account.is_primary = body.is_primary
    db.commit()
    db.refresh(account)
    return SupplierBankAccountItem(
        id=account.id, supplier_id=account.supplier_id, bank_name=account.bank_name,
        branch_name=account.branch_name, branch_code=account.branch_code,
        account_type=account.account_type, account_number=account.account_number,
        account_holder_kana=account.account_holder_kana,
        transfer_destination_name=account.transfer_destination_name,
        effective_from=account.effective_from, effective_until=account.effective_until,
        is_primary=account.is_primary,
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

        client = db.get(Client, project.client_id)
        if not client or client.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Client not found")

        client_staff = None
        if request.client_staff_id:
            client_staff = db.get(ClientStaff, request.client_staff_id)
            if not client_staff or client_staff.deleted_at is not None or client_staff.client_id != client.id:
                raise HTTPException(status_code=404, detail="Client staff not found")

        year = int(request.period_key[:4])
        month = int(request.period_key[4:6])
        subject = (request.subject or "").strip() or f"{year}年{month}月分_{project.name}"
        
        check_permission(current_user, Permission.INVOICE_GENERATE)
        invoice = invoice_service.generate_invoice(
            session=db,
            client_id=project.client_id,
            project_id=request.project_id,
            period_key=request.period_key,
            billing_date=request.billing_date or date.today(),
            user_id=current_user.username,
            document_type=request.document_type,
            subject=subject,
            addressee_company_name=client.name,
            addressee_name=(client_staff.name if client_staff else client.contact_name),
            addressee_email=(client_staff.email if client_staff and client_staff.email else client.billing_email or client.contact_email),
            addressee_address=client.address,
            fixed_office_fee_amount=request.fixed_office_fee_amount,
        )
        db.commit()
        db.refresh(invoice)

        return _serialize_invoice_response(invoice)
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
        _store_invoice_pdf(invoice)
        db.commit()

        return _serialize_invoice_response(invoice)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except VANZAIException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="請求書発行に失敗しました")


@app.get("/api/invoices/{invoice_id}/pdf", tags=["Invoice"])
async def download_invoice_pdf(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """請求書PDFを都度生成して返す"""
    try:
        check_permission(current_user, Permission.INVOICE_READ)

        from src.models.transaction import Invoice

        invoice = db.get(Invoice, invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        if _status_to_str(invoice.status) == "preparing":
            raise HTTPException(status_code=400, detail="請求書はまだ発行前です")

        pdf_bytes = _load_invoice_pdf_bytes(invoice)

        filename = f'invoice_{invoice.id}_v{invoice.version}.pdf'
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except VANZAIException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="請求書PDFの生成に失敗しました")


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
        recipient_type = request.recipient_type or ("worker" if request.worker_id else None)
        recipient_id = request.recipient_id or request.worker_id
        if not recipient_type or not recipient_id:
            raise HTTPException(status_code=400, detail="recipient_type と recipient_id、または worker_id を指定してください")
        if recipient_type == "worker":
            from src.models.master import Worker

            linked_vanzai_staff = db.query(VanzaiStaff).filter(
                VanzaiStaff.linked_worker_id == recipient_id,
                VanzaiStaff.role == "全体統括責任者",
                VanzaiStaff.deleted_at.is_(None),
            ).first()
            if linked_vanzai_staff:
                raise HTTPException(
                    status_code=400,
                    detail="この稼働者は全体統括責任者の本人稼働分として VANZAI担当者支払に集約してください",
                )
            if not db.get(Worker, recipient_id):
                raise HTTPException(status_code=404, detail="稼働者が見つかりません")
            payout = payout_service.generate_payout(
                session=db,
                worker_id=recipient_id,
                project_id=request.project_id,
                period_key=request.period_key,
                payment_date=date.today(),
                user_id=current_user.username,
            )
        elif recipient_type == "supplier":
            payout = payout_service.generate_supplier_payout(
                session=db,
                supplier_id=recipient_id,
                period_key=request.period_key,
                payment_date=date.today(),
                user_id=current_user.username,
            )
        elif recipient_type == "vanzai_staff":
            payout = payout_service.generate_vanzai_staff_payout(
                session=db,
                vanzai_staff_id=recipient_id,
                period_key=request.period_key,
                payment_date=date.today(),
                user_id=current_user.username,
                support_fee_amount=request.support_fee_amount,
            )
        else:
            raise HTTPException(status_code=400, detail="現時点の支払明細生成 API は worker / supplier / vanzai_staff recipient のみ対応しています")

        payout.recipient_type = payout.recipient_type or recipient_type
        payout.recipient_id = payout.recipient_id or recipient_id
        vanzai_staff = db.get(VanzaiStaff, payout.recipient_id) if payout.recipient_type == "vanzai_staff" and payout.recipient_id else None
        payout.payee_name_snapshot = payout.payee_name_snapshot or (payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else (vanzai_staff.name if vanzai_staff else None)))
        db.commit()
        
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
            worker_name=payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else (vanzai_staff.name if vanzai_staff else "")),
            payee_name=payout.payee_name_snapshot or (payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else (vanzai_staff.name if vanzai_staff else ""))),
            recipient_type=payout.recipient_type,
            recipient_id=payout.recipient_id,
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
        _store_payout_pdf(payout)
        db.commit()
        
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
        vanzai_staff = db.get(VanzaiStaff, payout.recipient_id) if payout.recipient_type == "vanzai_staff" and payout.recipient_id else None
        
        return PayoutResponse(
            id=payout.id,
            payout_number=payout.id,
            worker_name=payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else (vanzai_staff.name if vanzai_staff else "")),
            payee_name=payout.payee_name_snapshot or (payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else (vanzai_staff.name if vanzai_staff else ""))),
            recipient_type=payout.recipient_type,
            recipient_id=payout.recipient_id,
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


@app.get("/api/payouts/{payout_id}/deliveries", response_model=PayoutDeliveryListResponse, tags=["Payout"])
async def list_payout_deliveries(
    payout_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """支払明細送信履歴取得"""
    try:
        check_permission(current_user, Permission.PAYOUT_READ)

        from src.models.transaction import Payout, PayoutDelivery

        payout = db.get(Payout, payout_id)
        if not payout:
            raise HTTPException(status_code=404, detail="Payout not found")

        rows = (
            db.query(PayoutDelivery)
            .filter(PayoutDelivery.payout_id == payout_id)
            .order_by(PayoutDelivery.sent_at.desc(), PayoutDelivery.created_at.desc())
            .all()
        )
        return PayoutDeliveryListResponse(items=[_serialize_payout_delivery_item(row) for row in rows])
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="支払明細送信履歴の取得に失敗しました")


@app.post("/api/payouts/{payout_id}/deliver", response_model=PayoutDeliveryItem, tags=["Payout"])
async def deliver_payout(
    payout_id: str,
    request: PayoutDeliveryRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """支払明細メール送信"""
    try:
        check_permission(current_user, Permission.PAYOUT_APPROVE)

        from src.models.master import VanzaiStaff
        from src.models.transaction import Payout, PayoutDelivery

        payout = db.get(Payout, payout_id)
        if not payout:
            raise HTTPException(status_code=404, detail="Payout not found")
        if _status_to_str(payout.status) == "preparing":
            raise HTTPException(status_code=400, detail="支払明細はまだ確定前です")

        recipient_email = (request.recipient_email or "").strip()
        delivery_note = (request.delivery_note or "").strip() or None
        internal_note = (request.internal_note or "").strip() or None
        if not recipient_email:
            vanzai_staff = db.get(VanzaiStaff, payout.recipient_id) if payout.recipient_type == "vanzai_staff" and payout.recipient_id else None
            recipient_email = (
                payout.worker.email if payout.worker else (
                    payout.supplier.contact_email if payout.supplier else (
                        vanzai_staff.email if vanzai_staff else None
                    )
                )
            ) or ""
        if not recipient_email:
            raise HTTPException(status_code=400, detail="送信先メールアドレスが設定されていません")

        if not payout.pdf_object_key:
            _store_payout_pdf(payout)
        pdf_bytes = _load_payout_pdf_bytes(payout)

        provider = os.getenv("EMAIL_PROVIDER", "gmail")
        dry_run = os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
        payee_name = payout.payee_name_snapshot or (payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else (vanzai_staff.name if vanzai_staff else payout.id)))
        template = EmailTemplateService().payout_statement_delivery(
            payee_name=payee_name,
            payee_email=recipient_email,
            period_key=payout.period_key,
            total_amount=float(payout.total_amount),
            payout_id=payout.id,
        )
        template.attachments.append(
            EmailAttachment(
                filename=f"payout_{payout.id}_v{payout.version}.pdf",
                content=pdf_bytes,
                content_type="application/pdf",
            )
        )

        success = get_default_sender(provider=provider).send_email(template, dry_run=dry_run)
        delivery = PayoutDelivery(
            payout_id=payout.id,
            recipient_email=recipient_email,
            status="sent" if success else "failed",
            provider=provider,
            delivered_by=current_user.username,
            pdf_object_key_snapshot=payout.pdf_object_key,
            delivery_note=delivery_note,
            internal_note=internal_note,
            error_message=None if success else "email send failed",
            sent_at=datetime.now(timezone.utc),
        )
        db.add(delivery)
        db.flush()

        AuditService(db).log(
            AuditAction.PAYOUT_DELIVERY_SENT if success else AuditAction.PAYOUT_DELIVERY_FAILED,
            target_type="payout_delivery",
            target_id=delivery.id,
            actor=current_user.username,
            actor_role=current_user.role,
            after_value={
                "payout_id": payout.id,
                "recipient_email": recipient_email,
                "status": delivery.status,
                "delivery_note": delivery_note,
            },
            extra_metadata={
                "provider": provider,
                "pdf_object_key": payout.pdf_object_key,
                "recipient_email": recipient_email,
                "delivery_note": delivery_note,
                "internal_note": internal_note,
                "status": delivery.status,
                "error_message": delivery.error_message,
            },
        )
        db.commit()
        db.refresh(delivery)
        return _serialize_payout_delivery_item(delivery)
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="支払明細メール送信に失敗しました")


@app.post("/api/payouts/{payout_id}/paid", response_model=PayoutResponse, tags=["Payout"])
async def mark_payout_paid(
    payout_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """支払済み更新"""
    try:
        check_permission(current_user, Permission.PAYOUT_APPROVE)
        payout = payout_service.mark_payout_paid(
            session=db,
            payout_id=payout_id,
            user_id=current_user.username,
        )
        db.commit()

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
        vanzai_staff = db.get(VanzaiStaff, payout.recipient_id) if payout.recipient_type == "vanzai_staff" and payout.recipient_id else None

        return PayoutResponse(
            id=payout.id,
            payout_number=payout.id,
            worker_name=payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else (vanzai_staff.name if vanzai_staff else "")),
            payee_name=payout.payee_name_snapshot or (payout.worker.name if payout.worker else (payout.supplier.name if payout.supplier else (vanzai_staff.name if vanzai_staff else ""))),
            recipient_type=payout.recipient_type,
            recipient_id=payout.recipient_id,
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
        raise HTTPException(status_code=500, detail="支払済み更新に失敗しました")


@app.get("/api/payouts/{payout_id}/pdf", tags=["Payout"])
async def download_payout_pdf(
    payout_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """支払明細PDFを都度生成して返す"""
    try:
        check_permission(current_user, Permission.PAYOUT_READ)

        from src.models.transaction import Payout

        payout = db.get(Payout, payout_id)
        if not payout:
            raise HTTPException(status_code=404, detail="Payout not found")

        if _status_to_str(payout.status) == "preparing":
            raise HTTPException(status_code=400, detail="支払明細はまだ確定前です")

        pdf_bytes = _load_payout_pdf_bytes(payout)

        filename = f'payout_{payout.id}_v{payout.version}.pdf'
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except VANZAIException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500, detail="支払明細PDFの生成に失敗しました")


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


# ===========================
# Staff Notices API
# ===========================

def _resolve_notice_targets(db: Session, notice: StaffNotice) -> list:
    """通知の対象稼働者リストを解決する（メール送信用）"""
    from src.models.master import Worker
    from src.models.transaction import Assignment

    if notice.target_type == NoticeTargetType.ALL.value:
        return db.query(Worker).filter(
            Worker.deleted_at.is_(None),
            Worker.is_active.is_(True),
            Worker.email.isnot(None),
        ).all()

    if notice.target_type == NoticeTargetType.PROJECT.value and notice.target_project_id:
        worker_ids = db.query(Assignment.worker_id).filter(
            Assignment.project_id == notice.target_project_id,
            Assignment.deleted_at.is_(None),
        ).distinct().subquery()
        return db.query(Worker).filter(
            Worker.id.in_(worker_ids),
            Worker.deleted_at.is_(None),
            Worker.is_active.is_(True),
            Worker.email.isnot(None),
        ).all()

    if notice.target_type == NoticeTargetType.WORKER.value and notice.target_worker_ids:
        return db.query(Worker).filter(
            Worker.id.in_(notice.target_worker_ids),
            Worker.deleted_at.is_(None),
            Worker.email.isnot(None),
        ).all()

    return []


@app.post("/api/notices", response_model=NoticeListItem, tags=["Notices"])
async def create_notice(
    request: NoticeCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    スタッフ通知作成

    - 管理者/OPSが通知を作成し、オプションでメール送信
    - target_type=all: 全アクティブ稼働者
    - target_type=project: 指定案件のアサイン済み稼働者
    - target_type=worker: 個別指定
    """
    try:
        check_permission(current_user, Permission.NOTICE_WRITE)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    # target_type 整合性チェック
    if request.target_type == NoticeTargetType.PROJECT.value and not request.target_project_id:
        raise HTTPException(status_code=422, detail="target_type=project のときは target_project_id が必要です")
    if request.target_type == NoticeTargetType.WORKER.value and not request.target_worker_ids:
        raise HTTPException(status_code=422, detail="target_type=worker のときは target_worker_ids が必要です")

    now = datetime.now(timezone.utc)
    notice = StaffNotice(
        id=generate_ulid(),
        title=request.title,
        body=request.body,
        notice_type=request.notice_type,
        priority=request.priority,
        target_type=request.target_type,
        target_project_id=request.target_project_id,
        target_worker_ids=request.target_worker_ids,
        send_email=request.send_email,
        push_action_type=request.push_action_type or None,
        sent_at=None,
        created_by=current_user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(notice)
    db.flush()

    # メール送信
    sent_count = 0
    if request.send_email:
        from src.models.transaction import Project
        project_name: str | None = None
        if notice.target_project_id:
            proj = db.get(Project, notice.target_project_id)
            project_name = proj.name if proj else None

        targets = _resolve_notice_targets(db, notice)
        tpl_svc = EmailTemplateService()
        sender = get_default_sender()
        dry_run = os.getenv("EMAIL_DRY_RUN", "false").lower() == "true"

        for worker in targets:
            try:
                tpl = tpl_svc.notice_to_worker(
                    worker_name=worker.name,
                    worker_email=worker.email,
                    title=notice.title,
                    body_text=notice.body,
                    notice_type=notice.notice_type,
                    priority=notice.priority,
                    project_name=project_name,
                )
                if not dry_run:
                    sender.send(tpl)
                sent_count += 1
            except Exception as exc:
                # 個別送信失敗はログに留めてスキップ
                AuditService(db).log(
                    action=AuditAction.NOTICE_SENT,
                    actor=current_user.username,
                    actor_role=current_user.role,
                    target_type="staff_notice",
                    target_id=notice.id,
                    extra_metadata={"error": str(exc), "worker_id": worker.id, "dry_run": dry_run},
                )

        notice.sent_at = now

    db.commit()
    db.refresh(notice)

    AuditService(db).log(
        action=AuditAction.NOTICE_CREATED,
        actor=current_user.username,
        actor_role=current_user.role,
        target_type="staff_notice",
        target_id=notice.id,
        extra_metadata={
            "title": notice.title,
            "notice_type": notice.notice_type,
            "target_type": notice.target_type,
            "send_email": notice.send_email,
            "sent_count": sent_count,
        },
    )

    # resolve project name for response
    from src.models.transaction import Project as Proj
    proj_name: str | None = None
    if notice.target_project_id:
        p = db.get(Proj, notice.target_project_id)
        proj_name = p.name if p else None

    creator_name = current_user.display_name or current_user.username

    # プッシュ通知を非同期で送信（失敗しても通知作成は成功扱い）
    try:
        from src.services.push_sender import send_push_to_workers
        push_worker_ids: list[str] = []
        if notice.target_type == NoticeTargetType.WORKER.value:
            push_worker_ids = list(notice.target_worker_ids or [])
        elif notice.target_type == NoticeTargetType.PROJECT.value:
            from src.models.transaction import Assignment, ShiftSlot
            push_worker_ids = [
                r[0] for r in db.query(Assignment.worker_id)
                .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
                .filter(
                    ShiftSlot.project_id == notice.target_project_id,
                    Assignment.deleted_at.is_(None),
                    ShiftSlot.deleted_at.is_(None),
                ).distinct().all()
            ]
        # target_type=all のときは push_worker_ids=[] → 全サブスクリプションに送信
        send_push_to_workers(
            db,
            push_worker_ids,
            title=notice.title,
            body=notice.body[:80] + ("..." if len(notice.body) > 80 else ""),
            url="/notices",
            notice_id=notice.id,
            push_action_type=notice.push_action_type,
        )
    except Exception as _push_exc:
        logger.warning("push notification failed: %s", _push_exc)

    return NoticeListItem(
        id=notice.id,
        title=notice.title,
        notice_type=notice.notice_type,
        priority=notice.priority,
        target_type=notice.target_type,
        target_project_id=notice.target_project_id,
        target_project_name=proj_name,
        target_worker_ids=notice.target_worker_ids,
        send_email=notice.send_email,
        push_action_type=notice.push_action_type,
        sent_at=notice.sent_at,
        read_count=0,
        created_by=notice.created_by,
        created_by_name=creator_name,
        created_at=notice.created_at,
        deleted_at=notice.deleted_at,
    )


@app.get("/api/notices", response_model=NoticeListResponse, tags=["Notices"])
async def list_notices(
    notice_type: Optional[str] = Query(None),
    target_type: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """スタッフ通知一覧（管理者用）"""
    try:
        check_permission(current_user, Permission.NOTICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    q = db.query(StaffNotice).filter(StaffNotice.deleted_at.is_(None))
    if notice_type:
        q = q.filter(StaffNotice.notice_type == notice_type)
    if target_type:
        q = q.filter(StaffNotice.target_type == target_type)

    total = q.count()
    notices = q.order_by(StaffNotice.created_at.desc()).offset(offset).limit(limit).all()

    from src.models.transaction import Project as Proj

    items = []
    for n in notices:
        proj_name: str | None = None
        if n.target_project_id:
            p = db.get(Proj, n.target_project_id)
            proj_name = p.name if p else None

        read_count = db.query(StaffNoticeRead).filter(
            StaffNoticeRead.notice_id == n.id
        ).count()

        creator_name: str | None = None
        if n.created_by:
            u = db.get(User, n.created_by)
            creator_name = (u.display_name or u.username) if u else None

        items.append(NoticeListItem(
            id=n.id,
            title=n.title,
            notice_type=n.notice_type,
            priority=n.priority,
            target_type=n.target_type,
            target_project_id=n.target_project_id,
            target_project_name=proj_name,
            target_worker_ids=n.target_worker_ids,
            send_email=n.send_email,
            push_action_type=n.push_action_type,
            sent_at=n.sent_at,
            read_count=read_count,
            created_by=n.created_by,
            created_by_name=creator_name,
            created_at=n.created_at,
            deleted_at=n.deleted_at,
        ))

    return NoticeListResponse(items=items, total=total, offset=offset, limit=limit)


@app.delete("/api/notices/{notice_id}", status_code=204, tags=["Notices"])
async def delete_notice(
    notice_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """スタッフ通知を論理削除（管理者用）"""
    try:
        check_permission(current_user, Permission.NOTICE_WRITE)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    notice = db.get(StaffNotice, notice_id)
    if not notice or notice.deleted_at is not None:
        raise HTTPException(status_code=404, detail="通知が見つかりません")

    notice.deleted_at = datetime.now(timezone.utc)
    db.commit()

    AuditService(db).log(
        action=AuditAction.NOTICE_DELETED,
        actor=current_user.username,
        actor_role=current_user.role,
        target_type="staff_notice",
        target_id=notice_id,
        extra_metadata={"title": notice.title},
    )


@app.get("/api/worker/notices", response_model=WorkerNoticeListResponse, tags=["Notices"])
async def list_worker_notices(
    unread_only: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    自分宛ての通知一覧（稼働者用）

    - アサイン情報・worker_id に基づいて表示対象を絞り込む
    """
    try:
        check_permission(current_user, Permission.NOTICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    # 稼働者レコードを特定
    from src.models.master import Worker
    worker = db.query(Worker).filter(
        Worker.id == current_user.worker_id,
        Worker.deleted_at.is_(None),
    ).first() if current_user.worker_id else None

    if not worker:
        # worker_id が紐付いていない（管理者などが誤って呼んでも空返す）
        return WorkerNoticeListResponse(items=[], unread_count=0, total=0)

    from src.models.transaction import Assignment, ShiftSlot

    # 自分がアサインされている案件ID一覧（ShiftSlot 経由で取得）
    assigned_project_ids = [
        r[0] for r in db.query(ShiftSlot.project_id)
        .join(Assignment, Assignment.shift_slot_id == ShiftSlot.id)
        .filter(
            Assignment.worker_id == worker.id,
            Assignment.deleted_at.is_(None),
            ShiftSlot.deleted_at.is_(None),
        ).distinct().all()
    ]

    # 対象通知の絞り込み（Python 側でフィルタ）
    notices = db.query(StaffNotice).filter(
        StaffNotice.deleted_at.is_(None),
    ).order_by(StaffNotice.created_at.desc()).all()

    # JSON contains は SQLite では使えないので Python 側でフィルタ
    def _worker_targeted(n: StaffNotice) -> bool:
        if n.target_type == NoticeTargetType.ALL.value:
            return True
        if n.target_type == NoticeTargetType.PROJECT.value:
            return n.target_project_id in assigned_project_ids
        if n.target_type == NoticeTargetType.WORKER.value:
            return worker.id in (n.target_worker_ids or [])
        return False

    notices = [n for n in notices if _worker_targeted(n)]

    # 既読状態を取得
    notice_ids = [n.id for n in notices]
    reads_map: dict[str, StaffNoticeRead] = {}
    if notice_ids:
        reads = db.query(StaffNoticeRead).filter(
            StaffNoticeRead.worker_id == worker.id,
            StaffNoticeRead.notice_id.in_(notice_ids),
        ).all()
        reads_map = {r.notice_id: r for r in reads}

    # unread_only フィルタ
    if unread_only:
        notices = [n for n in notices if n.id not in reads_map]

    total = len(notices)
    unread_count = sum(1 for n in notices if n.id not in reads_map)
    paged = notices[offset: offset + limit]

    items = []
    for n in paged:
        r = reads_map.get(n.id)
        proj_name: str | None = None
        if n.target_project_id:
            p = db.get(Proj, n.target_project_id)
            proj_name = p.name if p else None

        items.append(WorkerNoticeItem(
            id=n.id,
            title=n.title,
            body=n.body,
            notice_type=n.notice_type,
            priority=n.priority,
            target_project_id=n.target_project_id,
            target_project_name=proj_name,
            push_action_type=n.push_action_type,
            is_read=r is not None,
            read_at=r.read_at if r else None,
            response=r.response if r else None,
            responded_at=r.responded_at if r else None,
            created_at=n.created_at,
        ))

    return WorkerNoticeListResponse(items=items, unread_count=unread_count, total=total)


@app.post("/api/worker/notices/{notice_id}/read", status_code=204, tags=["Notices"])
async def mark_notice_read(
    notice_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """通知を既読にする（稼働者用）"""
    try:
        check_permission(current_user, Permission.NOTICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker
    worker = db.query(Worker).filter(
        Worker.id == current_user.worker_id,
        Worker.deleted_at.is_(None),
    ).first() if current_user.worker_id else None

    if not worker:
        raise HTTPException(status_code=403, detail="稼働者アカウントが必要です")

    notice = db.get(StaffNotice, notice_id)
    if not notice or notice.deleted_at is not None:
        raise HTTPException(status_code=404, detail="通知が見つかりません")

    existing = db.query(StaffNoticeRead).filter(
        StaffNoticeRead.notice_id == notice_id,
        StaffNoticeRead.worker_id == worker.id,
    ).first()

    if not existing:
        now = datetime.now(timezone.utc)
        db.add(StaffNoticeRead(
            id=generate_ulid(),
            notice_id=notice_id,
            worker_id=worker.id,
            read_at=now,
            created_at=now,
            updated_at=now,
        ))
        db.commit()


@app.post("/api/worker/notices/{notice_id}/respond", status_code=204, tags=["Notices"])
async def respond_to_notice(
    notice_id: str,
    body: StaffNoticeRespondRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    通知に返答する（稼働者用）

    - response: "ok" または "ng"
    - 既読も同時に記録する（未読でも返答可能）
    """
    if body.response not in ("ok", "ng"):
        raise HTTPException(status_code=422, detail="response は 'ok' または 'ng' を指定してください")

    try:
        check_permission(current_user, Permission.NOTICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker
    worker = db.query(Worker).filter(
        Worker.id == current_user.worker_id,
        Worker.deleted_at.is_(None),
    ).first() if current_user.worker_id else None

    if not worker:
        raise HTTPException(status_code=403, detail="稼働者アカウントが必要です")

    notice = db.get(StaffNotice, notice_id)
    if not notice or notice.deleted_at is not None:
        raise HTTPException(status_code=404, detail="通知が見つかりません")

    now = datetime.now(timezone.utc)
    existing = db.query(StaffNoticeRead).filter(
        StaffNoticeRead.notice_id == notice_id,
        StaffNoticeRead.worker_id == worker.id,
    ).first()

    if existing:
        existing.response = body.response
        existing.responded_at = now
        existing.updated_at = now
        # 未読なら既読にもする
        if existing.read_at is None:
            existing.read_at = now
    else:
        db.add(StaffNoticeRead(
            id=generate_ulid(),
            notice_id=notice_id,
            worker_id=worker.id,
            read_at=now,
            response=body.response,
            responded_at=now,
            created_at=now,
            updated_at=now,
        ))

    db.commit()

    AuditService(db).log(
        action=AuditAction.NOTICE_RESPONDED,
        actor=current_user.username,
        actor_role=current_user.role,
        target_type="staff_notice",
        target_id=notice_id,
        extra_metadata={"response": body.response, "worker_id": worker.id},
    )


@app.get("/api/worker/push/vapid-public-key", response_model=VapidPublicKeyResponse, tags=["Notices"])
async def get_vapid_public_key(
    current_user: User = Depends(get_current_active_user),
):
    """VAPID 公開鍵を返す（フロントが Push 登録時に使う）"""
    return VapidPublicKeyResponse(public_key=os.environ.get("VAPID_PUBLIC_KEY", ""))


@app.post("/api/worker/push/subscribe", status_code=204, tags=["Notices"])
async def subscribe_push(
    body: PushSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Web Push サブスクリプションを登録する（稼働者用）

    - 同じ endpoint + worker_id が既存なら更新（upsert）
    """
    try:
        check_permission(current_user, Permission.NOTICE_READ)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    from src.models.master import Worker
    worker = db.query(Worker).filter(
        Worker.id == current_user.worker_id,
        Worker.deleted_at.is_(None),
    ).first() if current_user.worker_id else None

    worker_id = worker.id if worker else None
    now = datetime.now(timezone.utc)

    existing = db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint,
        PushSubscription.worker_id == worker_id,
    ).first()

    if existing:
        existing.p256dh = body.p256dh
        existing.auth = body.auth
        existing.user_agent_hash = body.user_agent_hash
        existing.updated_at = now
    else:
        db.add(PushSubscription(
            id=generate_ulid(),
            worker_id=worker_id,
            endpoint=body.endpoint,
            p256dh=body.p256dh,
            auth=body.auth,
            user_agent_hash=body.user_agent_hash,
            created_at=now,
            updated_at=now,
        ))
    db.commit()


@app.delete("/api/worker/push/subscribe", status_code=204, tags=["Notices"])
async def unsubscribe_push(
    body: PushSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Web Push サブスクリプションを削除する（通知拒否時に呼ばれる）"""
    db.query(PushSubscription).filter(
        PushSubscription.endpoint == body.endpoint,
    ).delete(synchronize_session=False)
    db.commit()


from src.api.ocr_routes import router as ocr_router
from src.api.inventory_routes import router as inventory_router

app.include_router(ocr_router)
app.include_router(inventory_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
