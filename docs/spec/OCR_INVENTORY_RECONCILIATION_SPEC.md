# OCR在庫照合 仕様書（精算レシート・在庫照合機能）

## 位置づけ

本書は `PAYGATE精算レシート OCR・在庫照合 計画書（改訂版 v4）`（以下「計画書v4」）の実装内容を仕様として確定するドキュメントである。計画書自体は編集しない。実装状況・確定事項の正本は本書と `docs/decisions/DECISION_LOG.md` とする。

対象スコープ: 精算レシート（`source_type = paygate_settlement`）のOCR読取強化 ＋ 在庫照合機能。Paygateスクリーンショット（`paygate_screenshot`）は対象外・変更なし。

## 1. Phase 0-Step3: 実在庫入力の正式ルール（確定）

計画書v4 Phase 0 Step 3「パイロット結果を踏まえ、実在庫入力の正式ルール（入力者・タイミング・修正権限）を確定」に対応する。

### 1.1 入力者

- 実在庫（`inventory_snapshots`）の入力は**事務局（`admin` / `ops` / `accounting` ロール）が担当**する。現場稼働者本人による直接入力は行わない（計画書v4の前提「利用者：事務局」に整合）。
- 現場からの実在庫数の申告は、既存の画像受け渡しと同じ経路（オフライン受領）で事務局に伝達され、事務局が代行入力する。

### 1.2 入力タイミング

- 対象の精算レシートが OCR 解析・確定された後、**事務局の月次/週次バッチ処理のタイミングで**、当該 `work_date` の実在庫（`opening_count` / `closing_count`）を入力する。
- リアルタイム入力は求めない（計画書v4のスコープ「バッチ処理前提」に整合）。入力の目安は稼働日から概ね1〜2週間以内（月次CSV出力までに完了していることが望ましい）。
- `entered_at` は入力時点のタイムスタンプを自動記録する。

### 1.3 修正権限

- `inventory_snapshots` は事務局ロール（`admin` / `ops` / `accounting`）であれば誰でも修正可能とする（第三者承認は不要、計画書v4 §2 確定事項）。
- `confirmed_by` は `entered_by` と同一人物でよい（自己申告制、承認フローはシステムでは実装しない）。
- 修正・削除操作は既存の監査ログ（`audit_log`）に記録する。

### 1.4 branch_id の必須化判断

- 計画書v4レビュー③の指摘を受け、**`branch_id` は Phase 0 の結果を待たず最初から照合キーに含める**（計画書v4 §6.2で確定済み）。
- MVPの照合キー: `(branch_id, terminal_short_id, work_date)`。`branch_id` が未入力の場合のみ `(terminal_short_id, work_date)` にフォールバックする。
- 実装上、`inventory_snapshots.branch_id` は入力必須ではないが、**運用上は原則入力すること**とし、未入力ケースが継続する場合は改めて必須化（NOT NULL制約）を検討する。

## 2. `adjustment_count` の符号規約（確定・実装済み）

計画書v4 §4.2 のとおり実装済み。

```text
adjustment_count は、販売以外の理由による在庫増減を表す。

- 紛失・破損・担当者間移動など、販売以外で在庫が「減った」場合 → 正の値
- 返品・追加補充・入力修正など、販売以外で在庫が「増えた」場合 → 負の値

在庫照合上の販売相当減数（inventory_decrease）は次式で算出する:

  在庫減数 = opening_count - closing_count - adjustment_count
  diff = transaction_count - 在庫減数
```

`adjustment_count != 0` の場合、`adjustment_reason` の入力を必須とする（`src/services/inventory_reconciliation.py` でバリデーション済み）。

## 3. 在庫照合キー・一意性制約（確定・実装済み）

- 照合キー: `(branch_id, terminal_short_id, work_date)`
- **在庫照合対象として採用できる精算レシート行（`reconciliation_eligible=true` かつ `status=confirmed` かつ `voided_at IS NULL`）は、同一キーで常に1件のみ**とする部分ユニークインデックス `uq_ocr_settlement_reconciliation_target` を `ocr_extracted_rows` に実装済み（`alembic/versions/20260702a001_add_inventory_reconciliation.py`）。
- 同一端末・同日に複数の精算レシートが存在すること自体は許容する。事務局がどちらを在庫照合対象とするか明示的に選択し、非採用側には `excluded_reason` を設定する。

## 4. OCR確定と在庫照合対象採用の分離（確定・実装済み）

| 概念 | フィールド | 意味 |
|------|-----------|------|
| OCR確定 | `status = confirmed` | 精算レシートから読み取った情報が人手確認により正しいと判断された状態 |
| 在庫照合対象採用 | `reconciliation_eligible`（既定 `true`, opt-out方式） | 当該OCR確定行を、その端末・稼働日の在庫照合に使ってよい最終的な精算データとして採用するかどうか |
| OCR行の無効化 | `voided_at` / `voided_by` / `void_reason` | OCR行そのものを無効化した状態（誤アップロード・誤確定の取消）。`excluded`（照合対象外）とは別概念 |

## 5. 検証結果の重大度分離（確定・実装済み）

`blocking_errors`（確定をブロックする重大エラー）と `warnings`（確定は可能だが要注意）に分離。`unit_breakdown_status = manual` は `warnings` 扱いとし、OCR確定をブロックしない。詳細は `src/services/ocr/validation.py`、`src/services/ocr/settlement_processing.py` を参照。

## 6. 意味的重複検知（確定・実装済み）

画像SHA256の完全一致排除とは別に、`(terminal_short_id, record_date, record_time, amount, transaction_count)` が既存行と一致する場合に `duplicate_receipt_candidate = true` を立てて事務局に警告する。自動除外は行わない。実装: `src/services/ocr/duplicate_detection.py`。

## 7. 単価構成ソルバーの適用範囲（確定・実装済み）

クレジット売上または その他支払いが非ゼロの行は自動解決を試みず `unit_breakdown_status = manual` とする。対象は現金／PAYGATE POSの2値のみ。実装: `src/services/ocr/unit_breakdown.py`。

## 8. 残る運用判断事項

- **JTとの契約上、決済・在庫関連データをVANZAI（社外DB）に保存してよいか**: 未検討。契約内容の確認は本システム設計とは別タスクとして管理する（`docs/decisions/DECISION_LOG.md` DEC-026 参照）。
- パイロット運用（`docs/ops/OCR_INVENTORY_PILOT_TEMPLATE.md`）の結果、実運用で「通常取引数＝販売台数」の前提が成立しないケースが多数見つかった場合は、本書 §1・§3 のルールを見直し、`docs/decisions/DECISION_LOG.md` に理由付きで記録する。

## 関連ドキュメント

- 計画書: `PAYGATE精算レシート OCR・在庫照合 計画書（改訂版 v4）`
- 運用手順: `docs/ops/OCR_INVENTORY_RUNBOOK.md`
- パイロット記録テンプレート: `docs/ops/OCR_INVENTORY_PILOT_TEMPLATE.md`
- 意思決定ログ: `docs/decisions/DECISION_LOG.md`
