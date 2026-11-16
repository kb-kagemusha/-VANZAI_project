from scripts.compare_holiday_csv import official_dates
import pytest


def test_official_csv_read_only_supports_cp932_and_rejects_missing_year(tmp_path):
    path = tmp_path / "holidays.csv"
    path.write_bytes("国民の祝日・休日月日,国民の祝日・休日名称\n2027/1/1,元日\n2027/1/11,成人の日\n".encode("cp932"))
    assert official_dates(path, 2027) == {"2027-01-01", "2027-01-11"}
    with pytest.raises(ValueError, match="2028"):
        official_dates(path, 2028)
