"""Calendar month boundaries shared by SQLite and PostgreSQL queries."""
from calendar import monthrange
from datetime import date
import re

from src.exceptions import ValidationException


def month_date_range(period_key: str) -> tuple[date, date]:
    """Accept the canonical YYYYMM and existing incentive YYYY-MM format."""
    if not re.fullmatch(r"[0-9]{4}-?(0[1-9]|1[0-2])", period_key):
        raise ValidationException("対象月をYYYYMMまたはYYYY-MMで指定してください")
    compact = period_key.replace("-", "")
    year, month = int(compact[:4]), int(compact[4:])
    if year == 0:
        raise ValidationException("対象月の年は1以上で指定してください")
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])
