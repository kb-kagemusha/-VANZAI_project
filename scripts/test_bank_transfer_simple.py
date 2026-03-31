#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
銀行振込ファイル生成の簡易テスト
Task 11: Bank transfer file generation
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import csv
from datetime import datetime, date
import os

from src.services.bank_transfer import BankTransferRecord, BankTransferBatch

CSV_PATH = "kintone_app/bank_transfers_sjis.csv"
OUT_DIR = "storage/bank_transfers"

ACCOUNT_TYPE_MAP = {
    "ordinary": "1",
    "普通": "1",
    "当座": "2",
    "checking": "2",
}


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> int:
    if not os.path.exists(CSV_PATH):
        print(f"❌ CSVが見つかりません: {CSV_PATH}")
        return 1

    records = []
    batch_id = None

    with open(CSV_PATH, "r", encoding="cp932", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("id"):
                continue

            if not batch_id:
                batch_id = row.get("batch_id") or None

            account_type_raw = (row.get("account_type") or "").strip()
            account_type = ACCOUNT_TYPE_MAP.get(account_type_raw, "1")

            transfer_date_str = (row.get("transfer_date") or "").strip()
            transfer_date = parse_date(transfer_date_str) if transfer_date_str else date.today()

            record = BankTransferRecord(
                recipient_name=(row.get("account_holder") or "").strip(),
                bank_code=(row.get("bank_code") or "").strip(),
                branch_code=(row.get("branch_code") or "").strip(),
                account_type=account_type,
                account_number=(row.get("account_number") or "").strip(),
                amount=int(float(row.get("transfer_amount") or 0)),
                customer_code=(row.get("worker_id") or "").strip().zfill(20),
                transfer_date=transfer_date,
            )
            records.append(record)

    if not records:
        print("❌ 振込レコードがありません")
        return 1

    if not batch_id:
        batch_id = f"BATCH_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    batch = BankTransferBatch(
        batch_id=batch_id,
        transfer_date=records[0].transfer_date,
        records=records,
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"bank_transfer_{batch_id}.txt")
    batch.save_to_file(out_path)

    print("✅ 振込ファイル生成成功")
    print(f"  - 出力先: {out_path}")
    print(f"  - レコード数: {len(records)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
