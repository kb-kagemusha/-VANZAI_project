"""LINE承認の競合試験は、この段階では実行しない。

基盤の準備（test_harness_ready.py）が通っても、ここを合格にしてはならない。
T09、T13、T14、T15 は承認処理の実装後に、同じ試験用PostgreSQLで追加する。
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="LINE承認の競合試験は未実装。基盤の準備であり、競合試験の合格ではない"
)


def test_line_approval_conflict_cases_are_not_claimed_passed():
    raise AssertionError("この試験を合格にしてはならない")
