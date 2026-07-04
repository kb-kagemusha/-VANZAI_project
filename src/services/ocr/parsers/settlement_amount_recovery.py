"""Recover settlement amounts when OCR misaligns labels and values."""
from __future__ import annotations

import re
from decimal import Decimal

from src.services.ocr.parsers.settlement_amount import (
    is_valid_settlement_unit_sales_amount,
    sanitize_settlement_amount,
    sanitize_settlement_sales_amount,
)

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


def _needs_sales_recovery(value: Decimal | None) -> bool:
    if value is None or value == 0:
        return True
    return not is_valid_settlement_unit_sales_amount(value)


def _accept_sales_amount(amount: Decimal | None) -> bool:
    return amount is not None and amount > 0 and is_valid_settlement_unit_sales_amount(amount)


def _infer_sales_from_total(repaired: dict[str, Decimal | None]) -> None:
    total = repaired.get("total")
    if total is None:
        return
    cash = repaired.get("cash") or Decimal(0)
    credit = repaired.get("credit") or Decimal(0)
    other = repaired.get("other") or Decimal(0)
    pos = repaired.get("pos") or Decimal(0)

    if not (pos > 0 and is_valid_settlement_unit_sales_amount(pos)):
        remainder = total - cash - credit - other
        if is_valid_settlement_unit_sales_amount(remainder):
            repaired["pos"] = remainder
        elif pos > 0:
            repaired["pos"] = Decimal(0)

    cash = repaired.get("cash") or Decimal(0)
    if not (cash > 0 and is_valid_settlement_unit_sales_amount(cash)):
        remainder = total - (repaired.get("pos") or Decimal(0)) - credit - other
        if is_valid_settlement_unit_sales_amount(remainder):
            repaired["cash"] = remainder


def repair_settlement_amounts(
    text: str,
    amounts: dict[str, Decimal | None],
) -> dict[str, Decimal | None]:
    """ラベルと金額が別行にずれた本番OCR向けの補正。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    repaired = dict(amounts)

    for key in ("cash", "pos", "credit"):
        value = repaired.get(key)
        if value is not None and value > 0 and not is_valid_settlement_unit_sales_amount(value):
            repaired[key] = Decimal(0)

    credit = repaired.get("credit")
    if credit is not None and 0 < credit < 100 and not is_valid_settlement_unit_sales_amount(credit):
        repaired["credit"] = Decimal(0)

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
        if "現金売上" not in compact and "現会売上" not in compact:
            continue
        if not _needs_sales_recovery(repaired.get("cash")):
            break
        if index == 0:
            break
        previous = lines[index - 1]
        if _is_skipped_amount_context(previous):
            break
        amount = _standalone_amount(previous)
        if _accept_sales_amount(amount):
            repaired["cash"] = amount
        break

    for index, line in enumerate(lines):
        compact = _compact(line).upper().replace("-", "")
        if "PAYGATEPOS" not in compact:
            continue
        if not _needs_sales_recovery(repaired.get("pos")):
            break
        for lookback in range(index - 1, max(index - 5, -1), -1):
            candidate = lines[lookback]
            candidate_compact = _compact(candidate)
            if any(
                marker in candidate_compact
                for marker in ("その他支払", "現金売上", "クレジット", "小計", "合計", "消費税")
            ):
                break
            if _is_skipped_amount_context(candidate) and "POS" not in _compact(candidate).upper():
                continue
            amount = _standalone_amount(candidate)
            if _accept_sales_amount(amount):
                repaired["pos"] = amount
                break
        break

    _infer_sales_from_total(repaired)

    if repaired.get("total") is None:
        cash = repaired.get("cash")
        subtotal = repaired.get("subtotal")
        credit = repaired.get("credit") or Decimal(0)
        pos = repaired.get("pos") or Decimal(0)
        other = repaired.get("other") or Decimal(0)
        if cash is not None and _accept_sales_amount(cash):
            if credit == 0 and pos == 0 and other == 0:
                repaired["total"] = cash
            elif subtotal is not None and subtotal == cash:
                repaired["total"] = cash

    if repaired.get("total") is not None and repaired.get("cash") == repaired.get("total"):
        for key in ("credit", "pos", "other"):
            value = repaired.get(key)
            if value and (value < 100 or not is_valid_settlement_unit_sales_amount(value)):
                repaired[key] = Decimal(0)

    other = repaired.get("other")
    pos = repaired.get("pos")
    if other not in (None, Decimal(0)) and pos not in (None, Decimal(0)) and other == pos:
        repaired["other"] = Decimal(0)

    return repaired
