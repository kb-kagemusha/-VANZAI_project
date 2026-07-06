"""Tests for misaligned settlement amount recovery."""
from decimal import Decimal

from src.services.ocr.parsers.settlement_amount_recovery import (
    reconcile_subtotal_total_consistency,
    repair_settlement_amounts,
)


def test_repair_cash_amount_on_line_before_label():
    text = """
合計
5,880
3,920
現金売上
0
"""
    amounts = repair_settlement_amounts(text, {"cash": Decimal(0), "total": Decimal("5880")})
    assert amounts["cash"] == Decimal("3920")


def test_repair_pos_amount_before_paygate_label():
    text = """
その他支払い
1,960
-PAYGATE POS
0
"""
    amounts = repair_settlement_amounts(text, {"pos": Decimal(0)})
    assert amounts["pos"] == Decimal("1960")


def test_repair_pos_rejects_ten_and_recovers_from_lookback():
    text = """
その他支払い
1,960
-PAYGATE POS
10
-その他
0
"""
    amounts = repair_settlement_amounts(
        text,
        {"total": Decimal("5880"), "cash": Decimal("3920"), "pos": Decimal("10")},
    )
    assert amounts["pos"] == Decimal("1960")


def test_infer_pos_from_total_when_ocr_reads_ten():
    text = """
合計
5,880
3,920
現金売上
0
-PAYGATE POS
10
"""
    amounts = repair_settlement_amounts(
        text,
        {"total": Decimal("5880"), "cash": Decimal("3920"), "pos": Decimal("10")},
    )
    assert amounts["pos"] == Decimal("1960")


def test_other_payment_ignores_misaligned_tax_amount():
    text = """
その他支払い
1,960
-PAYGATE POS
0
-その他
534
消費税
534
"""
    amounts = repair_settlement_amounts(
        text,
        {
            "total": Decimal("5880"),
            "cash": Decimal("3920"),
            "pos": Decimal("1960"),
            "other": Decimal("1960"),
        },
    )
    assert amounts["other"] == Decimal(0)


def test_reconcile_subtotal_greater_than_total_uses_subtotal_and_infers_pos():
    text = """
小計
15,680
合計
15/880
現金売上
5,880
-PAYGATE POS
9,800
通常取引数
16
"""
    amounts = repair_settlement_amounts(
        text,
        {
            "subtotal": Decimal("15680"),
            "total": Decimal("5880"),
            "cash": Decimal("5880"),
            "pos": Decimal(0),
        },
    )
    amounts, reason = reconcile_subtotal_total_consistency(text, amounts)
    assert reason == "subtotal_exceeds_total"
    assert amounts["total"] == Decimal("15680")
    assert amounts["cash"] == Decimal("5880")
    assert amounts["pos"] == Decimal("9800")
