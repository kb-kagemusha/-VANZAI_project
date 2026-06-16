# DESIGN_SPEC v0.3（復元たたき台）

> **文書ステータス**: 2026-06-10 時点の復元たたき台  
> 元ファイルがリポジトリから欠落していたため、以下を根拠に再構成した。  
> - `docs/ops/IMPLEMENTATION_STEPS_FROM_SPEC.md`  
> - `docs/spec/REVIEW_MERGE_v0.3.md`  
> - `docs/spec/CHANGELOG_v0.3_2026-01-27.md`  
> - `docs/decisions/DECISION_LOG.md`（DEC-001〜025）  
> - コード実装（`src/models`, `src/services`, `src/api/main.py`）との照合結果  
>
> **正本運用**: 本書と `DECISION_LOG.md` が矛盾する場合は DECISION_LOG を優先する。  
> 実装との差分は各章末の「実装メモ」または `project-docs/handover_notes.md` §12 を参照。

---

## 1. 目的

案件・シフト・実績・請求・支払を一元管理し、月次運用を「担当者依存」から「再現可能な標準業務」へ移す。

優先順位（MVP）:
1. 単価スナップショットと再計算の境界（締め前/締め後）
2. CSV取り込み（部分取り込み、洗い替え、二重化防止）
3. 予定/確定の定義を一貫させる集計
4. 請求書の生成（版管理、PDF保管、訂正/再発行）
5. 支払明細の生成（版管理、訂正）
6. ダッシュボード（未処理＝次の一手が分かる一覧）
7. 監査ログと権限

---

## 2. スコープ

### 2.1 対象
- 案件運用（project / shift_slot / assignment）
- 実績確定（CSV取込、打刻）
- 時間計算・単価適用
- 請求・支払・締め
- スタッフ向け（予定返信、稼働可否、経費、通知）

### 2.2 対象外（v0.3 時点）
- Kintone の即時完全置換（段階移行）
- 全銀フォーマットの最終仕様確定（DEC-004 Follow-ups）
- 貸出備品の Web DB 化（Kintone 運用が残存）

---

## 3. 設計原則

| 原則 | 内容 |
|------|------|
| 再現性 | 金額・時間の計算結果をスナップショット保存し、後から説明可能にする |
| 非破壊 | 物理削除より `superseded` / `invalid` / 版管理を優先 |
| 明細正本 | `invoice_line` / `payout_line` が正本、合計は集計値 |
| 月次キー | `period_key`（YYYYMM）で運用単位を固定 |
| 二段認可 | UI ガード + API 権限チェック（API が最終防衛線） |

---

## 4. 用語定義

| 用語 | 定義 |
|------|------|
| planned | assignment ベースの予定集計 |
| confirmed | actual.status=active ベースの確定集計 |
| snapshot | 計算・単価を確定時点で固定保存した値 |
| Soft Close | 実績確定後・帳票発行前の凍結 |
| Hard Close | 請求発行・支払承認/支払完了後の確定 |
| replace_scope | スコープ内の active actual を superseded にし新規投入する洗い替え |

---

## 5. ロールと権限

| ロール | 主な責務 |
|--------|---------|
| admin | 全体管理、マスタ、監査、締め解除 |
| ops | 案件運用、CSV取込、請求/支払生成、Soft Close |
| accounting | 請求発行、支払承認、Hard Close |
| site_manager | 担当案件の参照・CSV提出（`CSV_SUBMIT`） |
| worker | スタッフモバイル（予定返信、打刻、可否、経費） |

**DEC-011（Proposal）**: 現場管理者の正本は `project.primary_manager_id` / `secondary_manager_id`。  
`shift_slot.site_manager_id`（CHANGELOG §24）との整合は未確定。

---

## 6. データモデル

### 6.1 主要エンティティ

**マスタ**: worker, client, site, project_type, role, price_sales, price_outsource, price_rule, incentive_rule, supplier, vanzai_staff

**トランザクション**: project, shift_slot, assignment, actual, import_batch, expense, incentive, invoice, invoice_line, payout, payout_line, payout_delivery, closing

**監査・通知**: audit_log, staff_notice, staff_notice_read, push_subscription

**Phase1 拡張（2026-04）**: registration_requests 系, project_type_documents, task_templates, project_tasks, sales_reports

### 6.2 状態遷移（要約）

| エンティティ | 状態 |
|-------------|------|
| assignment | tentative / confirmed / canceled |
| actual | active / invalid / superseded |
| invoice | preparing / issued / closed |
| payout | preparing / approved / paid / closed |
| closing | open / soft_closed / hard_closed |
| import_batch | processing / completed / partial_error / failed |

### 6.3 不変条件

1. 集計対象の actual は `status=active` のみ
2. assignment が canceled のまま actual=active を残さない（取消時は invalid 化またはブロック）
3. 発行済み invoice / 承認済み payout に紐づく actual は再計算除外
4. 請求/支払で使用した単価・時間はスナップショット列に保持
5. Hard Close 後は unlock せず訂正/再発行で対応（例外は監査付き）

**実装メモ**: DB CHECK なしの制約（payout worker xor supplier 等）はアプリ層で担保。

---

## 7. 単価適用とスナップショット

### 7.1 適用タイミング
actual が `active` 確定時に `applied_price_sales` / `applied_price_outsource` を保存。以後の金額計算はスナップショットを正本とする。

### 7.2 優先順位
- **売上**: locked_price_sales → project 紐付き price_sales → price_rule（priority 昇順） → デフォルト
- **外注**: locked_price_outsource → worker×role → price_rule → price_outsource デフォルト

### 7.3 再計算（7.4）
- 対象期間・案件・actual 集合を明示
- 影響件数・金額差を事前表示
- invoice issued / payout approved|paid 紐付け actual は除外
- Hard Close 済み案件×月は再計算拒否

**DEC-005**: 税は合計計算（ヘッダ `tax_amount` 正本、税率 10% 暫定固定）。

**実装メモ**: `PRICE_RULE_CHANGED` 監査は未実装。`price_resolver` は解決のたび `PRICE_RESOLVED` を記録。

---

## 8. 時間計算

### 8.1 設定（project 正本）
`rounding_unit_minutes`, `rounding_method`, `break_deduction_rule`, `time_calc_mode`, `night_window`, `night_calc_mode`

### 8.2 system_first
minutes_total → break（auto/manual/none）→ billable → rounding → night_minutes → `actual.calc_*` 保存

### 8.3 csv_hours_first
CSV `hours` を正本として `minutes_billable` を採用

### 8.4 要確認フラグ
CSV hours と計算結果の差が閾値超（実装: 30分）→ `needs_review=true`

**DEC-006（Confirmed）**: `calc_minutes_night` を保存（再現性優先）。

**実装メモ**: 請求/支払の数量は `calc_minutes_total / 60` を使用。集計（`aggregation.py`）は `calc_minutes_billable` 優先。**不一致あり（要修正候補）**。

---

## 9. CSV取り込み

### 9.1 提出チャネル
原則: システム CSV 提出（site_manager）。例外: ops が `submit_channel` 指定。

### 9.2 必須列
project_id, work_date, worker_id, role_id, start_time または hours, end_time（start_time がある場合）

### 9.3 任意列
break_minutes, hours, notes, external_row_key, shift_label（**DEC-007: 任意**）

### 9.4 import_batch.mode
| モード | 用途 |
|--------|------|
| append | 原則使わない |
| upsert_by_external_key | external_row_key がある場合 |
| replace_scope | **推奨デフォルト** |

### 9.5 replace_scope スコープ
- `project_month`（推奨）
- `project_day`
- `project_day_worker`

### 9.6 二重化防止・洗い替え
1. **DEC-001**: 重複キー `(file_hash, project_id, period_key)`
2. スコープ内 active → superseded（物理削除しない）
3. 新規行を active で INSERT
4. 行数急減（前回比 50% 未満）で警告

**DEC-002**: period_key は YYYYMM 6桁。  
**DEC-003**: アサインなし行はエラー拒否。

**実装メモ**:
- `replace_scope` のみ実質運用。`upsert_by_external_key` / `append` は未実装
- `has_total_time_warning` ロジック未実装
- `count_skip` は常に 0
- **締め状態チェックなし**（Soft/Hard Close 後も取込可能）

---

## 10. アサイン取消・差替え

### 10.2 取消
- canceled 変更時、紐づく active actual がある場合はブロック（Admin 例外: invalid 化 + 理由必須）
- 集計は actual.status が正本

### 10.3 差替え
- Soft Close 前: invalid + replace_scope で再取込
- Hard Close 後: 訂正フロー

**実装メモ**: `invalidate_actuals_for_canceled_assignment()` 実装済み。

---

## 11. 請求書・支払明細

### 11.1 原則
- 発行後上書き禁止
- PDF は version ごとに保存（**DEC-015**: 暫定 `storage/`、object key を DB 保持）
- 明細行が正本

### 11.2 訂正 vs 再発行
- **訂正（推奨）**: 親 CLOSED、子 version+1、明細コピー + 訂正行
- **再発行（例外）**: Accounting 承認 + 理由

### 11.3 税
**DEC-005**: 合計計算、税率 10% 暫定。

**DEC-016**: `payout_deliveries` に送信試行ごとに履歴追記。

**DEC-019**: payout は `recipient_type` / `recipient_id` を正本（worker / supplier / vanzai_staff）。

**実装メモ**: `reissue_invoice()` は合計のみ引き継ぎ、**明細行未コピー**（バグ候補）。

---

## 12. 締め処理

### 12.1 Soft / Hard Close

| 種別 | タイミング | 解除 |
|------|-----------|------|
| Soft Close | 取込完了・差分確認・帳票生成前 | 制約付きで可 |
| Hard Close | invoice issued / payout approved|paid 後 | 原則不可 |

### 12.2 Soft Close 解除ガードレール
- 回数上限: **2回**
- 二者承認（実行者 ≠ 承認者）
- 再締め期限: **7営業日**（仕様）→ 実装は **7暦日**
- 超過時エスカレーション（仕様）

### 12.3 Hard Close 後
unlock しない。訂正/再発行で対応。

**実装メモ**:
- `release_hard_close()` は例外 API として存在（SOFT_CLOSED に戻す、再締め 3暦日）
- **csv_import / invoice_service / payout_service は締め状態を参照しない**
- 締めガードは `recalculation.py` の Hard Close チェックのみ

---

## 13. ダッシュボード

未処理一覧の列: 未確定シフト、実績未提出、取込残件、差分アラート、締め解除履歴。

**実装メモ**: `get_dashboard_summary()` 実装済み。差分アラートの後続アクション列は部分実装。

---

## 14. 運用カレンダー・催促

### 14.1 営業日基準
期限起算は営業日カレンダーを正本とする（**実装未対応: 暦日で代替**）。

### 14.2 催促手段
暫定: システム通知 + メール。reminder / escalation 履歴を保持。

---

## 15. CSV遅延救済（provisional）

月末+3営業日で provisional 扱い。遅延提出後は replace_scope、発行済みなら訂正/再発行。

**実装メモ**: provisional フローはコードベース未検出。

---

## 16. 監査ログ（必須イベント）

単価ルール変更、実績取り込み、replace_scope、Soft/Hard Close、解除、訂正/再発行、経費承認、インセンティブ、送信、振込バッチ、備品貸出/返却

**API**: `POST /api/audit/search`（正本）。`GET /api/audit-logs` は未実装。

**実装メモ**: `ACTUAL_SUPERSEDED`, `PRICE_RULE_CHANGED` は Enum のみで未記録。

---

## 17〜26. 拡張機能（v0.3 追加）

| 章 | 機能 | 実装状況（2026-06） |
|----|------|---------------------|
| 17 | 経費精算 | ✅ Web 実装済み |
| 18 | インセンティブ | ✅ 部分実装（優先順位未確定） |
| 19 | 支払明細送信 | ✅ payout_deliveries |
| 20 | 銀行振込フォーマット | ⚠️ `bank_transfer.py` のみ、DB テーブルなし |
| 21 | 貸出備品 | ❌ Kintone のみ |
| 22 | 案件説明資料 | ⚠️ migration のみ（ORM なし） |
| 23 | タスク進捗 | ⚠️ migration のみ（ORM なし） |
| 24 | 現場管理者可視化 | ⚠️ project manager フィールドあり、DEC-011 未確定 |
| 25 | 売上/粗利 | ⚠️ aggregation API あり、PL ダッシュボード未整備 |
| 26 | 実績フォーム漏れアラート | ❌ 専用実装未確認 |

**DEC-008**: キャンセル料（3日前10%/前日20%/当日50%）確定。ルール投入は運用側。

**DEC-009**: drv 日額支払（1人工 = worker×date×project）。

---

## 27. 未決事項一覧

| 論点 | 状態 | 参照 |
|------|------|------|
| 全銀 FB/CSV 仕様 | 未決 | DEC-004 Follow-ups |
| 貸出備品マスタ | 未決 | CHANGELOG §21 |
| インセンティブ複数ルール優先順位 | 検討中 | STATUS.md |
| 税率変更履歴 | 未決 | DEC-005 Follow-ups |
| site_manager 正本 | Proposal | DEC-011 |
| Kintone 停止条件 | 未決 | STATUS.md |
| R2 本番切替 | 暫定ローカル | DEC-015 |
| 締め×取込/帳票の統合ガード | **実装ギャップ** | コード照合 2026-06 |

---

## 付録 A. API 正本パス（コード照合 2026-06）

| 領域 | 正本パス |
|------|---------|
| CSV | `POST /api/csv/import`, `POST /api/csv/upload` |
| 締め | `POST /api/closing/soft`, `/hard`, `/soft/release`, `/hard/release` |
| 監査 | `POST /api/audit/search` |
| 請求生成 | `POST /api/invoices/generate` |
| 支払生成 | `POST /api/payouts/generate` |
| 公開登録 | `/public/registrations/*`（token + PIN） |

エントリポイント: `src/api/main.py`（100 エンドポイント）。`main_simple.py` は開発用スタブ（5 EP、認証なし）。

---

## 付録 B. 関連ドキュメント

- `docs/decisions/DECISION_LOG.md`
- `docs/spec/REVIEW_MERGE_v0.3.md`
- `docs/spec/CHANGELOG_v0.3_2026-01-27.md`
- `docs/ops/IMPLEMENTATION_STEPS_FROM_SPEC.md`
- `project-docs/`（移植・引き継ぎ向け要約）
