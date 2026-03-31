"""
メール送信サービス

EmailTemplateServiceと統合してSMTP経由でメール送信を行う
Gmail, SendGrid, AWS SES対応
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import Optional
import os

from src.services.email_template import EmailTemplate


@dataclass
class SMTPConfig:
    """SMTP設定"""
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    
    @classmethod
    def from_env(cls, provider: str = "gmail") -> "SMTPConfig":
        """
        環境変数からSMTP設定を取得
        
        Args:
            provider: "gmail", "sendgrid", "ses"
        
        Returns:
            SMTPConfig
        """
        if provider == "gmail":
            return cls(
                host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
                port=int(os.getenv("SMTP_PORT", "587")),
                username=os.getenv("SMTP_USERNAME", ""),
                password=os.getenv("SMTP_PASSWORD", ""),
                use_tls=True,
                from_email=os.getenv("SMTP_FROM_EMAIL"),
                from_name=os.getenv("SMTP_FROM_NAME", "VANZAI System")
            )
        elif provider == "sendgrid":
            return cls(
                host="smtp.sendgrid.net",
                port=587,
                username="apikey",
                password=os.getenv("SENDGRID_API_KEY", ""),
                use_tls=True,
                from_email=os.getenv("SMTP_FROM_EMAIL"),
                from_name=os.getenv("SMTP_FROM_NAME", "VANZAI System")
            )
        elif provider == "ses":
            region = os.getenv("AWS_REGION", "us-east-1")
            return cls(
                host=f"email-smtp.{region}.amazonaws.com",
                port=587,
                username=os.getenv("AWS_SMTP_USERNAME", ""),
                password=os.getenv("AWS_SMTP_PASSWORD", ""),
                use_tls=True,
                from_email=os.getenv("SMTP_FROM_EMAIL"),
                from_name=os.getenv("SMTP_FROM_NAME", "VANZAI System")
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")


class EmailSender:
    """
    メール送信サービス
    
    EmailTemplateServiceで生成したテンプレートをSMTP経由で送信
    """
    
    def __init__(self, config: SMTPConfig):
        """
        Args:
            config: SMTP設定
        """
        self.config = config
    
    def send_email(
        self,
        template: EmailTemplate,
        dry_run: bool = False
    ) -> bool:
        """
        メール送信
        
        Args:
            template: EmailTemplateインスタンス
            dry_run: True の場合は送信せずログ出力のみ
        
        Returns:
            送信成功: True, 失敗: False
        """
        # 送信元アドレス
        from_email = self.config.from_email or self.config.username
        from_name = self.config.from_name or "VANZAI System"
        
        # MIMEメッセージ構築
        msg = MIMEMultipart()
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = template.to
        if template.cc:
            msg["Cc"] = template.cc
        msg["Subject"] = template.subject
        
        # 本文（プレーンテキスト）
        msg.attach(MIMEText(template.body, "plain", "utf-8"))
        
        if dry_run:
            print("=== DRY RUN: Email NOT sent ===")
            print(f"From: {msg['From']}")
            print(f"To: {msg['To']}")
            print(f"Cc: {msg.get('Cc', 'None')}")
            print(f"Subject: {msg['Subject']}")
            print(f"Body:\n{template.body}")
            print("=" * 50)
            return True
        
        try:
            # SMTP接続
            if self.config.use_tls:
                server = smtplib.SMTP(self.config.host, self.config.port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.config.host, self.config.port)
            
            # ログイン
            if self.config.username and self.config.password:
                server.login(self.config.username, self.config.password)
            
            # 送信
            recipients = [template.to]
            if template.cc:
                recipients.extend(template.cc.split(","))
            
            server.sendmail(from_email, recipients, msg.as_string())
            server.quit()
            
            return True
        
        except Exception as e:
            print(f"Email send failed: {str(e)}")
            return False
    
    def send_bulk_emails(
        self,
        templates: list[EmailTemplate],
        dry_run: bool = False
    ) -> dict[str, int]:
        """
        一括メール送信
        
        Args:
            templates: EmailTemplateリスト
            dry_run: True の場合は送信せずログ出力のみ
        
        Returns:
            {"success": 成功数, "failed": 失敗数}
        """
        success_count = 0
        failed_count = 0
        
        for template in templates:
            if self.send_email(template, dry_run=dry_run):
                success_count += 1
            else:
                failed_count += 1
        
        return {"success": success_count, "failed": failed_count}


# ===========================
# ユーティリティ関数
# ===========================

def get_default_sender(provider: str = "gmail") -> EmailSender:
    """
    デフォルトのEmailSenderインスタンスを取得
    
    Args:
        provider: "gmail", "sendgrid", "ses"
    
    Returns:
        EmailSender
    """
    config = SMTPConfig.from_env(provider)
    kintone_from_email, kintone_from_name = _load_kintone_email_overrides()
    if kintone_from_email:
        config.from_email = kintone_from_email
    if kintone_from_name:
        config.from_name = kintone_from_name
    return EmailSender(config)


def send_quick_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    provider: str = "gmail",
    dry_run: bool = False
) -> bool:
    """
    クイックメール送信（テンプレート不要）
    
    Args:
        to: 送信先
        subject: 件名
        body: 本文
        cc: CC
        provider: SMTPプロバイダー
        dry_run: True の場合は送信せずログ出力のみ
    
    Returns:
        送信成功: True, 失敗: False
    """
    template = EmailTemplate(
        subject=subject,
        body=body,
        to=to,
        cc=cc
    )
    
    sender = get_default_sender(provider)
    return sender.send_email(template, dry_run=dry_run)


def _load_kintone_email_overrides() -> tuple[Optional[str], Optional[str]]:
    """Kintoneの設定アプリから送信元メールを取得する（任意）。"""
    app_id_raw = os.getenv("KINTONE_APP_SYSTEM_SETTINGS")
    token = os.getenv("KINTONE_TOKEN_SYSTEM_SETTINGS")
    if not app_id_raw or not token:
        return None, None

    try:
        app_id = int(app_id_raw)
    except ValueError:
        print("KINTONE_APP_SYSTEM_SETTINGS is not a valid integer")
        return None, None

    try:
        from src.services.kintone_service import KintoneConfig, KintoneService
    except Exception as exc:  # pragma: no cover - 実行環境に依存
        print(f"Failed to import KintoneService: {exc}")
        return None, None

    config = KintoneConfig()
    service = KintoneService(config, api_token=token)

    try:
        records = service.get_records(
            app_id,
            query='settings_key = "email"',
            fields=["settings_key", "smtp_from_email", "smtp_from_name"],
        )
    except Exception as exc:
        print(f"Failed to load email settings from Kintone: {exc}")
        return None, None

    if not records:
        return None, None

    record = records[0]

    def _get_value(field_code: str) -> Optional[str]:
        field = record.get(field_code)
        if isinstance(field, dict):
            value = field.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    return _get_value("smtp_from_email"), _get_value("smtp_from_name")
