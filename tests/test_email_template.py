"""
メールテンプレートサービスのテスト
"""
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal

from src.services.email_template import EmailTemplateService


def test_shift_unconfirmed_reminder():
    """シフト未確定催促メールテスト"""
    service = EmailTemplateService(sender_signature="テスト署名")
    
    template = service.shift_unconfirmed_reminder(
        site_manager_name="山田太郎",
        site_manager_email="yamada@example.com",
        project_name="新宿警備案件",
        week_start=date(2025, 1, 13),
        week_end=date(2025, 1, 19),
        unconfirmed_count=5,
        deadline=datetime(2025, 1, 10, 17, 0, tzinfo=timezone.utc),
    )
    
    assert template.to == "yamada@example.com"
    assert "【要対応】シフト未確定枠があります" in template.subject
    assert "新宿警備案件" in template.subject
    assert "山田太郎 様" in template.body
    assert "未確定枠数: 5" in template.body
    assert "テスト署名" in template.body


def test_csv_unsubmitted_reminder():
    """CSV未提出催促メールテスト"""
    service = EmailTemplateService()
    
    template = service.csv_unsubmitted_reminder(
        site_manager_name="佐藤花子",
        site_manager_email="sato@example.com",
        project_name="渋谷警備案件",
        target_month="202501",
        deadline=datetime(2025, 2, 5, 17, 0, tzinfo=timezone.utc),
    )
    
    assert template.to == "sato@example.com"
    assert "【要対応】実績CSV未提出です" in template.subject
    assert "2025-01" in template.subject
    assert "佐藤花子 様" in template.body
    assert "対象月: 2025-01" in template.body


def test_csv_error_rejection():
    """CSVエラー差戻しメールテスト"""
    service = EmailTemplateService()
    
    error_samples = [
        {"line": 10, "reason": "アサインメントが見つかりません", "key": "2025-01-10 山田太郎"},
        {"line": 15, "reason": "時刻フォーマットエラー", "key": "2025-01-15 鈴木一郎"},
        {"line": 20, "reason": "必須項目が未入力です", "key": "2025-01-20 田中次郎"},
    ]
    
    template = service.csv_error_rejection(
        site_manager_name="山田太郎",
        site_manager_email="yamada@example.com",
        project_name="新宿警備案件",
        target_month="202501",
        import_datetime=datetime(2025, 2, 1, 10, 30, tzinfo=timezone.utc),
        error_count=15,
        error_samples=error_samples,
        correction_deadline=datetime(2025, 2, 3, 17, 0, tzinfo=timezone.utc),
    )
    
    assert template.to == "yamada@example.com"
    assert "【要修正】実績CSVにエラーがあります" in template.subject
    assert "エラー件数: 15" in template.body
    assert "10行目: アサインメントが見つかりません" in template.body
    assert "15行目: 時刻フォーマットエラー" in template.body
    assert "20行目: 必須項目が未入力です" in template.body


def test_csv_error_rejection_truncates_errors():
    """CSVエラー差戻しメール（エラー件数が多い場合の切り詰めテスト）"""
    service = EmailTemplateService()
    
    # 10件のエラーサンプルを渡す
    error_samples = [
        {"line": i, "reason": f"エラー{i}", "key": f"キー{i}"}
        for i in range(1, 11)
    ]
    
    template = service.csv_error_rejection(
        site_manager_name="山田太郎",
        site_manager_email="yamada@example.com",
        project_name="テスト案件",
        target_month="202501",
        import_datetime=datetime(2025, 2, 1, 10, 0, tzinfo=timezone.utc),
        error_count=100,
        error_samples=error_samples,
        correction_deadline=datetime(2025, 2, 3, 17, 0, tzinfo=timezone.utc),
    )
    
    # 最大5件までしか表示されない
    assert "1行目:" in template.body
    assert "5行目:" in template.body
    assert "6行目:" not in template.body


def test_invoice_approval_request():
    """請求書承認依頼メールテスト"""
    service = EmailTemplateService()
    
    template = service.invoice_approval_request(
        approver_name="経理担当者",
        approver_email="accounting@example.com",
        client_name="テスト株式会社",
        period_key="202501",
        total_amount=1100000.0,
        invoice_id="01INV001",
        approval_deadline=datetime(2025, 2, 10, 17, 0, tzinfo=timezone.utc),
    )
    
    assert template.to == "accounting@example.com"
    assert "【承認依頼】請求書承認をお願いします" in template.subject
    assert "テスト株式会社" in template.subject
    assert "請求金額: ¥1,100,000" in template.body
    assert "請求書ID: 01INV001" in template.body


def test_payout_approval_request():
    """支払承認依頼メールテスト"""
    service = EmailTemplateService()
    
    template = service.payout_approval_request(
        approver_name="経理担当者",
        approver_email="accounting@example.com",
        worker_name="山田太郎",
        period_key="202501",
        total_amount=320000.0,
        payout_id="01PAY001",
        approval_deadline=datetime(2025, 2, 15, 17, 0, tzinfo=timezone.utc),
    )
    
    assert template.to == "accounting@example.com"
    assert "【承認依頼】支払承認をお願いします" in template.subject
    assert "山田太郎" in template.subject
    assert "支払金額: ¥320,000" in template.body
    assert "支払明細ID: 01PAY001" in template.body


def test_escalation_notification():
    """エスカレーション通知メールテスト"""
    service = EmailTemplateService()
    
    template = service.escalation_notification(
        admin_name="管理者",
        admin_email="admin@example.com",
        project_name="新宿警備案件",
        issue_type="CSV提出",
        site_manager_name="山田太郎",
        deadline=datetime(2025, 2, 5, 17, 0, tzinfo=timezone.utc),
        delay_days=3,
        previous_actions="2回催促メール送信済み、返信なし",
    )
    
    assert template.to == "admin@example.com"
    assert "【エスカレーション】対応遅延" in template.subject
    assert "新宿警備案件" in template.subject
    assert "遅延日数: 3" in template.body
    assert "2回催促メール送信済み、返信なし" in template.body


def test_email_template_signature_customization():
    """署名カスタマイズテスト"""
    service = EmailTemplateService(sender_signature="カスタム署名")
    
    template = service.shift_unconfirmed_reminder(
        site_manager_name="テスト",
        site_manager_email="test@example.com",
        project_name="テスト案件",
        week_start=date(2025, 1, 13),
        week_end=date(2025, 1, 19),
        unconfirmed_count=1,
        deadline=datetime(2025, 1, 10, 17, 0, tzinfo=timezone.utc),
    )
    
    assert "カスタム署名" in template.body
    assert "VANZAI管理システム" not in template.body
