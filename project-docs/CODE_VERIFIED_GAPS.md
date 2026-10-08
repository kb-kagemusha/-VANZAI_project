# CODE_VERIFIED_GAPS.md

コード解析（2026-06-10）で確認した、仕様意図と実装のギャップ一覧。  
優先度は会計・再現性リスクを基準に P0（最優先）〜 P3 で分類。

---

## P0: 会計整合性に直結（早急対応推奨）

| ID | ギャップ | 仕様/意図 | 実装実態 | 該当コード |
|----|---------|----------|---------|-----------|
| G-001 | 締め後 CSV 取込 | Soft Close 後は取込凍結 | **締めチェックなし** | `csv_import.py` |
| G-002 | 締め後帳票生成 | 締め状態を尊重 | invoice/payout に closing 参照なし | `invoice_service.py`, `payout_service.py` |
| G-003 | 請求数量の時間軸 | billable 時間で請求 | `calc_minutes_total / 60` を使用 | `invoice_service.py` L116 |
| G-004 | 再発行の明細欠落 | 明細行が正本 | `reissue_invoice` は合計のみコピー | `invoice_service.py` L426+ |
| G-005 | 集計 API 無認証 | 認証必須 | `/api/aggregation/*` に権限チェックなし | `main.py` |

---

## P1: 監査・再現性（次に対応）

| ID | ギャップ | 内容 | 該当 |
|----|---------|------|------|
| G-101 | supersede 監査 | `ACTUAL_SUPERSEDED` 未記録 | `csv_import._supersede_existing` |
| G-102 | 単価変更監査 | `PRICE_RULE_CHANGED` 未実装 | マスタ API |
| G-103 | 再計算監査 | 専用 Action なし、`PRICE_RESOLVED` に埋め込み | `recalculation.py` |
| G-104 | incentive 監査誤用 | 作成/承認に `IMPORT_BATCH_*` 流用 | `incentive_service.py` |
| G-105 | 総時間警告未実装 | `has_total_time_warning` 未設定 | `csv_import.py` |

---

## P2: 仕様未完了・部分実装

| ID | ギャップ | 内容 |
|----|---------|------|
| G-201 | ImportMode | append / upsert_by_external_key 未実装 |
| G-202 | 営業日カレンダー | 締め再締め期限が暦日（7日/3日） |
| G-203 | provisional 救済 | 仕様15章、コード未検出 |
| G-204 | Hard Close 解除 | 仕様は原則不可、API は例外実装あり |
| G-205 | OPEN→Hard エラー文言 | `hard_close` の OPEN 時メッセージが不正確 |

---

## P3: ドキュメント・構造・拡張

| ID | ギャップ | 内容 |
|----|---------|------|
| G-301 | DESIGN_SPEC 欠落 | 復元たたき台 `docs/spec/DESIGN_SPEC_v0.3.md` で暫定対応 |
| G-302 | ORM 未定义テーブル | Phase1E 4テーブル（tasks, sales_reports 等） |
| G-303 | main_simple 二重管理 | 本番は `main.py` のみ使用を明文化 |
| G-304 | API パス旧表記 | project-docs 旧 `/api/closings/*` 等 → 更新済み |
| G-305 | 未実装拡張機能 | equipment, bank_transfer_batch, admin-notices |

---

## 締めガードの現状マトリクス

| 操作 | OPEN | SOFT_CLOSED | HARD_CLOSED |
|------|:----:|:-----------:|:-----------:|
| CSV 取込 | ✅ 可 | ✅ 可（**要制限**） | ✅ 可（**要制限**） |
| 請求生成 | ✅ 可 | ✅ 可（**要制限**） | ✅ 可（**要制限**） |
| 支払生成 | ✅ 可 | ✅ 可（**要制限**） | ✅ 可（**要制限**） |
| 再計算 | ✅ 可 | ✅ 可 | ❌ 拒否 |

**結論**: 再計算のみ Hard Close ガードが効いている。AGENTS.md「締め後に計算結果が変わらない」は再計算に限定され、取込・帳票生成はガード外。

---

## 推奨対応順序

1. G-001, G-002（締めガード統合）— サービス層に `assert_closing_allows_mutation()` 等を共通化
2. G-003（請求数量の統一）— `calc_minutes_billable` へ揃えるか仕様を明文化
3. G-004（reissue 明細コピー）— `correct_invoice` と同パターンで修正
4. G-005（aggregation 認証）— 即時対応可能
5. G-101〜105（監査網羅）
