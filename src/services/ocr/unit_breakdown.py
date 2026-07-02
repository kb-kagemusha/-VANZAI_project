"""Unit-count breakdown solver for Paygate settlement receipts.

計画書 v4 §5.2 / FR-2.4, FR-2.5 に対応。

レシートには単価別（¥980 / ¥1,480 / ¥2,980）の内訳・数量は印字されないため、
現金売上・PAYGATE POS売上・通常取引数から数学的に内訳を逆算する。
一意に解けない場合は "ambiguous"、解が存在しない場合は "invalid" を返し、
いずれも人手確認（manual_review）に回す。

クレジット売上・その他支払いが非ゼロの場合は、ソルバー対象外（現金/PAYGATE POSの
2値限定）として無条件で "manual" を返す（レビュー②の指摘に基づく仕様）。
"""
from __future__ import annotations

from decimal import Decimal
from typing import TypedDict

UNIT_PRICES: tuple[int, int, int] = (980, 1480, 2980)


class UnitBreakdownResult(TypedDict):
    unit_breakdown_status: str  # resolved | ambiguous | invalid | manual
    unit_breakdown_json: dict | None
    cash_unit_count: int | None
    pos_unit_count: int | None


def _to_int_yen(value: Decimal | None) -> int:
    if value is None:
        return 0
    return int(value)


def solve_unit_combinations(amount_yen: int) -> list[tuple[int, int, int]]:
    """Return all (n980, n1480, n2980) combinations whose value sums to amount_yen."""
    if amount_yen < 0:
        return []
    if amount_yen == 0:
        return [(0, 0, 0)]

    solutions: list[tuple[int, int, int]] = []
    max_2980 = amount_yen // UNIT_PRICES[2]
    for n2980 in range(max_2980 + 1):
        remaining_after_2980 = amount_yen - n2980 * UNIT_PRICES[2]
        max_1480 = remaining_after_2980 // UNIT_PRICES[1]
        for n1480 in range(max_1480 + 1):
            remaining = remaining_after_2980 - n1480 * UNIT_PRICES[1]
            if remaining % UNIT_PRICES[0] == 0:
                n980 = remaining // UNIT_PRICES[0]
                solutions.append((n980, n1480, n2980))
    return solutions


def _combo_to_dict(combo: tuple[int, int, int]) -> dict:
    return {"980": combo[0], "1480": combo[1], "2980": combo[2]}


def compute_unit_breakdown(
    *,
    cash_sales: Decimal | None,
    pos_sales: Decimal | None,
    credit_sales: Decimal | None,
    other_payment: Decimal | None,
    transaction_count: int | None,
) -> UnitBreakdownResult:
    """Solve cash/PAYGATE POS unit counts from settlement totals.

    Missing (None) sub-amounts are treated as 0 for the purpose of solving; if that
    assumption is wrong, `validate_settlement_blocking_errors` will already flag an
    amount_breakdown_mismatch and block OCR confirmation independently of this result.
    """
    credit_yen = _to_int_yen(credit_sales)
    other_yen = _to_int_yen(other_payment)
    if credit_yen != 0 or other_yen != 0:
        return UnitBreakdownResult(
            unit_breakdown_status="manual",
            unit_breakdown_json=None,
            cash_unit_count=None,
            pos_unit_count=None,
        )

    cash_yen = _to_int_yen(cash_sales)
    pos_yen = _to_int_yen(pos_sales)

    cash_solutions = solve_unit_combinations(cash_yen)
    pos_solutions = solve_unit_combinations(pos_yen)

    combos: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = []
    for cash_combo in cash_solutions:
        cash_units = sum(cash_combo)
        for pos_combo in pos_solutions:
            pos_units = sum(pos_combo)
            if transaction_count is not None and (cash_units + pos_units) != transaction_count:
                continue
            combos.append((cash_combo, pos_combo))

    if not combos:
        return UnitBreakdownResult(
            unit_breakdown_status="invalid",
            unit_breakdown_json=None,
            cash_unit_count=None,
            pos_unit_count=None,
        )

    if len(combos) == 1:
        cash_combo, pos_combo = combos[0]
        return UnitBreakdownResult(
            unit_breakdown_status="resolved",
            unit_breakdown_json={
                "cash": _combo_to_dict(cash_combo),
                "paygate_pos": _combo_to_dict(pos_combo),
            },
            cash_unit_count=sum(cash_combo),
            pos_unit_count=sum(pos_combo),
        )

    return UnitBreakdownResult(
        unit_breakdown_status="ambiguous",
        unit_breakdown_json={
            "candidates": [
                {"cash": _combo_to_dict(cash_combo), "paygate_pos": _combo_to_dict(pos_combo)}
                for cash_combo, pos_combo in combos[:20]
            ],
            "candidate_count": len(combos),
        },
        cash_unit_count=None,
        pos_unit_count=None,
    )
