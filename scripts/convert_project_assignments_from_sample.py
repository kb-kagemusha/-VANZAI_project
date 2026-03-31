import csv
from pathlib import Path

SOURCE = Path(r"c:\VANZAI_project\kintone_app\sample\案件カテゴリ分け.csv")
OUTPUT = Path(r"c:\VANZAI_project\kintone_app\project_assignments_data.csv")

OUTPUT_COLUMNS = [
    "assignment_id",
    "client_name",
    "client_manager",
    "main_staff",
    "category_major",
    "category_middle",
    "category_minor",
    "start_date",
    "end_date",
    "address",
    "gathering_time",
    "start_time",
    "end_time",
    "dismissal_time",
    "working_hours",
    "detail_url",
    "sales_rule",
    "billing_rate_monthly",
    "billing_rate_daily",
    "billing_rate_incentive",
    "notes",
]

HEADER_KEYS = {
    "assignment_id": "ID",
    "client_name": "会社名",
    "client_manager": "責任者",
    "main_staff": "メイン担当者",
    "category_major": "大カテゴリ",
    "category_middle": "中カテゴリ",
    "category_minor": "小カテゴリ",
    "start_date": "開始期間",
    "end_date": "終了期間",
    "address": "住所",
    "gathering_time": "集合時間",
    "start_time": "開始時間",
    "end_time": "終了時間",
    "dismissal_time": "解散時間",
    "working_hours": "1日稼働時間(h)",
    "detail_url": "詳細リンク",
    "sales_rule": "販売ルール",
    "billing_rate_monthly": "請求単価/月ベース報酬(税抜)",
    "billing_rate_daily": "請求単価/1日1人工/ベース報酬(税抜)",
    "billing_rate_incentive": "請求単価/1日1人工/インセン報酬",
    "notes": "備考",
}


def normalize_header(value: str) -> str:
    return "".join(value.split())


def build_header_index(header_row):
    normalized = {normalize_header(name): idx for idx, name in enumerate(header_row)}
    header_index = {}
    for out_key, jp_header in HEADER_KEYS.items():
        normalized_key = normalize_header(jp_header)
        if normalized_key in normalized:
            header_index[out_key] = normalized[normalized_key]
    return header_index


def row_has_data(row_values):
    return any(value.strip() for value in row_values)


def convert():
    output_rows = []
    header_row = None
    header_index = {}
    rows_written = 0
    rows_skipped = 0

    with SOURCE.open("r", encoding="utf-8", newline="") as source_file:
        reader = csv.reader(source_file)
        for row in reader:
            if not row_has_data(row):
                continue
            if row and row[0] == "ID":
                header_row = row
                header_index = build_header_index(header_row)
                break

        if not header_row:
            raise ValueError("Header row starting with 'ID' was not found.")

        for row in reader:
            if not row_has_data(row):
                continue
            if row and row[0] == "ID":
                continue

            row = row + [""] * (len(header_row) - len(row))
            assignment_id = row[header_index["assignment_id"]].strip() if "assignment_id" in header_index else ""
            category_major = row[header_index["category_major"]].strip() if "category_major" in header_index else ""

            if not assignment_id or not category_major:
                rows_skipped += 1
                continue

            output_row = {}
            for out_key in OUTPUT_COLUMNS:
                index = header_index.get(out_key)
                value = row[index].strip() if index is not None and index < len(row) else ""
                output_row[out_key] = value
            output_rows.append(output_row)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as out_file:
        writer = csv.DictWriter(out_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)
        rows_written = len(output_rows)

    print("==== 変換結果 ====")
    print(f"入力: {SOURCE}")
    print(f"出力: {OUTPUT}")
    print(f"書き込み: {rows_written}件")
    print(f"スキップ: {rows_skipped}件")


if __name__ == "__main__":
    convert()
