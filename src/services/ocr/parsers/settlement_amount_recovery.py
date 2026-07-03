"""Recover settlement amounts when OCR misaligns labels and values."""
from __future__ import annotations

import re
from decimal import Decimal

from src.services.ocr.parsers.settlement_amount import sanitize_settlement_amount

_STANDALONE_AMOUNT_RE = re.compile(r"^(?:[¥￥]\s*)?([\d,/]+)\s*$")
_SKIP_AMOUNT_LINE_KEYWORDS = ("売上", "小計", "合計", "計", "税", "PAYGATE", "その他", "精算", "端末", "登録")


def _compact(line: str) -> str:
    return line.replace("　", "").replace(" ", "")


def _standalone_amount(line: str) -> Decimal | None:
    match = _STANDALONE_AMOUNT_RE.match(line.strip())
    if not match:
        return None
    amount, _ = sanitize_settlement_amount(match.group(1))
    return amount


def _is_skipped_amount_context(line: str) -> bool:
    compact = _compact(line)
    return any(keyword in compact for keyword in _SKIP_AMOUNT_LINE_KEYWORDS)


def repair_settlement_amounts(
    text: str,
    amounts: dict[str, Decimal | None],
) -> dict[str, Decimal | None]:
    """ラベルと金額が別行にずれた本番OCR向けの補正。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    repaired = dict(amounts)

    for index, line in enumerate(lines):
        compact = _compact(line)
        if compact in {"-その他", "その他"} or compact.startswith("-その他"):
            if index + 1 < len(lines):
                amount = _standalone_amount(lines[index + 1])
                if amount is not None:
                    total = repaired.get("total")
                    cash = repaired.get("cash") or Decimal(0)
                    pos = repaired.get("pos") or Decimal(0)
                    if amount == 0:
                        repaired["other"] = Decimal(0)
                    elif (
                        total is not None
                        and int(amount) % 10 == 0
                        and cash + pos + amount == total
                    ):
                        repaired["other"] = amount
                    else:
                        repaired["other"] = Decimal(0)
            break

    for index, line in enumerate(lines):
        compact = _compact(line)
        if "現金売上" not in compact:
            continue
        if repaired.get("cash") not in (None, Decimal(0)):
            break
        if index == 0:
            break
        previous = lines[index - 1]
        if _is_skipped_amount_context(previous):
            break
        amount = _standalone_amount(previous)
        if amount is not None and amount > 0:
            repaired["cash"] = amount
        break

    for index, line in enumerate(lines):
        compact = _compact(line).upper().replace("-", "")
        if "PAYGATEPOS" not in compact:
            continue
        if repaired.get("pos") not in (None, Decimal(0)):
            break
        for lookback in range(index - 1, max(index - 5, -1), -1):
            candidate = lines[lookback]
            if "その他支払" in _compact(candidate):
                break
            if _is_skipped_amount_context(candidate) and "POS" not in _compact(candidate).upper():
                continue
            amount = _standalone_amount(candidate)
            if amount is not None and amount > 0:
                repaired["pos"] = amount
                break
        break

    other = repaired.get("other")
    pos = repaired.get("pos")
    if other not in (None, Decimal(0)) and pos not in (None, Decimal(0)) and other == pos:
        repaired["other"] = Decimal(0)

    return repaired
