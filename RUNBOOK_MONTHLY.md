# RUNBOOK_MONTHLY

## 目的
月次で CSV取り込み→請求発行→支払確定→締め までを再現性高く回す

## 前提条件
- DB接続情報が `.env` に設定済み
- 対象月が確定している（例: `202601`）
- 対象案件リストが確定している (status='operating')
- 実行者のロール: **Ops** または **Accounting** または **Admin**

---

## 1️⃣ CSV提出状況の確認（Ops）

### 目的
未提出案件を特定し、催促する

### 自動実行（スケジューラー）
- **週次催促メール**: 毎週月曜9:00に自動実行
- **実行内容**: CSV未提出者にリマインドメール送信
- **設定**: `EMAIL_DRY_RUN=false` で本番送信、`=true` でログ出力のみ
- **環境変数**: `SCHEDULER_WEEKLY_DAY=0`, `SCHEDULER_WEEKLY_HOUR=9`

### 手動確認手順
```python
from src.services.dashboard import get_unprocessed_items

# 未提出案件を抽出
result = get_unprocessed_items(session, period_key="202601", item_type="csv_missing")

for item in result.items:
    print(f"案件: {item.project_name}, 担当: {item.site_manager_email}")
```

### チェックリスト
- [ ] 対象月の全案件リストを取得
- [ ] 提出期限（月初5営業日目）を確認
- [ ] スケジューラーログで自動送信を確認（週次催促メール）
- [ ] 期限超過案件をAdminへエスカレーション

### 出力例
```
Project: 警備A現場, Site Manager: manager@example.com, 提出期限: 2026-02-05
```

---

## 2️⃣ CSV取り込み（Ops）

### 目的
提出されたCSVを取り込み、エラーを差戻す

### 手順
```python
from src.services.csv_import import CSVImportService, ImportMode, ImportScopeType

service = CSVImportService(session)

# 洗い替えモードで取り込み
result = service.import_csv(
    file_content=csv_content,
    file_name="project_A_202601.csv",
    project_id="PROJECT_A_ID",
    period_key="202601",
    mode=ImportMode.REPLACE_SCOPE,
    scope_type=ImportScopeType.PROJECT_MONTH,
    default_price_sales=Decimal("1500"),
    default_price_outsource=Decimal("1200"),
)

# エラー確認
if result.errors:
    for err in result.errors:
        print(f"行{err.row_number}: {err.field} - {err.message}")
```

### チェックリスト
- [ ] CSVファイルのエンコーディングが UTF-8 であることを確認
- [ ] 取込モードは `REPLACE_SCOPE` を使用（洗い替え）
- [ ] エラー行がある場合、差戻しテンプレでSite Managerへ連絡
- [ ] 修正CSV の再提出期限を設定（通常2営業日）
- [ ] 再取り込み時も `REPLACE_SCOPE` で二重化防止

### エラー対応
| エラー種別 | 原因 | 対処 |
|---|---|---|
| `No matching assignment` | アサインが登録されていない | ShiftSlotとAssignmentを登録 |
| `Assignment is canceled` | キャンセル済アサインへの投入 | アサイン状態を確認 |
| `Duplicate file hash` | 同じファイルの再投入 | 修正済みCSVか確認 |

---

## 3️⃣ 予定との差分チェック（Ops/Accounting）

### 目的
予定実績の乖離を検知し、異常値を修正する

### 手順
```python
from src.services.aggregation import get_variance_alerts

alerts = get_variance_alerts(
    session,
    period_key="202601",
    threshold_percent=10.0,  # 10%以上の差異
)

for alert in alerts:
    print(f"案件: {alert.project_name}, 差異: {alert.variance_percent}%")
    print(f"  予定: {alert.planned_amount}円, 実績: {alert.actual_amount}円")
```

### チェックリスト
- [ ] 閾値超過アラートを全件確認
- [ ] 影響金額が大きい順にソート
- [ ] 正当な理由（休憩変更、シフト変更）か確認
- [ ] 問題なしなら確認済フラグを立てる
- [ ] 問題ありならAssignment, PriceRule, またはCSVを修正し再取込

### 許容範囲
- 10%未満の差異 → 確認のみ
- 10-20% → 理由を記録
- 20%以上 → 必ず調査と修正

---

## 4️⃣ 請求書生成（Ops）

### 目的
対象月の実績から請求書を生成し、レビュー待ち状態にする

### 手順
```python
from src.services.invoice_service import generate_invoice

invoice = generate_invoice(
    session=session,
    client_id="CLIENT_A_ID",
    project_id="PROJECT_A_ID",  # 案件別請求の場合
    period_key="202601",
    billing_date=date(2026, 2, 1),
    user_id="ops_user",
)

print(f"請求書ID: {invoice.id}, 金額: {invoice.total_amount}円")
```

### チェックリスト
- [ ] 全案件の請求書生成を実行
- [ ] 生成失敗した案件を記録（エラーログ確認）
- [ ] 請求書ステータスが `preparing` であることを確認
- [ ] Accountingへレビュー依頼メール送信

---

## 4️⃣-補足: バンドル価格（Wヘッダー）手入力調整（Ops/Accounting）

### 目的
Wヘッダー等で「案件別の合算」ではなく「バンドル価格」を採用する場合に、請求書発行前に `actual.applied_price_sales` を手動で調整する（DEC-009 / docs/ops/DRV_PAYOUT_RULES.md）。

### ガード（重要）
- 発行済み請求（`issued`/`closed`）や承認済み支払（`approved`/`paid`/`closed`）に含まれる実績は変更しない
- Hard Close 済みの実績は変更しない

### 手順（推奨: スクリプトで監査ログを残す）
```bash
# dry-run
python scripts/adjust_actual_applied_prices.py --actual-id ACTUAL_ID --sales 35000 --reason "Wヘッダーのバンドル調整"

# 実反映
python scripts/adjust_actual_applied_prices.py --actual-id ACTUAL_ID --sales 35000 --reason "Wヘッダーのバンドル調整" --actor ops_user --commit
```

### チェックリスト
- [ ] 対象実績が「発行前」「未Hard Close」である
- [ ] 変更理由（バンドル額/根拠）を記録した
- [ ] `audit_logs` に `actual_applied_price_adjusted` が記録された

---

## 5️⃣ 請求レビューと発行（Accounting）

### 目的
請求書の金額を確認し、問題なければ発行する

### 手順
```python
from src.services.invoice_service import issue_invoice

# レビュー
invoice = session.get(Invoice, invoice_id)
assert invoice.status == InvoiceStatus.PREPARING.value

# 発行
issue_invoice(
    session=session,
    invoice_id=invoice.id,
    user_id="accounting_user",
)

# PDF確認（自動生成済み）
# ./invoices/invoice_{invoice.id}_v{invoice.version}.pdf を確認
```

### レビューチェックリスト
- [ ] 合計金額が実績から正しく計算されている
- [ ] 単価スナップショット（applied_price_sales）が正しい
- [ ] InvoiceLineの行数が実績件数と一致
- [ ] 消費税計算が正しい（subtotal * 0.1）
- [ ] 前月との金額変動が妥当か確認

### NGパターン
| 問題 | 対処 |
|---|---|
| 単価が間違っている | PriceSalesを修正して再生成 |
| 実績が漏れている | CSV再取込後に再生成 |
| 実績が重複している | Actual.statusを確認して再生成 |

---

## 6️⃣ 支払明細生成（Ops）

### 目的
稼働者への支払明細を生成する

### 手順
```python
from src.services.payout_service import generate_payout

payout = generate_payout(
    session=session,
    worker_id="WORKER_A_ID",
    project_id="PROJECT_A_ID",  # 案件別の場合
    period_key="202601",
    payment_date=date(2026, 2, 10),
    user_id="ops_user",
)

print(f"支払明細ID: {payout.id}, 金額: {payout.total_amount}円")
```

### チェックリスト
- [ ] 全稼働者の支払明細を生成
- [ ] 例外（差替え、取消、訂正）が混ざっていないか確認
- [ ] 支払明細ステータスが `preparing` であることを確認

---

## 7️⃣ 支払承認と確定（Admin/Accounting）

### 目的
支払明細を承認し、確定状態にする

### 手順
```python
from src.services.payout_service import confirm_payout

confirm_payout(
    session=session,
    payout_id=payout.id,
    user_id="admin_user",
)
```

### チェックリスト
- [ ] 全支払明細の金額を確認
- [ ] 異常値（前月比2倍など）がないか確認
- [ ] 承認後に訂正が必要な場合は `correct_payout()` を使用

---

## 8️⃣ 締め（Admin）

### 目的
対象月を確定し、以降の変更を防ぐ

### 手順
```python
from src.services.closing import soft_close, hard_close

# Soft Close（解除可能）
soft_close(
    session=session,
    project_id="PROJECT_A_ID",
    month_key="202601",
    user_id="admin_user",
)

# Hard Close（解除には二者承認が必要）
hard_close(
    session=session,
    project_id="PROJECT_A_ID",
    month_key="202601",
    user_id="admin_user",
    reason="月次確定",
)
```

### 事前チェックリスト
- [ ] 未取込実績 = 0
- [ ] 未発行請求書 = 0
- [ ] 未確定支払明細 = 0
- [ ] 差分アラート全件確認済

### Hard Close後の注意
- 再計算は不可
- 締め解除には二者承認が必要
- 解除回数上限（デフォルト3回）あり

---

## トラブルシューティング

### Q: CSV取込でエラーが大量発生
A: 
1. ファイルエンコーディングを確認
2. 必須カラムの欠損を確認
3. worker_id, role_id がマスタに存在するか確認

### Q: 請求書金額が前月と大きく異なる
A:
1. 差分アラートを確認
2. 単価マスタの変更履歴を確認
3. 実績件数を前月と比較

### Q: 締め後に誤りを発見
A:
1. 締め解除申請（二者承認）
2. 解除理由と再締め期限を記録
3. 修正後、速やかに再締め

---

## 監査ログの確認

```python
from src.services.audit import get_audit_logs

# 締め操作の履歴
logs = get_audit_logs(
    session,
    action="closing_hard_closed",
    month_key="202601",
)

for log in logs:
    print(f"{log.created_at}: {log.user_id} - {log.action}")
```
- 差分アラートが確認済であることを確認
- 締めを実行

## 9 例外：締め解除（Admin）
- 本当に解除が必要か確認（訂正で済むなら解除しない）
- 解除回数上限を確認
- 二者承認が必要ならAccounting承認を取得
- 理由と再締め期限を入力
- 解除実行
- 修正完了後に再締め
