"""Tests for the paygate_settlement unit-count breakdown solver (計画書 v4 §5.2)."""
from decimal import Decimal

from src.services.ocr.unit_breakdown import compute_unit_breakdown, solve_unit_combinations


def test_solve_unit_combinations_unique_case():
    # 11 units * 980 == 10780, no other combination fits exactly.
    combos = solve_unit_combinations(10780)
    assert (11, 0, 0) in combos


def test_ambiguous_case_from_plan_example():
    # Plan example: transaction_count=5, total=6900 has (>=) 2 valid combinations.
    combos = [c for c in solve_unit_combinations(6900) if sum(c) == 5]
    assert (1, 4, 0) in combos
    assert (4, 0, 1) in combos
    assert len(combos) >= 2


def test_compute_unit_breakdown_resolved():
    result = compute_unit_breakdown(
        cash_sales=Decimal("10780"),
        pos_sales=None,
        credit_sales=Decimal("0"),
        other_payment=None,
        transaction_count=11,
    )
    assert result["unit_breakdown_status"] == "resolved"
    assert result["cash_unit_count"] == 11
    assert result["pos_unit_count"] == 0


def test_compute_unit_breakdown_ambiguous():
    result = compute_unit_breakdown(
        cash_sales=Decimal("6900"),
        pos_sales=None,
        credit_sales=None,
        other_payment=None,
        transaction_count=5,
    )
    assert result["unit_breakdown_status"] == "ambiguous"
    assert result["cash_unit_count"] is None


def test_compute_unit_breakdown_manual_when_credit_sales_nonzero():
    result = compute_unit_breakdown(
        cash_sales=Decimal("6860"),
        pos_sales=Decimal("1960"),
        credit_sales=Decimal("500"),
        other_payment=None,
        transaction_count=9,
    )
    assert result["unit_breakdown_status"] == "manual"


def test_compute_unit_breakdown_manual_when_other_payment_nonzero():
    result = compute_unit_breakdown(
        cash_sales=Decimal("980"),
        pos_sales=Decimal("980"),
        credit_sales=None,
        other_payment=Decimal("10"),
        transaction_count=2,
    )
    assert result["unit_breakdown_status"] == "manual"


def test_compute_unit_breakdown_invalid_when_no_combo_matches_transaction_count():
    result = compute_unit_breakdown(
        cash_sales=Decimal("980"),
        pos_sales=None,
        credit_sales=None,
        other_payment=None,
        transaction_count=5,
    )
    assert result["unit_breakdown_status"] == "invalid"
