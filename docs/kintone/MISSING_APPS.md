# Kintone 未作成アプリの対応

## 問題

以下のアプリがKintoneに存在しません：
- **請求書 (invoices)** - 請求書発行・管理
- **支払明細 (payouts)** - 支払明細発行・管理

これらはシステムの中核機能（請求書PDF生成、支払明細PDF生成）に必要です。

## 現状

### ✅ 既にKintoneに存在するアプリ（20個）

| アプリID | アプリ名 | APIトークン | 用途 |
|---|---|---|---|
| 165 | workers | ✅ | 稼働者マスタ |
| 167 | clients | ✅ | クライアントマスタ |
| 166 | sites | ✅ | 現場マスタ |
| 163 | roles | ✅ | 役割マスタ |
| 164 | project_types | ✅ | 案件種別マスタ |
| 162 | price_sales | ✅ | 売上単価マスタ |
| 161 | price_outsource | ✅ | 外注単価マスタ |
| 154/157 | price_rules | ✅ | 単価ルールマスタ |
| 160 | projects | ✅ | 案件マスタ |
| 159 | shift_slots | ✅ | シフト枠マスタ |
| 158 | assignments | ✅ | アサイン管理 |
| 168 | actuals | ✅ | 実績データ |
| 151 | expenses | ✅ | 経費精算 |
| 150 | incentives | ✅ | インセンティブ |
| 152/155 | incentive_rules | ✅ | インセンティブルール |
| 149 | payout_deliveries | ✅ | 支払明細送信履歴 |
| 148 | bank_transfer_batches | ✅ | 銀行振込バッチ |
| 147 | equipment | ✅ | 貸出備品マスタ |
| 146 | equipment_loans | ✅ | 貸出備品管理 |
| 145 | tasks | ✅ | タスク管理 |
| 144 | project_documents | ✅ | 案件ドキュメント |

### ❌ Kintoneに存在しないアプリ（2個）

| アプリ名 | 必要性 | 影響 |
|---|---|---|
| **invoices** | **高** | 請求書発行・PDF生成・訂正管理ができない |
| **payouts** | **高** | 支払明細発行・PDF生成・訂正管理ができない |

## 対応方法

### オプション1: Kintoneに新規作成（推奨）

請求書と支払明細のアプリをKintoneに新規作成します。

#### 手順

1. **請求書アプリ (invoices) 作成**

Kintone管理画面で新規アプリ作成:

**フィールド設定:**
```
invoice_id          : 文字列（1行）※必須、重複禁止
invoice_number      : 文字列（1行）※必須
client_id           : 文字列（1行）※必須
project_id          : 文字列（1行）
period_key          : 文字列（1行）※必須 (YYYYMM形式)
issue_date          : 日付※必須
payment_due_date    : 日付
version             : 数値※必須
status              : ドロップダウン（preparing/confirmed/sent/paid/superseded）
subtotal            : 数値
tax_amount          : 数値
total_amount        : 数値
parent_invoice_id   : 文字列（1行）
superseded_by_id    : 文字列（1行）
pdf_storage_key     : 文字列（1行）
notes               : 文字列（複数行）
```

**APIトークン設定:**
- アプリ作成後、「設定」→「APIトークン」
- 権限: レコード閲覧、レコード追加、レコード編集、**アプリの設定**
- トークンを生成してコピー
- `.env` に `KINTONE_TOKEN_INVOICES=<トークン>` を追加

2. **支払明細アプリ (payouts) 作成**

**フィールド設定:**
```
payout_id           : 文字列（1行）※必須、重複禁止
payout_number       : 文字列（1行）※必須
worker_id           : 文字列（1行）※必須
period_key          : 文字列（1行）※必須 (YYYYMM形式)
issue_date          : 日付※必須
payment_date        : 日付
version             : 数値※必須
status              : ドロップダウン（preparing/confirmed/paid/superseded）
total_amount        : 数値
parent_payout_id    : 文字列（1行）
superseded_by_id    : 文字列（1行）
pdf_storage_key     : 文字列（1行）
notes               : 文字列（複数行）
```

**APIトークン設定:**
- 同様に設定
- `.env` に `KINTONE_TOKEN_PAYOUTS=<トークン>` を追加

3. **スクリプトに設定追加**

アプリIDを確認（例: invoices=169, payouts=170）して、各スクリプトに追加:

- `extract_kintone_fields.py`
- `update_kintone_field_types.py`
- `sync_db_to_kintone.py`

4. **フィールド定義抽出**

```bash
python scripts/extract_kintone_fields.py 169  # invoices
python scripts/extract_kintone_fields.py 170  # payouts
```

5. **フィールドタイプ変更**

```bash
python scripts/update_kintone_field_types.py 169  # invoices
python scripts/update_kintone_field_types.py 170  # payouts
```

---

### オプション2: Kintone連携を一時無効化（暫定）

Kintoneアプリ作成が間に合わない場合、ローカルDBのみで運用します。

**影響:**
- ✅ 請求書・支払明細のPDF生成は可能（DBベース）
- ✅ 月次締め・再計算は可能
- ❌ Kintoneでの閲覧・検索不可
- ❌ Kintone経由でのステータス更新不可

---

### オプション3: ローカルテーブルで代替（非推奨）

invoicesとpayoutsをKintoneと同期せず、ローカルDBのみで管理します。

**問題点:**
- Kintoneの一元管理メリットが失われる
- 二重管理のリスク
- 将来的な統合が困難

---

## 推奨アクション

### 🔥 優先度: 高

1. **Kintoneに invoices と payouts を作成**（約30分）
   - 上記フィールド定義でアプリ作成
   - APIトークン設定（アプリの設定権限も付与）
   
2. **トークンを .env に追加**
   ```
   KINTONE_TOKEN_INVOICES=<生成したトークン>
   KINTONE_TOKEN_PAYOUTS=<生成したトークン>
   ```

3. **アプリIDをスクリプトに追加**（約10分）

4. **フィールド自動設定を実行**（約5分）
   ```bash
   python scripts/update_kintone_field_types.py 169  # invoices
   python scripts/update_kintone_field_types.py 170  # payouts
   ```

---

## 作業手順（外部作業）

- Kintoneで invoices アプリ作成
- Kintoneで payouts アプリ作成
- 両アプリのAPIトークン生成（アプリの設定権限あり）
- .env にトークン追加
- extract_kintone_fields.py にアプリID追加
- update_kintone_field_types.py にフィールド定義追加
- sync_db_to_kintone.py に同期関数追加
- フィールド自動設定実行
- 動作確認

---

## 現在の状態

✅ マスタ5アプリ: フィールド定義抽出完了  
✅ bank_transfer_batches: フィールド定義抽出完了  
❌ invoices: Kintoneアプリ未作成  
❌ payouts: Kintoneアプリ未作成  

**次のステップ:**  
Kintoneで invoices と payouts アプリを作成し、APIトークンを発行してください。
