"""会社情報（0.49.8、DEC-082）。

保存先は既存の請求書の発行元設定（order_billing_issuer の1行）。サイドメニュー「会社情報」で編集し、
依頼元別の月次請求書と、実績からの請求書・見積書の発行元に使う。発行した書類には、その時点の内容を
別に保存するので、ここを変えても発行済みの書類は変わらない。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.order_billing import OrderBillingIssuer

PROFILE_KEYS = (
    "revision",
    "name",
    "postal_code",
    "address",
    "phone",
    "email",
    "representative",
    "registration_number",
    "bank_details",
    "payment_terms",
)


def profile_snapshot(row: OrderBillingIssuer) -> dict:
    return {key: getattr(row, key) or ("" if key != "revision" else row.revision) for key in PROFILE_KEYS}


def current_profile(session: Session) -> dict | None:
    """今の会社情報。設定の行がない環境（初期化前・試験）では None。"""
    row = session.get(OrderBillingIssuer, "default")
    return profile_snapshot(row) if row is not None else None


def issuer_lines(snapshot: dict | None) -> list[str]:
    """PDFの発行元の欄に出す行。空の項目は出さない。"""
    if not snapshot:
        return []
    lines = [snapshot.get("name") or ""]
    if snapshot.get("representative"):
        lines.append(f"代表者：{snapshot['representative']}")
    if snapshot.get("postal_code"):
        lines.append(f"〒{snapshot['postal_code']}")
    if snapshot.get("address"):
        lines.append(snapshot["address"])
    if snapshot.get("phone"):
        lines.append(f"TEL：{snapshot['phone']}")
    if snapshot.get("email"):
        lines.append(f"メール：{snapshot['email']}")
    if snapshot.get("registration_number"):
        lines.append(f"登録番号：{snapshot['registration_number']}")
    return [line for line in lines if line]
