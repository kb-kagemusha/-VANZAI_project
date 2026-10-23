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
- 全銀フォーマットの最終仕様確定（DEC-004 Follow-ups）
- 貸出備品の Web DB 化（未実装）

**実装メモ（2026-07-24、置き場所更新 2026-10-11）**: Kintone 連携は本番から除去済み。マスタ・帳票・運用の正本は Web システム（admin-web / API）のみ。旧連携スクリプトは `.old/`（未使用。実行しない）。手順の記録は `docs/kintone/`（アーカイブ）。

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
| site_manager | 全案件の参照、担当案件のCSV提出（`CSV_SUBMIT`）。請求・支払・単価は初期設定で不可（DEC-056） |
| worker | スタッフモバイル（予定返信、打刻、可否、経費） |

**DEC-011 / DEC-056**: CSV提出範囲の担当判定は `project.primary_manager_id` / `secondary_manager_id`。
`shift_slot.site_manager_id`（CHANGELOG §24）との整合は未確定。

---

### 5.1 ログインIDと役割の管理（DEC-056）

全体管理者だけがログインIDの作成、役割の付与・変更、IDの有効/無効、役割ごとの閲覧・操作権限を設定する。
標準役割admin/ops/accounting/site_managerに加え、管理者が名前と権限を指定して独自役割を作成できる（DEC-057）。同じ役割の全IDに同じ権限セットを適用する。
adminは全権限固定、自分自身の降格・無効化は拒否する。workerの既存モバイル権限は維持する。
管理者は標準役割（adminを含む）と独自役割の表示名を名称変更専用ポップアップで変更できる（DEC-059/060）。名称変更には理由入力を要求せず、名称の変更前後・実行者・日時を自動で監査する。識別子・付与済みID・権限は変更しない。空欄・他の役割との重複・他の標準役割名・内部識別子は拒否する。workerはこの画面の対象外。
usersの既存列を再利用し、role_access_policies（role主キー、display_name、permissions JSON、created_at/updated_at）に役割定義と設定を保存する。標準役割は未設定なら既定値を使用する。独自役割の識別子はシステム発行とし、初期権限なしから選択する。display_nameは重複を拒否する。
画面・直接URL・APIの権限を確認し、APIは各リクエストで現在のDB設定を確認する。
ID作成、役割/有効状態変更、権限セット変更を監査し、変更前後・理由・実行者を残す。パスワードは返却・監査しない。
現場管理者の全案件閲覧は担当者紐付けを不要とするが、CSV提出の担当案件制限は拡大しない。
運用手順はdocs/ops/ACCESS_MANAGEMENT_RUNBOOK.mdを参照。

### 5.2 一覧からの作成・編集入力（DEC-057）

新規作成・登録・生成のフォームは一覧に常設せず、明示的なボタンからポップアップで開く。
ID・役割・案件・シフト枠・配置・請求・支払・単価・通知・登録リンクに共通適用し、既存のマスタ・稼働者・依頼書のポップアップ方式を維持する。
編集フォームも同じポップアップ方式へそろえる。検索・絞り込みは一覧上に残す。
ポップアップはフォーカスを内部に保ち、Escape/閉じるで閉じ、元の操作ボタンへフォーカスを戻す。送信中の閉じる操作は受け付けない。
DEC-077: 発注依頼書は「テンプレートの作成」から再利用内容を直接保存できる。日付・期限・送付先を入力せず、依頼書や送付記録を作らない。既存の作成済み依頼書からの保存と同じ一覧・呼出し・権限・監査・非破壊除外を利用する。直接作成の保存元版はNULLとし、既存の保存元は保持する（migration `20261023e001`）。
DEC-078: 発注依頼書の案件名（確定時必須）と参考URL（任意）を分離し、左半分の同じ枠に置く。参考URLは既存request_conditions JSONのreference_urlに保存し、本文・PDF・テンプレートで保持する。稼働場所は会場名、稼働場所の住所は既存site_addressに郵便番号を含む住所として保存する。郵便番号検索は取引先登録と共通の補完処理を使用し、手入力済み住所の自動上書きを防止する。DB変更・旧データの一括変換は行わない。
共通レコードフォームのポップアップは内容に合わせた高さとし、項目間を画面の高さまで引き伸ばさない。長いフォームは画面内に収めて内部スクロールにする。名称変更など少数項目の画面は横幅も小さくする（DEC-060）。

---

## 6. データモデル

### 6.1 主要エンティティ

**マスタ**: worker, client, site, project_type, role, price_sales, price_outsource, price_rule, incentive_rule, supplier, vanzai_staff

稼働者タグは `workers.tags`（定義済みコードの配列）に保存する。自由入力は受け付けない。定義の正本は `src/domain/worker_tags.py`（DEC-029）。

稼働者の最寄り駅は既存の `nearest_station` / `station_walk_minutes` を1駅目として保持し、任意の2駅目以降は `additional_stations`（駅名・徒歩分数の配列）へ保存する。管理画面・LINE登録の双方で追加・削除でき、LINEは承認後に反映する。詳細はDEC-050。

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

### 11.4 依頼書の金額確定・依頼元別月次請求（DEC-074 / 2026-10-23）
- 全体管理者（admin）のみが、正式・確定済みの最新依頼書について、通常請求額（税抜）・請求月を記録する。請求先は依頼書の発注元クライアントに固定し、金額画面・APIで別の請求先を選べない（DEC-075）。稼働者への支払単価と分離する。
- 月をまたぐ依頼も管理者が指定した請求月へ全額計上する。0円は記入済み。金額未入力件数をサイドメニューの赤いバッジに表示し、下書き・テスト・取消・削除・旧版は除外する。
- 金額は依頼書の版ごとの追記履歴とし、変更理由と実行者を保存。依頼書改訂時は新しい版の金額を再確認する。
- `order_billing_invoice_lines` の明細行を正本として請求先・請求月別に集約。小計×10%の円未満を切り捨てる。税率・丸め・請求先と明細をスナップショット化する。
- 下書き→内容/PDF確認→明示的発行。発行後は明細・PDF固定。下書き取消は理由を記録し、旧版/PDFを残して再作成する。発行済み訂正・追加請求は別途仕様決定とし、上書きしない。
- 依頼系列単位の一意な請求割当と同一請求先/月の有効帳票一意制約で二重計上を防ぐ。既存実績請求との対応が未定義なため、同一請求先/月の両経路併用を相互拒否する。
- 新規5テーブル追加migration `20261023c001`。既存実績・支払・締め処理とは独立し、既存請求一覧へ自動転記しない。全体管理者以外には監査検索でも金額を公開しない。
- 発行元の正式名称・郵便番号・住所・登録番号・振込先・支払期限/条件を管理者が設定し、作成時点の設定を帳票に保持。初期値は株式会社VANZAI／〒116-0002 東京都荒川区荒川1丁目39-11 東京アルバタワー1703（ユーザー指定）。未指定の任意項目は空欄。変更は新しい請求書だけに反映する。手順は `docs/ops/ORDER_BILLING_RUNBOOK.md`。
- DEC-075: 依頼書はインセンティブなし／ありを選択し、初期値なしは「インセンティブなし」を自動記載。ありは条件メモを必須とする。金額画面には条件メモをそのまま表示し、ありの場合だけ実績後に税抜インセンティブ額を入力して通常請求額に加算する。金額未確定はNULL（0円と区別）として先行保存できるが、未処理件数に残し、同じ請求先/月の月次請求書生成・発行を停止する。
- DEC-075: `order_billing_amounts.incentive_amount` と版ごとの条件snapshot、`order_billing_invoice_lines.incentive_amount/incentive_note` を追加。明細のamountは通常額＋インセンティブの税抜合計。旧金額・旧明細・旧PDFを更新しない。以前の請求先不一致やインセンティブ未確認は自動補正せず再確認する。追加migration `20261023d001`。
- DEC-076: 通常請求額・インセンティブ額の入力表示は半角数字・3桁カンマ区切りとし、直下に万円・億円などの単位による補助を表示する（例: `200,000` / `20万円`）。APIへはカンマなしで送信し、金額・計算・保存方式は変更しない。
- DEC-077: 金額補助の「25万円」などは入力欄の数字と左端をそろえ、フォントを1remに拡大する。金額の正本・保存・計算は変更しない。

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

### 14.3 カレンダー・依頼書・参加日の確認（DEC-071）
イベントごと・稼働者ごとの横長のカレンダーは日付と名前を固定し、文書番号から依頼書詳細をポップアップ表示する。
依頼書の稼働日選択は月曜始まり。送付前のPDF確認から「修正する」で同じ下書きの入力へ戻る。
LINEの日付選択は月をまたいだ選択可能日の全選択に対応する。確認・受付通知では期間・共通休業日・参加日・不参加日を区別し、不参加日に共通休業日を含めない。連続する2日以上は期間にまとめ、離れた日は1日1行で表示する。
DB・受諾済み参加日の正本・会計計算は変更しない。

### 14.4 発注依頼書のテンプレートと参加日の初期値（DEC-072）
保存済み依頼書の内容を名前付きの独立したスナップショットとして保持し、新規作成時に検索して呼び出せる。
`order_request_templates` に名前・正規化名・再利用用payload・保存元の版と文書番号・保存者・日時・一覧除外日時と実行者を保存する。有効な名前はDBの部分一意インデックスで重複を拒否する。物理削除・既存テンプレートの上書きはしない。
日付・休業日・回答期限・送付先と個人不参加日・電話済み情報・回答状況を引き継がない。稼働条件・時刻・単価などは引き継ぎ、今回の内容を確認して別の新規依頼として保存する。保存と一覧除外にorder_write、閲覧にorder_readを要求し、操作を監査する。
LINEの日付選択は初めから本人の選択可能な全日を選び、本人が参加できない日だけ外す。DEC-071の全日選択ボタンは撤去する。確認を経由して送信した時だけ受諾を記録し、受諾済みの場合は保存済み参加日だけを表示する。

### 14.5 依頼書の期間制限・入力配置（DEC-073）
勤務詳細・単価詳細の日付選択を、全体の稼働日の開始日〜終了日内に制限する。全体の期間が未設定・不正なら選択できない。期間変更で範囲外になった既存入力は自動削除せず再選択を案内し、既存のAPI検証も維持する。
背景を半幅で稼働場所の右に置く。テンプレート呼出しは青い縁、取引相手メモは連絡担当者の右から行末まで広げて「PDFには記載しません」を見出しの右に表示する。期限の案内は「（必須）」を見出しの右に表示し、「期限内に返事がない相手へ案内を送ります」と説明する。電話メモは電話先行チェック時だけ右に表示し、非表示でも既存メモを消さない。狭い画面では縦に並べる。DB・帳票・送付処理は変更しない。

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
| 21 | 貸出備品 | ❌ 未実装 |
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
| Kintone 停止条件 | ✅ 2026-07-24 本番除去完了 | CHANGELOG 0.11.36〜0.11.37 |
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
