# フィールドマッピング・発見事項まとめ

## 実績時刻取り込みCSVのフィールド
（`kintone_app/sample/稼働単価サンプル.csv` と `シフト表サンプル.csv` 参照）

### シフト表サンプル.csv
- 現場ごとの日別シフト
- 役割別の出勤人数
- 時間帯（開始時刻・終了時刻）

### 稼働単価サンプル.csv  
- ワーカー別の単価設定
- 売上単価・支払単価
- 役割×現場×ワーカーの組み合わせ

## データベース・モデルのフィールド名の発見

### InvoiceLine / PayoutLine
| 想定フィールド名 | 実際のフィールド名 |
|------------------|-------------------|
| quantity | quantity_snapshot |
| unit_price | unit_price_snapshot |
| amount | line_amount |

### 必須フィールド（Not Null制約あり）
1. `line_number`: 明細行番号（1から連番）
2. `unit_type`: 単位種別（"hours" または "days"）
3. `line_type`: 明細種別（LineType.WORK / EXPENSE / INCENTIVE）

### Payout
| 想定フィールド名 | 実際のフィールド名 |
|------------------|-------------------|
| payout_month | period_key |
| - | payment_date (必須) |

### Closing
| 想定フィールド名 | 実際のフィールド名 |
|------------------|-------------------|
| project_id (int) | project_id (str/ULID) |

## Enum値の正式名称

### LineType
- ✅ `WORK` (実績作業)
- ✅ `EXPENSE` (経費)
- ✅ `INCENTIVE` (インセンティブ)
- ❌ ~~`LABOR`~~ (存在しない)

### InvoiceStatus
- `draft` - 下書き
- `issued` - 発行済み
- `paid` - 支払済み
- `closed` - 締め済み

### PayoutStatus
- ✅ `preparing` - 準備中
- ✅ `approved` - 承認済み
- ✅ `paid` - 支払済み
- ✅ `closed` - 締め済み
- ❌ ~~`DRAFT`~~ (存在しない)

### ClosingStatus
- `open` - 未締め
- `soft_closed` - ソフト締め
- `hard_closed` - ハード締め

## インポートパスの修正

### ULID生成関数
- ❌ `from src.utils.ulid import generate_ulid`
- ✅ `from src.models.base import generate_ulid`

理由: `src/utils/` ディレクトリは存在せず、`generate_ulid()` は `src/models/base.py` で定義されている

## API修正内容

### `src/api/main.py`
1. **Closingエンドポイント修正**
   - `ClosingService`クラスを使わず、`closing`モジュールの関数を直接呼び出し
   - `soft_close()` → `closing.soft_close(session, project_id, period_key, user_id, notes)`
   - `hard_close()` → `closing.hard_close(session, project_id, period_key, user_id, notes)`
   
2. **関数名の衝突回避**
   - エンドポイント関数名を `close_soft()`, `close_hard()` に変更
   - Pythonの関数名とimportしたモジュール内関数名の衝突を回避

### `src/api/schemas.py`
1. **Closing関連スキーマの型修正**
   - `SoftCloseRequest.project_id`: `int` → `str`
   - `HardCloseRequest.project_id`: `int` → `str`
   - `ClosingResponse.id`: `int` → `str`
   - `ClosingResponse.project_id`: `int` → `str`

## テストスクリプトで使用するID

### プロジェクトID (ULID)
- `01KG1E59K7177GH432H0GM6WQN` - テスト案件202601

### 期間キー
- `202601` - 2026年1月

### ワーカー
- 山田太郎: `01KFZS7DRB0X156CWR0G1JPBVR`
- 佐藤花子: `01KFZS7DRBQM7BJPHF6VD5Z8CC`
- 鈴木次郎: `01KFZS7DRBQM7BJPHF6VD5Z8CD`

## 残課題

### Task 10: 月次締め処理
- APIエンドポイント実装完了
- テスト未実施（APIサーバー再起動後に実行）

### Task 11: 銀行振込ファイル生成
- 実装保留（Kintone連携で対応可能）
- FB-Data形式の仕様確認が必要な場合は別途実施

## 検証済み機能

✅ 請求書生成（Invoice + InvoiceLine）
✅ 支払明細生成（Payout + PayoutLine）
✅ 集計API（売上・外注費）
✅ CSVインポート機能
✅ Kintone同期機能

## 次回実施事項

1. APIサーバーの安定起動確認
2. 月次締め処理のエンドツーエンドテスト
3. 全体のワークフロー検証
4. ドキュメントの最終更新
