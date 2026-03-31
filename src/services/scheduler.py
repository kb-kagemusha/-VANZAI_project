"""
スケジューラーサービス（APScheduler）

週次催促、日次更新、月次請求書生成の定期実行
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, date
import logging
import os

# ロガー設定
logger = logging.getLogger(__name__)


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
            replace_existing=True
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
            replace_existing=True
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
            replace_existing=True
        )
        logger.info(f"Added monthly invoice job: Day {day} at {hour}:00")
    
    def _run_weekly_reminder(self):
        """週次催促実行"""
        logger.info("Running weekly reminder...")
        
        try:
            # NOTE:
            # 旧実装では "CSV未提出" を案件担当者へ催促する仕様だったが、
            # 現行コードベースでは案件担当者メール等の取得ロジックが未定義のため、
            # ここでは安全に no-op として扱う（落ちないことを優先）。
            logger.info("Weekly reminder is not configured; skipping")
        except Exception as e:
            logger.error(f"Weekly reminder failed: {e}")
        
        logger.info("Weekly reminder process completed")
    
    def _run_daily_update(self):
        """日次ダッシュボード更新実行"""
        logger.info("Running daily dashboard update...")
        
        try:
            from src.models.base import get_session
            from src.services.dashboard import get_dashboard_summary
            from datetime import date
            
            with get_session() as session:
                period_key = date.today().strftime("%Y%m")
                summary = get_dashboard_summary(session, period_key)
                total = (
                    summary.unprocessed_assignment_count
                    + summary.missing_price_count
                    + summary.unprocessed_invoice_count
                    + summary.unprocessed_payout_count
                    + summary.unclosed_project_count
                )
                logger.info(
                    "Dashboard summary refreshed (%s): total=%s (assign=%s, missing_price=%s, invoice=%s, payout=%s, unclosed=%s)",
                    period_key,
                    total,
                    summary.unprocessed_assignment_count,
                    summary.missing_price_count,
                    summary.unprocessed_invoice_count,
                    summary.unprocessed_payout_count,
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
            from src.models.base import get_session
            from src.models.transaction import Project
            from datetime import date
            from dateutil.relativedelta import relativedelta
            from pathlib import Path
            import os
            
            with get_session() as session:
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
