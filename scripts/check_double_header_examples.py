"""ダブルヘッダーの実例（tests/fixtures/double_header_examples/*.json）を読み、移動の間隔と初期値を並べて出す（DEC-148）。

使い方：python scripts/check_double_header_examples.py [--minutes 60]
DBには触れない。初期値を変えるときの根拠を出すだけ（変更は管理画面の「初期値を変更」で行う）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.domain import order_bundle as rules  # noqa: E402
from tests.double_header_examples import load_examples, schedule_of  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minutes", type=int, default=rules.PROVISIONAL_TRAVEL_MINUTES, help="比べる移動に必要な時間（分）")
    args = parser.parse_args()
    examples = load_examples()
    if not examples:
        print("実例はまだありません（tests/fixtures/double_header_examples/ に置いてください）。")
        return 0
    gaps = []
    print(f"比べる移動に必要な時間：{args.minutes}分")
    for path, example in examples:
        first, second = (schedule_of(leg, "2026-01-01") for leg in example["legs"])
        result = rules.check(first, second, args.minutes)
        pay = rules.legs_pay_total(first, second)
        actual = example.get("actual_travel_minutes")
        state = "重なり" if result["overlap"] else ("不足" if result["short"] else "足りる")
        print(f"- {example['label']}（{path.name}）：間隔 {result['gap_minutes']}分／{state}／実際の移動 {actual if actual is not None else '不明'}分／報酬の合計 {pay['total'] or '時給を含む'}")
        if result["gap_minutes"] is not None:
            gaps.append(result["gap_minutes"])
        if actual is not None and actual > args.minutes:
            print(f"  ※実際の移動（{actual}分）が初期値より長い例です")
    if gaps:
        print(f"間隔の最小 {min(gaps)}分・最大 {max(gaps)}分（{len(gaps)}例）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
