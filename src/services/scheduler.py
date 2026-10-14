"""
スケジューラーサービス（APScheduler）

週次催促、日次更新、月次請求書生成の定期実行
"""
from contextlib import contextmanager
from dataclasses import dataclass
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, date, timedelta
import logging
import os

from src.api.deps import SessionLocal
from src.models.enums import AssignmentStatus, AssignmentWorkerResponseStatus, AuditAction
from src.services.audit import AuditService
from src.services.email_sender import get_default_sender
from src.services.email_template import EmailTemplateService

# ロガー設定
logger = logging.getLogger(__name__)


@dataclass
class WorkerReminderPayload:
    worker_id: str
    worker_name: str
    worker_email: str | None
    assignments: list[dict[str, object]]


@dataclass
class ReminderDispatchWorkerResult:
    worker_id: str
    worker_name: str
    worker_email: str | None
    assignment_ids: list[str]
    assignment_count: int
    status: str


@dataclass
class ReminderDispatchResult:
    eligible_assignment_count: int
    recipient_count: int
    sent_count: int
    failed_count: int
    skipped_missing_email_count: int
    dry_run: bool
    worker_results: list[ReminderDispatchWorkerResult]


class SchedulerService:
    """
    定期実行スケジューラー
    
    APSchedulerを使用してバックグラウンドタスクを実行
    """
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        logger.info("Scheduler started")
    
    def add_weekly_reminder(self, day_of_week: str = "mon", hour: int = 9):
        """
        週次催促ジョブ追加
        
        Args:
            day_of_week: 曜日（mon, tue, wed, thu, fri, sat, sun）
            hour: 実行時刻（時）
        """
        self.scheduler.add_job(
            func=self._run_weekly_reminder,
            trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=0),
            id="weekly_reminder",
            name="週次催促",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600,
            max_instances=1,
        )
        logger.info(f"Added weekly reminder job: {day_of_week} {hour}:00")
    
    def add_daily_dashboard_update(self, hour: int = 6):
        """
        日次ダッシュボード更新ジョブ追加
        
        Args:
            hour: 実行時刻（時）
        """
        self.scheduler.add_job(
            func=self._run_daily_update,
            trigger=CronTrigger(hour=hour, minute=0),
            id="daily_update",
            name="日次ダッシュボード更新",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600,
            max_instances=1,
        )
        logger.info(f"Added daily dashboard update job: {hour}:00")
    
    def add_monthly_invoice_generation(self, day: int = 1, hour: int = 10):
        """
        月次請求書生成ジョブ追加
        
        Args:
            day: 実行日（月の何日）
            hour: 実行時刻（時）
        """
        self.scheduler.add_job(
            func=self._run_monthly_invoice,
            trigger=CronTrigger(day=day, hour=hour, minute=0),
            id="monthly_invoice",
            name="月次請求書生成",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=3600,
            max_instances=1,
        )
        logger.info(f"Added monthly invoice job: Day {day} at {hour}:00")

    @contextmanager
    def _session_scope(self):
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    def _collect_worker_response_reminders(
        self,
        session,
        *,
        period_start: date | None = None,
        period_end: date | None = None,
        assignment_ids: list[str] | None = None,
    ) -> tuple[list[WorkerReminderPayload], int]:
        from src.models.master import Worker
        from src.models.transaction import Assignment, Project, ShiftSlot

        query = (
            session.query(
                Assignment.id.label("assignment_id"),
                Worker.id.label("worker_id"),
                Worker.name.label("worker_name"),
                Worker.email.label("worker_email"),
                Project.name.label("project_name"),
                ShiftSlot.work_date.label("work_date"),
                ShiftSlot.shift_label.label("shift_label"),
                ShiftSlot.start_time.label("start_time"),
            )
            .join(ShiftSlot, Assignment.shift_slot_id == ShiftSlot.id)
            .join(Project, ShiftSlot.project_id == Project.id)
            .join(Worker, Assignment.worker_id == Worker.id)
            .filter(Assignment.status != AssignmentStatus.CANCELED.value)
            .filter(Assignment.worker_response_status == AssignmentWorkerResponseStatus.PENDING.value)
            .order_by(Worker.id, ShiftSlot.work_date, ShiftSlot.start_time, Project.name)
        )

        if period_start is not None:
            query = query.filter(ShiftSlot.work_date >= period_start)
        if period_end is not None:
            query = query.filter(ShiftSlot.work_date <= period_end)
        if assignment_ids is not None:
            query = query.filter(Assignment.id.in_(assignment_ids if assignment_ids else [""]))

        rows = query.all()

        reminders_by_worker: dict[str, WorkerReminderPayload] = {}
        total_assignments = 0

        for row in rows:
            total_assignments += 1
            payload = reminders_by_worker.setdefault(
                row.worker_id,
                WorkerReminderPayload(
                    worker_id=row.worker_id,
                    worker_name=row.worker_name,
                    worker_email=row.worker_email,
                    assignments=[],
                ),
            )
            payload.assignments.append(
                {
                    "assignment_id": row.assignment_id,
                    "project_name": row.project_name,
                    "work_date": row.work_date,
                    "shift_label": row.shift_label,
                }
            )

        return list(reminders_by_worker.values()), total_assignments

    def send_assignment_response_reminders(
        self,
        session,
        *,
        actor: str,
        actor_role: str,
        period_start: date | None = None,
        period_end: date | None = None,
        assignment_ids: list[str] | None = None,
        dry_run: bool | None = None,
    ) -> ReminderDispatchResult:
        resolved_dry_run = dry_run if dry_run is not None else os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
        sender = get_default_sender(provider=os.getenv("EMAIL_PROVIDER", "gmail"))
        email_service = EmailTemplateService()
        audit_service = AuditService(session)

        reminder_payloads, assignment_count = self._collect_worker_response_reminders(
            session,
            period_start=period_start,
            period_end=period_end,
            assignment_ids=assignment_ids,
        )

        recipient_count = len(reminder_payloads)
        sent_count = 0
        failed_count = 0
        skipped_missing_email_count = 0
        worker_results: list[ReminderDispatchWorkerResult] = []

        effective_period_start = period_start or min((item["work_date"] for payload in reminder_payloads for item in payload.assignments), default=date.today())
        effective_period_end = period_end or max((item["work_date"] for payload in reminder_payloads for item in payload.assignments), default=date.today())

        for payload in reminder_payloads:
            assignment_ids_for_worker = [str(item["assignment_id"]) for item in payload.assignments]
            if not payload.worker_email or not payload.worker_email.strip():
                skipped_missing_email_count += 1
                worker_results.append(
                    ReminderDispatchWorkerResult(
                        worker_id=payload.worker_id,
                        worker_name=payload.worker_name,
                        worker_email=payload.worker_email,
                        assignment_ids=assignment_ids_for_worker,
                        assignment_count=len(payload.assignments),
                        status="skipped_missing_email",
                    )
                )
                logger.warning("Skipping assignment response reminder for worker %s due to missing email", payload.worker_id)
                continue

            template = email_service.assignment_response_reminder(
                worker_name=payload.worker_name,
                worker_email=payload.worker_email,
                period_start=effective_period_start,
                period_end=effective_period_end,
                pending_assignments=payload.assignments,
            )
            sent = sender.send_email(template, dry_run=resolved_dry_run)
            status = "sent" if sent else "failed"
            if sent:
                sent_count += 1
            else:
                failed_count += 1

            worker_results.append(
                ReminderDispatchWorkerResult(
                    worker_id=payload.worker_id,
                    worker_name=payload.worker_name,
                    worker_email=payload.worker_email,
                    assignment_ids=assignment_ids_for_worker,
                    assignment_count=len(payload.assignments),
                    status=status,
                )
            )

            audit_service.log(
                AuditAction.ASSIGNMENT_RESPONSE_REMINDER_SENT if sent else AuditAction.ASSIGNMENT_RESPONSE_REMINDER_FAILED,
                target_type="assignment",
                actor=actor,
                actor_role=actor_role,
                after_value={
                    "worker_id": payload.worker_id,
                    "worker_email": payload.worker_email,
                    "assignment_count": len(payload.assignments),
                    "period_start": effective_period_start.isoformat(),
                    "period_end": effective_period_end.isoformat(),
                    "dry_run": resolved_dry_run,
                },
                extra_metadata={
                    "assignment_ids": assignment_ids_for_worker,
                },
            )

        return ReminderDispatchResult(
            eligible_assignment_count=assignment_count,
            recipient_count=recipient_count,
            sent_count=sent_count,
            failed_count=failed_count,
            skipped_missing_email_count=skipped_missing_email_count,
            dry_run=resolved_dry_run,
            worker_results=worker_results,
        )
    
    def _run_weekly_reminder(self):
        """週次催促実行"""
        logger.info("Running weekly reminder...")
        
        try:
            lookahead_days = max(int(os.getenv("SCHEDULER_WEEKLY_LOOKAHEAD_DAYS", "14")), 0)
            period_start = date.today()
            period_end = period_start + timedelta(days=lookahead_days)
            dry_run = os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
            sender = get_default_sender(provider=os.getenv("EMAIL_PROVIDER", "gmail"))
            email_service = EmailTemplateService()

            with self._session_scope() as session:
                dispatch_result = self.send_assignment_response_reminders(
                    session,
                    actor="scheduler",
                    actor_role="system",
                    period_start=period_start,
                    period_end=period_end,
                )

                if dispatch_result.eligible_assignment_count == 0:
                    logger.info(
                        "Weekly reminder found no pending worker responses (%s to %s)",
                        period_start,
                        period_end,
                    )
                    return

                session.commit()
                logger.info(
                    "Weekly reminder completed: assignments=%s recipients=%s sent=%s failed=%s skipped_missing_email=%s",
                    dispatch_result.eligible_assignment_count,
                    dispatch_result.recipient_count,
                    dispatch_result.sent_count,
                    dispatch_result.failed_count,
                    dispatch_result.skipped_missing_email_count,
                )
        except Exception as e:
            logger.error(f"Weekly reminder failed: {e}")
        
        logger.info("Weekly reminder process completed")
    
    def _run_daily_update(self):
        """日次ダッシュボード更新実行"""
        logger.info("Running daily dashboard update...")
        
        try:
            from src.services.dashboard import get_dashboard_summary
            from datetime import date
            
            with self._session_scope() as session:
                period_key = date.today().strftime("%Y%m")
                summary = get_dashboard_summary(session, period_key)
                total = (
                    summary.unprocessed_assignment_count
                    + summary.missing_price_count
                    + summary.unprocessed_invoice_count
                    + summary.unprocessed_payout_count
                    + summary.pending_assignment_response_count
                    + summary.unclosed_project_count
                )
                logger.info(
                    "Dashboard summary refreshed (%s): total=%s (assign=%s, missing_price=%s, invoice=%s, payout=%s, pending_response=%s, escalated_response=%s, unclosed=%s)",
                    period_key,
                    total,
                    summary.unprocessed_assignment_count,
                    summary.missing_price_count,
                    summary.unprocessed_invoice_count,
                    summary.unprocessed_payout_count,
                    summary.pending_assignment_response_count,
                    summary.escalated_assignment_response_count,
                    summary.unclosed_project_count,
                )
        except Exception as e:
            logger.error(f"Daily update failed: {e}")
        
        logger.info("Daily update completed")
    
    def _run_monthly_invoice(self):
        """月次請求書生成実行"""
        logger.info("Running monthly invoice generation...")
        
        try:
            from src.services import invoice_service
            from src.services.pdf_generator import PDFGenerator
            from src.services.email_template import EmailTemplateService, EmailTemplate
            from src.services.email_sender import get_default_sender
            from src.models.transaction import Project
            from datetime import date
            from dateutil.relativedelta import relativedelta
            from pathlib import Path
            import os
            
            with self._session_scope() as session:
                # 前月のperiod_key取得
                last_month = date.today().replace(day=1) - relativedelta(months=1)
                period_key = last_month.strftime("%Y%m")
                
                # 全プロジェクトを取得
                projects = session.query(Project).filter(Project.is_active == True).all()
                
                pdf_generator = PDFGenerator(output_dir=Path("./invoices"))
                email_service = EmailTemplateService()
                
                generated_count = 0
                pdf_count = 0
                email_templates = []
                
                for project in projects:
                    try:
                        # プロジェクト×期間で請求書生成
                        invoice = invoice_service.generate_invoice(
                            session=session,
                            client_id=project.client_id,
                            project_id=project.id,
                            period_key=period_key,
                            billing_date=date.today(),
                            user_id="scheduler"
                        )
                        logger.info(f"Generated invoice for {project.name}: {invoice.id}")
                        generated_count += 1
                        
                        # PDF生成
                        try:
                            pdf_path = pdf_generator.generate_invoice_pdf(invoice, list(invoice.lines))
                            logger.info(f"Generated PDF: {pdf_path}")
                            pdf_count += 1
                            
                            # 承認依頼メール準備（primary_managerがいれば送信）
                            if hasattr(project, 'primary_manager') and project.primary_manager:
                                manager_email = project.primary_manager.email
                                if manager_email:
                                    subject, body = email_service.invoice_approval_request(
                                        invoice_number=invoice.id,
                                        period=period_key,
                                        amount=float(invoice.total_amount),
                                        client_name=invoice.client.name if invoice.client else "不明",
                                        pdf_path=str(pdf_path) if isinstance(pdf_path, Path) else pdf_path
                                    )
                                    email_templates.append(EmailTemplate(
                                        to=manager_email,
                                        subject=subject,
                                        body=body
                                    ))
                        except Exception as e:
                            logger.error(f"Failed to generate PDF for invoice {invoice.id}: {e}")
                    except Exception as e:
                        logger.error(f"Failed to generate invoice for {project.name}: {e}")
                
                # 承認依頼メール一括送信
                if email_templates:
                    dry_run = os.getenv("EMAIL_DRY_RUN", "true").lower() == "true"
                    sender = get_default_sender(provider=os.getenv("EMAIL_PROVIDER", "gmail"))
                    result = sender.send_bulk_emails(email_templates, dry_run=dry_run)
                    logger.info(f"Approval emails: {result['success']} sent, {result['failed']} failed")
                
                logger.info(f"Monthly invoice generation: {generated_count} invoices, {pdf_count} PDFs created")
        except Exception as e:
            logger.error(f"Monthly invoice generation failed: {e}")
        
        logger.info("Monthly invoice generation completed")
    
    def list_jobs(self):
        """登録されているジョブ一覧"""
        jobs = self.scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time,
                "trigger": str(job.trigger)
            }
            for job in jobs
        ]
    
    def remove_job(self, job_id: str):
        """ジョブ削除"""
        self.scheduler.remove_job(job_id)
        logger.info(f"Removed job: {job_id}")
    
    def shutdown(self):
        """スケジューラー停止"""
        self.scheduler.shutdown()
        logger.info("Scheduler shutdown")

    def run_job_once(self, job_id: str):
        """指定ジョブを1回だけ実行する"""
        job_map = {
            "weekly_reminder": self._run_weekly_reminder,
            "daily_update": self._run_daily_update,
            "monthly_invoice": self._run_monthly_invoice,
        }
        job = job_map.get(job_id)
        if job is None:
            raise ValueError(f"Unknown scheduler job: {job_id}")

        logger.info("Running scheduler job once: %s", job_id)
        job()


# グローバルスケジューラーインスタンス
_scheduler_instance = None


def get_scheduler() -> SchedulerService:
    """スケジューラーシングルトン取得"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SchedulerService()
    return _scheduler_instance


def initialize_default_jobs():
    """デフォルトジョブ初期化"""
    def _get_env(name: str, fallback_name: str | None = None) -> str | None:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
        if fallback_name:
            value2 = os.getenv(fallback_name)
            if value2 is not None and value2 != "":
                return value2
        return None

    def _get_int(name: str, fallback_name: str | None, default: int) -> int:
        raw = _get_env(name, fallback_name)
        if raw is None:
            return default
        try:
            return int(raw)
        except Exception:
            return default

    def _normalize_weekday(value: str | None, default: str = "mon") -> str:
        if value is None:
            return default

        lowered = value.strip().lower()
        if lowered.isdigit():
            mapping = {
                "0": "mon",
                "1": "tue",
                "2": "wed",
                "3": "thu",
                "4": "fri",
                "5": "sat",
                "6": "sun",
            }
            return mapping.get(lowered, default)

        if lowered in {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}:
            return lowered
        return default

    enabled = _get_env("SCHEDULER_ENABLED")
    if enabled is None or enabled.lower() in {"false", "0", "no"}:
        logger.info("Scheduler disabled (set SCHEDULER_ENABLED=true to enable)")
        return

    scheduler = get_scheduler()

    weekly_day_raw = _get_env("SCHEDULER_WEEKLY_DAY", "WEEKLY_REMINDER_DAY")
    weekly_day = _normalize_weekday(weekly_day_raw, default="mon")
    weekly_hour = _get_int("SCHEDULER_WEEKLY_HOUR", "WEEKLY_REMINDER_HOUR", default=9)

    daily_hour = _get_int("SCHEDULER_DAILY_HOUR", "DAILY_UPDATE_HOUR", default=6)

    monthly_day = _get_int("SCHEDULER_MONTHLY_DAY", "MONTHLY_INVOICE_DAY", default=1)
    monthly_hour = _get_int("SCHEDULER_MONTHLY_HOUR", "MONTHLY_INVOICE_HOUR", default=10)

    # 週次催促
    scheduler.add_weekly_reminder(day_of_week=weekly_day, hour=weekly_hour)

    # 日次更新
    scheduler.add_daily_dashboard_update(hour=daily_hour)

    # 月次請求書
    scheduler.add_monthly_invoice_generation(day=monthly_day, hour=monthly_hour)

    logger.info(
        "Default jobs initialized (weekly=%s %s:00, daily=%s:00, monthly=%s %s:00)",
        weekly_day,
        weekly_hour,
        daily_hour,
        monthly_day,
        monthly_hour,
    )


if __name__ == "__main__":
    # テスト実行
    logging.basicConfig(level=logging.INFO)
    initialize_default_jobs()
    
    scheduler = get_scheduler()
    print("Registered jobs:")
    for job in scheduler.list_jobs():
        print(f"  - {job['name']} (ID: {job['id']})")
        print(f"    Next run: {job['next_run']}")
        print(f"    Trigger: {job['trigger']}")
