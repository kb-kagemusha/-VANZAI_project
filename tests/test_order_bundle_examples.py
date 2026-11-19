"""クライアントから届いたダブルヘッダーの実例で、時間の確認と報酬の合計を確かめる（DEC-148）。

実例は tests/fixtures/double_header_examples/ に置く（置き方は同じフォルダの README.md）。
まだ実例が無いときは、見本（example.template.json）で読み込みの仕組みだけを確かめる。
"""
from __future__ import annotations

import json

import pytest

from src.domain import order_bundle as rules
from tests.double_header_examples import EXAMPLES_DIR, load_examples, schedule_of

DAY = "2026-12-01"
EXAMPLES = load_examples()


def _check(example: dict, minutes: int = rules.PROVISIONAL_TRAVEL_MINUTES) -> tuple[dict, dict]:
    first, second = (schedule_of(leg, DAY) for leg in example["legs"])
    return rules.check(first, second, minutes), rules.legs_pay_total(first, second)


def test_template_example_is_readable_and_matches_its_expectation():
    template = json.loads((EXAMPLES_DIR / "example.template.json").read_text(encoding="utf-8"))
    result, pay = _check(template)
    assert result["complete"] and not result["issues"]
    assert result["overlap"] is template["expect"]["overlap"]
    assert result["gap_minutes"] == template["expect"]["gap_minutes"]
    assert pay["total"] == template["expect"]["pay_total"]


@pytest.mark.parametrize("path,example", EXAMPLES, ids=[path.stem for path, _ in EXAMPLES] or None)
def test_real_examples_match_expectations(path, example):
    result, pay = _check(example)
    assert not result["issues"], f"{path.name}: {result['issues']}"
    expect = example.get("expect") or {}
    if "overlap" in expect:
        assert result["overlap"] is expect["overlap"], path.name
    if expect.get("gap_minutes") is not None:
        assert result["gap_minutes"] == expect["gap_minutes"], path.name
    if "pay_total" in expect:
        assert pay["total"] == expect["pay_total"], path.name
