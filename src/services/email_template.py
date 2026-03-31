"""
メールテンプレートサービス

各種通知メールのテンプレート生成を担当
- シフト未確定催促
- CSV未提出催促
- CSVエラー差戻し
- 請求書承認依頼
- 支払承認依頼
- エスカレーション

仕様参照: EMAIL_TEMPLATES.md
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass
class EmailTemplate:
    """メールテンプレート"""
    subject: str
    body: str
    to: str
    cc: str | None = None


class EmailTemplateService:
    """メールテンプレート生成サービス"""

    def __init__(self, sender_signature: str = "VANZAI管理システム"):
        """
        Args:
            sender_signature: 送信者署名
        """
        self.sender_signature = sender_signature

    def shift_unconfirmed_reminder(
        self,
        site_manager_name: str,
        site_manager_email: str,
        project_name: str,
        week_start: date,
        week_end: date,
        unconfirmed_count: int,
        deadline: datetime,
    ) -> EmailTemplate:
        """
        シフト未確定催促メール

        Args:
            site_manager_name: 現場管理者名
            site_manager_email: 現場管理者メールアドレス
            project_name: 案件名
            week_start: 対象週開始日
            week_end: 対象週終了日
            unconfirmed_count: 未確定枠数
            deadline: 締切日時

        Returns:
            EmailTemplate
        """
        subject = f"【要対応】シフト未確定枠があります（{project_name} {week_start}週）"

        body = f"""{site_manager_name} 様

以下案件で未確定シフト枠が残っています
- 案件名: {project_name}
- 対象週: {week_start.strftime('%Y-%m-%d')}〜{week_end.strftime('%Y-%m-%d')}
- 未確定枠数: {unconfirmed_count}
- 締切: {deadline.strftime('%Y-%m-%d %H:%M')}

締切までに確定または状況共有をお願いします

Ops {self.sender_signature}
"""

        return EmailTemplate(
            subject=subject,
            body=body,
            to=site_manager_email,
        )

    def csv_unsubmitted_reminder(
        self,
        site_manager_name: str,
        site_manager_email: str,
        project_name: str,
        target_month: str,
        deadline: datetime,
        submission_method: str = "kintoneアプリにアップロード",
    ) -> EmailTemplate:
        """
        実績CSV未提出催促メール

        Args:
            site_manager_name: 現場管理者名
            site_manager_email: 現場管理者メールアドレス
            project_name: 案件名
            target_month: 対象月（YYYYMM形式）
            deadline: 提出期限
            submission_method: 提出方法

        Returns:
            EmailTemplate
        """
        subject = f"【要対応】実績CSV未提出です（{project_name} {target_month[:4]}-{target_month[4:]}）"

        body = f"""{site_manager_name} 様

以下案件の実績CSVが未提出です
- 案件名: {project_name}
- 対象月: {target_month[:4]}-{target_month[4:]}
- 提出期限: {deadline.strftime('%Y-%m-%d %H:%M')}
- 提出方法: {submission_method}

期限までの提出をお願いします

Ops {self.sender_signature}
"""

        return EmailTemplate(
            subject=subject,
            body=body,
            to=site_manager_email,
        )

    def csv_error_rejection(
        self,
        site_manager_name: str,
        site_manager_email: str,
        project_name: str,
        target_month: str,
        import_datetime: datetime,
        error_count: int,
        error_samples: list[dict[str, Any]],
        correction_deadline: datetime,
    ) -> EmailTemplate:
        """
        CSVエラー差戻しメール

        Args:
            site_manager_name: 現場管理者名
            site_manager_email: 現場管理者メールアドレス
            project_name: 案件名
            target_month: 対象月（YYYYMM形式）
            import_datetime: 取込日時
            error_count: エラー件数
            error_samples: エラーサンプル（最大5件）
                例: [{"line": 10, "reason": "アサインメントが見つかりません", "key": "2025-01-10 山田太郎"}]
            correction_deadline: 修正期限

        Returns:
            EmailTemplate
        """
        subject = f"【要修正】実績CSVにエラーがあります（{project_name} {target_month[:4]}-{target_month[4:]}）"

        error_details = "\n".join(
            f"{err['line']}行目: {err['reason']} ({err['key']})"
            for err in error_samples[:5]
        )

        body = f"""{site_manager_name} 様

提出いただいたCSVに以下のエラーがあります
- 案件名: {project_name}
- 対象月: {target_month[:4]}-{target_month[4:]}
- 取込日時: {import_datetime.strftime('%Y-%m-%d %H:%M')}
- エラー件数: {error_count}
- 修正期限: {correction_deadline.strftime('%Y-%m-%d %H:%M')}

エラー詳細（抜粋）
{error_details}

修正後のCSVを再提出してください

Ops {self.sender_signature}
"""

        return EmailTemplate(
            subject=subject,
            body=body,
            to=site_manager_email,
        )

    def invoice_approval_request(
        self,
        approver_name: str,
        approver_email: str,
        client_name: str,
        period_key: str,
        total_amount: float,
        invoice_id: str,
        approval_deadline: datetime,
    ) -> EmailTemplate:
        """
        請求書承認依頼メール

        Args:
            approver_name: 承認者名
            approver_email: 承認者メールアドレス
            client_name: クライアント名
            period_key: 請求期間
            total_amount: 請求金額
            invoice_id: 請求書ID
            approval_deadline: 承認期限

        Returns:
            EmailTemplate
        """
        subject = f"【承認依頼】請求書承認をお願いします（{client_name} {period_key}）"

        body = f"""{approver_name} 様

以下の請求書の承認をお願いします
- クライアント: {client_name}
- 請求期間: {period_key[:4]}-{period_key[4:]}
- 請求金額: ¥{total_amount:,.0f}
- 請求書ID: {invoice_id}
- 承認期限: {approval_deadline.strftime('%Y-%m-%d %H:%M')}

システムにログインして請求書を確認し、承認処理をお願いします

Accounting {self.sender_signature}
"""

        return EmailTemplate(
            subject=subject,
            body=body,
            to=approver_email,
        )

    def payout_approval_request(
        self,
        approver_name: str,
        approver_email: str,
        worker_name: str,
        period_key: str,
        total_amount: float,
        payout_id: str,
        approval_deadline: datetime,
    ) -> EmailTemplate:
        """
        支払承認依頼メール

        Args:
            approver_name: 承認者名
            approver_email: 承認者メールアドレス
            worker_name: 稼働者名
            period_key: 対象期間
            total_amount: 支払金額
            payout_id: 支払明細ID
            approval_deadline: 承認期限

        Returns:
            EmailTemplate
        """
        subject = f"【承認依頼】支払承認をお願いします（{worker_name} {period_key}）"

        body = f"""{approver_name} 様

以下の支払明細の承認をお願いします
- 稼働者: {worker_name}
- 対象期間: {period_key[:4]}-{period_key[4:]}
- 支払金額: ¥{total_amount:,.0f}
- 支払明細ID: {payout_id}
- 承認期限: {approval_deadline.strftime('%Y-%m-%d %H:%M')}

システムにログインして支払明細を確認し、承認処理をお願いします

Accounting {self.sender_signature}
"""

        return EmailTemplate(
            subject=subject,
            body=body,
            to=approver_email,
        )

    def escalation_notification(
        self,
        admin_name: str,
        admin_email: str,
        project_name: str,
        issue_type: str,
        site_manager_name: str,
        deadline: datetime,
        delay_days: int,
        previous_actions: str,
    ) -> EmailTemplate:
        """
        エスカレーション通知メール

        Args:
            admin_name: 管理者名
            admin_email: 管理者メールアドレス
            project_name: 案件名
            issue_type: 対象（シフト確定/CSV提出/CSV修正）
            site_manager_name: 現場管理者名
            deadline: 期限
            delay_days: 遅延日数
            previous_actions: これまでの対応概要

        Returns:
            EmailTemplate
        """
        subject = f"【エスカレーション】対応遅延（{project_name} {issue_type}）"

        body = f"""{admin_name} 様

以下で対応遅延が発生しています
- 案件名: {project_name}
- 対象: {issue_type}
- 現場管理者: {site_manager_name}
- 期限: {deadline.strftime('%Y-%m-%d %H:%M')}
- 遅延日数: {delay_days}
- これまでの対応: {previous_actions}

次の対応方針の判断をお願いします

Ops {self.sender_signature}
"""

        return EmailTemplate(
            subject=subject,
            body=body,
            to=admin_email,
        )
