"""OCR parse job worker helpers."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.ocr import OcrParseJob, OcrUploadAttempt
from src.services.ocr.execution_lock import ocr_execution_lock
from src.services.ocr_service import OcrService

STALE_PROCESSING_MINUTES = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def reconcile_stale_jobs(session: Session) -> int:
    cutoff = _utcnow() - timedelta(minutes=STALE_PROCESSING_MINUTES)
    stale_jobs = session.execute(
        select(OcrParseJob).where(
            OcrParseJob.status == "processing",
            OcrParseJob.claimed_at.is_not(None),
            OcrParseJob.claimed_at < cutoff,
        )
    ).scalars().all()
    for job in stale_jobs:
        job.status = "pending"
        job.claimed_at = None
        job.claim_token = None
    if stale_jobs:
        session.flush()
    return len(stale_jobs)


def claim_next_pending_job(session: Session) -> OcrParseJob | None:
    dialect = session.get_bind().dialect.name
    query = (
        select(OcrParseJob)
        .where(OcrParseJob.status == "pending")
        .order_by(OcrParseJob.priority.asc(), OcrParseJob.created_at.asc())
        .limit(1)
    )
    if dialect == "postgresql":
        query = query.with_for_update(skip_locked=True)
    job = session.execute(query).scalar_one_or_none()
    if job is None:
        return None

    job.status = "processing"
    job.claimed_at = _utcnow()
    job.claim_token = secrets.token_hex(16)
    session.flush()
    return job


def run_claimed_job(session: Session, job: OcrParseJob) -> None:
    image_ids = list(job.image_ids_json or [])
    if not image_ids:
        job.status = "failed"
        job.error_message = "image_ids_json is empty"
        job.completed_at = _utcnow()
        return

    attempt = session.get(OcrUploadAttempt, job.upload_attempt_id) if job.upload_attempt_id else None

    try:
        with ocr_execution_lock(session):
            service = OcrService(session)
            completed = service.parse_images(
                image_ids=image_ids,
                executed_by=job.executed_by or "ocr_worker",
                job_id=job.id,
            )
        if attempt is not None:
            attempt.attempt_status = (
                "parse_completed" if completed.status in {"completed", "partial_error"} else "parse_failed"
            )
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = _utcnow()
        if attempt is not None:
            attempt.attempt_status = "parse_failed"
        raise


def process_one_pending_job(session: Session) -> bool:
    reconcile_stale_jobs(session)
    job = claim_next_pending_job(session)
    if job is None:
        session.commit()
        return False
    job_id = job.id
    session.commit()

    session.begin()
    job = session.get(OcrParseJob, job_id)
    if job is None:
        session.rollback()
        return False
    try:
        run_claimed_job(session, job)
        session.commit()
    except Exception:
        session.rollback()
        session.begin()
        failed = session.get(OcrParseJob, job_id)
        if failed is not None and failed.status == "processing":
            failed.status = "failed"
            failed.completed_at = _utcnow()
            failed.error_message = failed.error_message or "worker failed"
            attempt = (
                session.get(OcrUploadAttempt, failed.upload_attempt_id)
                if failed.upload_attempt_id
                else None
            )
            if attempt is not None:
                attempt.attempt_status = "parse_failed"
        session.commit()
    return True
