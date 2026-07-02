# OCR・レシート解析／在庫照合 運用 Runbook

（旧: `OCR_RECEIPT_RUNBOOK.md`。精算レシート在庫照合機能の追加に伴い改称。参照: `PAYGATE精算レシート OCR・在庫照合 計画書（改訂版 v4）`）

## 概要

admin-web の **OCR・レシート解析**（`/operations/ocr-receipt`）で、Paygate 取引履歴スクショ（`paygate_screenshot`）と精算レシート写真（`paygate_settlement`）を解析し、年月別に保存・CSV 出力します。精算レシートについては、実在庫入力・在庫照合機能もあわせて提供します。

## 前提

- API に PaddleOCR 依存をインストール済みであること
  ```bash
  pip install -e ".[ocr]"
  ```
- VPS メモリ 4 GB 以上推奨（本番 VPS は 6 GB — 問題なし）
- **API は `--workers 1` で起動すること**（PaddleOCR はプロセスあたり 1 GB 超を消費。`--workers 2` だと解析開始時にワーカーが落ちる）
- 環境変数（任意）
  - `OCR_STORAGE_ROOT=storage/ocr`
  - `OCR_ENGINE_DISABLED=1` … OCR エンジン無効（テスト用）

## 月次手順

1. admin-web にログイン（`admin` / `ops` / `accounting`）
2. 左メニュー **OCR・レシート解析** を開く
3. **Paygateスクリーンショット** または **精算レシート** の枠に画像を D&D
4. **画像をアップロード** → **解析**
5. 結果テーブルで **要確認** バッジ・検証エラーの行を確認し、**編集** で修正
6. **確定可能な行のみ** 選択して **選択行を確定**（推定・fuzzy/missing 行は確定不可）
7. **月次CSV** または **全件CSV** をダウンロード

## OCR メタデータ値（CSV / API）

| フィールド | 値 |
|-----------|-----|
| `amount_source` | `ocr` / `corrected_ocr` / `fallback_default` / `manual` |
| `datetime_source` | `ocr_strict` / `fuzzy` / `missing` / `manual` |
| `amount_inferred` | `true` = 980円フォールバック等 |
| `confirm_required` | `true` = 人手確認前は confirmed 不可 |

**精算レシート（`paygate_settlement`）専用フィールド**（計画書 v4 §4.1）:

| フィールド | 値 |
|-----------|-----|
| `blocking_errors` | 確定をブロックする重大エラー（例: 金額不整合、1の位異常）。空でなければ確定不可 |
| `warnings` | 確定は可能だが要注意（例: `unit_breakdown_status=manual`） |
| `unit_breakdown_status` | `resolved` / `ambiguous` / `invalid` / `manual`。`manual`/`ambiguous` でも確定可 |
| `duplicate_receipt_candidate` | `true` = 意味的重複候補（`terminal_short_id`+`record_date`+`record_time`+`amount`+`transaction_count`が既存行と一致）。自動除外はしない、事務局が目視確認 |
| `reconciliation_eligible` | 既定 `true`（opt-out方式）。途中精算・重複・誤アップロード等は事務局が `false` にし `excluded_reason` を設定 |
| `voided_at` / `voided_by` / `void_reason` | OCR行そのものを無効化した場合に設定（`reconciliation_eligible=false` とは別概念。§「状態の責任範囲」参照） |

## 精算レシート（paygate_settlement）の確定条件

- OCR確定に必須: `record_date`, `record_time`, `amount`, `transaction_count`, `terminal_short_id`
- **`blocking_errors` が存在する行は確定不可**（金額不整合、合計・現金売上・PAYGATE POS金額いずれかの1の位が0以外、等）
- `warnings`（`unit_breakdown_status=manual` 等）は確定をブロックしない。単価内訳は編集モーダルの手入力欄で後から補完できる
- Paygateスクリーンショット（`paygate_screenshot`）は従来どおり `transaction_no` / `receipt_no` が必須（精算レシートとは確定条件が異なる点に注意）

### 状態の責任範囲（混同注意）

| フィールド | 意味 |
|-----------|------|
| `status`（`pending_review`/`confirmed`） | OCR行そのものの確定状態 |
| `voided_at`/`voided_by`/`void_reason` | OCR行として**無効化**（誤アップロード・誤確定の取消） |
| `reconciliation_eligible`/`excluded_reason` | OCR行としては有効だが**在庫照合には使わない** |
| `match_status`（照合結果側） | 在庫照合を実行した結果のステータス |

## 撮影ガイド（精算レシート）

- レシート全体が画面に入るよう真上から撮影
- 明るい場所で、指で文字を隠さない
- ブレ・ピンボケ時は撮り直し

## 本部 CSV 突合（Paygateスクリーンショット向け）

1. 突合セクションに本部 CSV をアップロード
2. 列名（取引番号・レシート番号・日付・金額）をサンプルに合わせて調整
3. **突合実行** で一致 / OCRのみ / 本部のみ / 金額差異を確認

## 実在庫入力・在庫照合（精算レシート専用）

参照: `PAYGATE精算レシート OCR・在庫照合 計画書（改訂版 v4）` §6〜7、`docs/spec/OCR_INVENTORY_RECONCILIATION_SPEC.md`

### 月次手順

1. 精算レシートの解析・確定を先に完了させる（上記「精算レシートの確定条件」参照）
2. **実在庫入力** セクションで、`branch_id` × `terminal_short_id` × `work_date` ごとに開始在庫（`opening_count`）・終了在庫（`closing_count`）・調整数（`adjustment_count`）・調整理由（`adjustment_reason`）を入力
   - `adjustment_count` の符号規約: 販売以外で在庫が**減った**場合は正の値、**増えた**場合は負の値
   - `adjustment_count ≠ 0` の場合、`adjustment_reason` は必須
   - 入力者（`entered_by`）と確認者（`confirmed_by`）は同一人物でよい（自己申告制、確定事項）
3. **在庫照合実行** で対象期間（`work_date` の範囲、または年月）を指定して実行
4. 結果一覧で `match_status` を確認し、`count_mismatch` 等の差異行には `diff_reason_category`（差異理由の分類）を設定
   - 差異が実質的に問題ないと判断できる場合（例: 調整理由の記入で説明がつく）は `adjusted_matched` として扱う
   - 途中精算・重複等で当該精算行を照合対象から外す場合は、精算レシート一覧側で `reconciliation_eligible=false` + `excluded_reason` を設定してから再実行する
5. 在庫照合CSV・精算レシート専用CSV（拡張）をダウンロードして保管

### 月次 `adjustment_reason` レビュー（必須運用・システム改修なし）

在庫調整（`adjustment_count`/`adjustment_reason`）は**入力者本人の自己申告制**であり、承認フローはシステムでは実装していない（計画書 v4 §2 確定事項）。不正・紛失の隠蔽経路になりうるリスクを事後監査で軽減するため、以下を**必須運用**とする。

1. 毎月、事務局責任者が当月分の `inventory_snapshots` のうち `adjustment_count ≠ 0` の行を一覧で目視レビューする（在庫照合結果一覧またはCSV出力で確認）
2. 不自然な調整（同一端末での頻発、理由記述が曖昧、金額換算で大きい等）がないか確認する
3. 疑義がある場合は入力者（`entered_by`）へ確認し、必要に応じて `docs/decisions/DECISION_LOG.md` に対応記録を残す
4. レビュー結果（実施日・レビュー担当者・指摘有無）は事務局内の月次記録に残す

### 同一端末・同日複数精算の扱い

同一端末・同一稼働日に複数回精算が発生すること自体は許容する（誤って途中精算、レシート再発行、担当者交代等）。ただし、**在庫照合の対象（`reconciliation_eligible=true`）は同一キー（`branch_id`+`terminal_short_id`+`work_date`）で常に1件のみ**にDB制約で制限されている。複数の精算レシートが存在する場合は、事務局がどちらを在庫照合に採用するか明示的に選択し、非採用側に `excluded_reason` を設定すること。

## nginx

API の `proxy_read_timeout` は OCR 用に **300s** を推奨（`tools/nginx_vanzai_new.conf` 参照）。

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| 503 PaddleOCR not installed | `pip install -e ".[ocr]"` を実行し API 再起動 |
| libGL.so.1 エラー | `pip uninstall opencv-contrib-python opencv-python opencv-contrib-python-headless opencv-python-headless` 後 `pip install "opencv-python-headless>=4.8.0,<5.0.0"`（**5.x は PaddleOCR と非互換**） |
| `cv2` has no attribute `INTER_LINEAR` | 上記と同様。複数の opencv パッケージが混在しているか、OpenCV 5.x が入っている |
| 解析に失敗しました（画面のみ） | API ログで `Child process died` を確認 → `--workers 1` で再起動 |
| 解析が途中で切れる | nginx `proxy_read_timeout` を 300s に延長 |
| 取引が重複 | 同一取引番号・レシート番号は解析時に自動統合。既に登録済みの行はスキップ（未確定行はより完全なキャプチャで上書き更新） |
| 行が空 | 撮影品質を見直し、手入力で PATCH 修正 |
| 精算レシートが「重複候補」バッジ表示 | 画像SHAが異なっていても内容（端末・日時・金額・取引数）が既存行と一致すると警告表示される。自動除外はされないため、事務局が実際に別レシートか確認し、重複なら片方を無効化（`voided`）または `reconciliation_eligible=false` に設定 |
| 精算レシートが「選択行を確定」で拒否される | `blocking_errors` を確認（金額不整合・1の位異常等）。編集モーダルで修正するか、再解析してから再確定する |
| 在庫照合で同一キーに複数の対象行を設定しようとしてエラー | 部分ユニーク制約により、同一 `branch_id`+`terminal_short_id`+`work_date` で `reconciliation_eligible=true` の行は1件のみ。既存の対象行を `false` に変更してから対象を切り替える |
| 在庫照合結果が `sales_only` / `inventory_only` のまま | 精算レシートの確定漏れ、または実在庫入力漏れ。両方が揃っているか確認 |
