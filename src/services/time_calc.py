"""
Time calculation utilities
仕様参照: DESIGN_SPEC_v0.3 セクション8.1, 8.2, 8.3
"""
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal

from src.models.enums import RoundingMethod, BreakDeductionRule, TimeCalcMode
from src.exceptions import ValidationException


@dataclass
class TimeCalcResult:
    """時間計算結果"""
    minutes_total: int
    minutes_break: int
    minutes_billable: int
    minutes_night: int | None
    rounding_unit: int
    rounding_method: str
    break_rule: str
    needs_review: bool = False
    review_reason: str | None = None
    warnings: list[str] | None = None


def time_to_minutes(t: time) -> int:
    """timeオブジェクトを0:00からの分数に変換"""
    return t.hour * 60 + t.minute


def calculate_total_minutes(start: time, end: time) -> int:
    """
    開始・終了時刻から総分数を計算
    日跨ぎに対応
    """
    start_mins = time_to_minutes(start)
    end_mins = time_to_minutes(end)
    
    if end_mins <= start_mins:
        # 日跨ぎ（例: 22:00 → 06:00）
        return (24 * 60 - start_mins) + end_mins
    else:
        return end_mins - start_mins


def apply_rounding(
    minutes: int,
    unit: int,
    method: RoundingMethod | str,
) -> int:
    """
    時間を丸める
    仕様参照: 8.2 step4
    
    Args:
        minutes: 丸め対象の分数
        unit: 丸め単位（1, 15, 30等）
        method: 丸め方法（floor/ceil/nearest）
    
    Returns:
        丸め後の分数
    """
    if unit <= 0:
        unit = 1
    
    method_str = method.value if isinstance(method, RoundingMethod) else method
    
    if method_str == RoundingMethod.FLOOR.value:
        return (minutes // unit) * unit
    elif method_str == RoundingMethod.CEIL.value:
        return math.ceil(minutes / unit) * unit
    elif method_str == RoundingMethod.NEAREST.value:
        return round(minutes / unit) * unit
    else:
        # デフォルトはceil
        return math.ceil(minutes / unit) * unit


def calculate_night_minutes(
    start: time,
    end: time,
    night_start: time,
    night_end: time,
) -> int:
    """
    深夜時間を計算
    仕様参照: 8.2 step5
    
    Args:
        start: 勤務開始時刻
        end: 勤務終了時刻
        night_start: 深夜帯開始（例: 22:00）
        night_end: 深夜帯終了（例: 05:00）
    
    Returns:
        深夜帯に重なる分数
    """
    # 簡易実装: 深夜帯は通常 22:00-05:00 のように日跨ぎ
    # 勤務時間と深夜帯の交差を計算
    
    work_start_mins = time_to_minutes(start)
    work_end_mins = time_to_minutes(end)
    night_start_mins = time_to_minutes(night_start)
    night_end_mins = time_to_minutes(night_end)
    
    # 日跨ぎ対応のため、24時間を2周で考える
    night_minutes = 0
    
    # 深夜帯は night_start → 24:00 → night_end
    # 勤務時間との交差を計算
    
    if work_end_mins <= work_start_mins:
        # 勤務が日跨ぎ
        # 1. work_start → 24:00
        # 2. 0:00 → work_end
        work_ranges = [
            (work_start_mins, 24 * 60),
            (0, work_end_mins),
        ]
    else:
        work_ranges = [(work_start_mins, work_end_mins)]
    
    if night_end_mins <= night_start_mins:
        # 深夜帯が日跨ぎ（通常はこちら）
        night_ranges = [
            (night_start_mins, 24 * 60),
            (0, night_end_mins),
        ]
    else:
        night_ranges = [(night_start_mins, night_end_mins)]
    
    # 交差を計算
    for w_start, w_end in work_ranges:
        for n_start, n_end in night_ranges:
            overlap_start = max(w_start, n_start)
            overlap_end = min(w_end, n_end)
            if overlap_end > overlap_start:
                night_minutes += overlap_end - overlap_start
    
    return night_minutes


def calculate_time(
    start_time: time | None,
    end_time: time | None,
    break_minutes_input: int | None,
    hours_input: Decimal | None,
    *,
    rounding_unit: int = 15,
    rounding_method: str = RoundingMethod.CEIL.value,
    break_rule: str = BreakDeductionRule.AUTO.value,
    time_calc_mode: str = TimeCalcMode.SYSTEM_FIRST.value,
    night_window_start: time | None = None,
    night_window_end: time | None = None,
    store_night_minutes: bool = True,
) -> TimeCalcResult:
    """
    時間計算メイン処理
    仕様参照: 8.2, 8.3
    
    Args:
        start_time: 開始時刻
        end_time: 終了時刻
        break_minutes_input: CSV入力の休憩分数
        hours_input: CSV入力の稼働時間
        rounding_unit: 丸め単位（分）
        rounding_method: 丸め方法
        break_rule: 休憩控除ルール
        time_calc_mode: 時間計算モード
        night_window_start: 深夜帯開始
        night_window_end: 深夜帯終了
        store_night_minutes: 深夜時間を計算・保存するか
    
    Returns:
        TimeCalcResult
    """
    warnings = []
    needs_review = False
    review_reason = None
    
    # csv_hours_first モードの場合
    if time_calc_mode == TimeCalcMode.CSV_HOURS_FIRST.value:
        if hours_input is not None:
            minutes_billable = int(hours_input * 60)
            
            # start/endがある場合は比較用
            minutes_total = 0
            if start_time and end_time:
                minutes_total = calculate_total_minutes(start_time, end_time)
                # 差が大きい場合は要確認
                expected_minutes = minutes_total - (break_minutes_input or 0)
                if abs(expected_minutes - minutes_billable) > 30:  # 30分以上の差
                    needs_review = True
                    review_reason = f"CSV hours ({hours_input}h) differs from calculated ({expected_minutes}min)"
            
            return TimeCalcResult(
                minutes_total=minutes_total,
                minutes_break=break_minutes_input or 0,
                minutes_billable=minutes_billable,
                minutes_night=None,
                rounding_unit=rounding_unit,
                rounding_method=rounding_method,
                break_rule=break_rule,
                needs_review=needs_review,
                review_reason=review_reason,
            )
        else:
            # hours_inputがない場合はsystem計算にフォールバック
            pass
    
    # system_first モード（または csv_hours_first でhours_inputがない場合）
    if not start_time or not end_time:
        raise ValueError("start_time and end_time are required for system_first mode")
    
    # Step 1: minutes_total
    minutes_total = calculate_total_minutes(start_time, end_time)
    
    # Step 2: minutes_break
    minutes_break = 0
    if break_rule == BreakDeductionRule.AUTO.value:
        if break_minutes_input is not None:
            minutes_break = break_minutes_input
        else:
            # break_minutes空なら0で警告
            minutes_break = 0
            warnings.append("break_minutes is empty, using 0")
    elif break_rule == BreakDeductionRule.MANUAL.value:
        if break_minutes_input is None:
            raise ValueError("break_minutes is required when break_deduction_rule=manual")
        minutes_break = break_minutes_input
    elif break_rule == BreakDeductionRule.NONE.value:
        minutes_break = 0
    
    # Step 3: minutes_billable (before rounding)
    minutes_billable_raw = max(minutes_total - minutes_break, 0)
    
    # Step 4: rounding
    minutes_billable = apply_rounding(
        minutes_billable_raw,
        rounding_unit,
        rounding_method,
    )
    
    # Step 5: night_minutes
    minutes_night = None
    if store_night_minutes and night_window_start and night_window_end:
        minutes_night = calculate_night_minutes(
            start_time, end_time, night_window_start, night_window_end
        )
    
    # Step 7: hours比較（差が閾値超なら要確認）
    if hours_input is not None:
        hours_input_minutes = int(hours_input * 60)
        if abs(hours_input_minutes - minutes_billable) > 30:  # 30分以上の差
            needs_review = True
            review_reason = f"CSV hours ({hours_input}h={hours_input_minutes}min) differs from calculated ({minutes_billable}min)"
    
    return TimeCalcResult(
        minutes_total=minutes_total,
        minutes_break=minutes_break,
        minutes_billable=minutes_billable,
        minutes_night=minutes_night,
        rounding_unit=rounding_unit,
        rounding_method=rounding_method,
        break_rule=break_rule,
        needs_review=needs_review,
        review_reason=review_reason,
        warnings=warnings if warnings else None,
    )
