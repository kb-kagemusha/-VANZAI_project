"""
Time calculation tests

仕様参照: DESIGN_SPEC_v0.3 セクション8
"""
import pytest
from datetime import time
from decimal import Decimal

from src.services.time_calc import (
    calculate_time,
    calculate_total_minutes,
    apply_rounding,
    calculate_night_minutes,
    TimeCalcResult,
)
from src.models.enums import RoundingMethod, BreakDeductionRule, TimeCalcMode


class TestCalculateTotalMinutes:
    """総時間計算テスト"""
    
    def test_normal_day(self):
        """通常の日中勤務"""
        result = calculate_total_minutes(time(9, 0), time(18, 0))
        assert result == 540  # 9時間
    
    def test_overnight(self):
        """日跨ぎ勤務"""
        result = calculate_total_minutes(time(22, 0), time(6, 0))
        assert result == 480  # 8時間
    
    def test_same_time(self):
        """同時刻（日跨ぎ24時間勤務として扱われる）"""
        result = calculate_total_minutes(time(9, 0), time(9, 0))
        assert result == 1440  # 24時間（日跨ぎ扱い）


class TestApplyRounding:
    """丸めテスト（仕様8.2 step4）"""
    
    def test_ceil_15min(self):
        """15分単位切り上げ"""
        assert apply_rounding(61, 15, RoundingMethod.CEIL) == 75
        assert apply_rounding(60, 15, RoundingMethod.CEIL) == 60
        assert apply_rounding(1, 15, RoundingMethod.CEIL) == 15
    
    def test_floor_15min(self):
        """15分単位切り捨て"""
        assert apply_rounding(61, 15, RoundingMethod.FLOOR) == 60
        assert apply_rounding(74, 15, RoundingMethod.FLOOR) == 60
    
    def test_nearest_15min(self):
        """15分単位四捨五入"""
        assert apply_rounding(67, 15, RoundingMethod.NEAREST) == 60
        assert apply_rounding(68, 15, RoundingMethod.NEAREST) == 75


class TestCalculateNightMinutes:
    """深夜時間計算テスト（仕様8.2 step5）"""
    
    def test_no_night_overlap(self):
        """深夜帯と重ならない日中勤務"""
        result = calculate_night_minutes(
            time(9, 0), time(18, 0),
            time(22, 0), time(5, 0),
        )
        assert result == 0
    
    def test_full_night_shift(self):
        """完全に深夜帯内の勤務"""
        result = calculate_night_minutes(
            time(23, 0), time(4, 0),
            time(22, 0), time(5, 0),
        )
        assert result == 300  # 5時間
    
    def test_partial_night_overlap(self):
        """深夜帯と一部重なる勤務"""
        # 20:00-24:00 のうち 22:00-24:00 が深夜
        result = calculate_night_minutes(
            time(20, 0), time(0, 0),
            time(22, 0), time(5, 0),
        )
        assert result == 120  # 2時間


class TestCalculateTime:
    """時間計算メインテスト（仕様8.2, 8.3）"""
    
    def test_system_first_basic(self):
        """system_first モードの基本計算"""
        result = calculate_time(
            start_time=time(9, 0),
            end_time=time(18, 0),
            break_minutes_input=60,
            hours_input=None,
            rounding_unit=15,
            rounding_method=RoundingMethod.CEIL.value,
            break_rule=BreakDeductionRule.AUTO.value,
            time_calc_mode=TimeCalcMode.SYSTEM_FIRST.value,
        )
        
        assert result.minutes_total == 540
        assert result.minutes_break == 60
        assert result.minutes_billable == 480  # 540-60=480, ceil(480/15)*15=480
    
    def test_system_first_with_rounding(self):
        """system_first モードで丸めが発生するケース"""
        result = calculate_time(
            start_time=time(9, 0),
            end_time=time(17, 50),  # 530分
            break_minutes_input=60,
            hours_input=None,
            rounding_unit=15,
            rounding_method=RoundingMethod.CEIL.value,
            break_rule=BreakDeductionRule.AUTO.value,
            time_calc_mode=TimeCalcMode.SYSTEM_FIRST.value,
        )
        
        # 530 - 60 = 470分 → ceil(470/15)*15 = 480分
        assert result.minutes_billable == 480
    
    def test_break_auto_empty_warning(self):
        """休憩が空の場合は警告（仕様8.2 step2）"""
        result = calculate_time(
            start_time=time(9, 0),
            end_time=time(18, 0),
            break_minutes_input=None,  # 空
            hours_input=None,
            rounding_unit=15,
            rounding_method=RoundingMethod.CEIL.value,
            break_rule=BreakDeductionRule.AUTO.value,
            time_calc_mode=TimeCalcMode.SYSTEM_FIRST.value,
        )
        
        assert result.minutes_break == 0
        assert result.warnings is not None
        assert any("break_minutes" in w for w in result.warnings)
    
    def test_break_manual_empty_error(self):
        """休憩manual+空はエラー（仕様8.2 step2）"""
        with pytest.raises(ValueError, match="break_minutes is required"):
            calculate_time(
                start_time=time(9, 0),
                end_time=time(18, 0),
                break_minutes_input=None,
                hours_input=None,
                break_rule=BreakDeductionRule.MANUAL.value,
                time_calc_mode=TimeCalcMode.SYSTEM_FIRST.value,
            )
    
    def test_csv_hours_first(self):
        """csv_hours_first モード（仕様8.3）"""
        result = calculate_time(
            start_time=time(9, 0),
            end_time=time(18, 0),
            break_minutes_input=60,
            hours_input=Decimal("8.0"),  # CSVのhoursを優先
            rounding_unit=15,
            rounding_method=RoundingMethod.CEIL.value,
            break_rule=BreakDeductionRule.AUTO.value,
            time_calc_mode=TimeCalcMode.CSV_HOURS_FIRST.value,
        )
        
        assert result.minutes_billable == 480  # 8.0 * 60
    
    def test_csv_hours_first_with_discrepancy(self):
        """csv_hours_first で差が大きい場合は要確認フラグ"""
        result = calculate_time(
            start_time=time(9, 0),
            end_time=time(18, 0),  # 9時間
            break_minutes_input=60,
            hours_input=Decimal("6.0"),  # 差が大きい
            rounding_unit=15,
            rounding_method=RoundingMethod.CEIL.value,
            break_rule=BreakDeductionRule.AUTO.value,
            time_calc_mode=TimeCalcMode.CSV_HOURS_FIRST.value,
        )
        
        assert result.needs_review is True
        assert result.review_reason is not None
    
    def test_night_minutes_calculation(self):
        """深夜時間が計算される"""
        result = calculate_time(
            start_time=time(20, 0),
            end_time=time(2, 0),  # 6時間（20:00-02:00）
            break_minutes_input=0,
            hours_input=None,
            rounding_unit=15,
            rounding_method=RoundingMethod.CEIL.value,
            break_rule=BreakDeductionRule.AUTO.value,
            time_calc_mode=TimeCalcMode.SYSTEM_FIRST.value,
            night_window_start=time(22, 0),
            night_window_end=time(5, 0),
            store_night_minutes=True,
        )
        
        # 22:00-02:00 = 4時間 = 240分
        assert result.minutes_night == 240
