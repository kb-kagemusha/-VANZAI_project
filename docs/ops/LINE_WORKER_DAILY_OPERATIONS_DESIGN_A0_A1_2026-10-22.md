# 公式LINE 日次操作 A0・A1 詳細設計書

作成日：2026-10-22
文書状態：**v0.5（A0・A1 実装済み）**。A0は 0.46.8、A1は 0.47.0 で実装。実装で設計と変えた点は §16

変更履歴：v0.5 A1の実装に合わせて更新：**回答受付版とロックを「依頼書」から「系列」へ移した**（§4.4。「変更を作成」で作った依頼書を元の依頼書と同じ系列として扱う＝ユーザー指示「推奨のものを反映」）。実装メモ §16。v0.4 設計レビュー v0.3（R3-01〜03）を反映。v0.3 設計レビュー（D01〜D08）を反映（§15）：子アクションの親機能への対応付け、PDFの発行・閲覧の認可、変更確認中の人の辞退記録、**適用送付行のポインタ表と、元データだけから決まる再構築**、生成元の複合FK、Webhookの応答方針、合意日の上限、テストの起床報告の扱い。v0.1 初版。v0.2 ユーザー回答を反映（C1：送付先ごとの「閲覧を停止」ボタンを撤去し、修正版で外れた人の旧いPDFリンクを自動で無効にする。C2：今後の予定がある依頼書は一覧から外せない。C3：テストの依頼書でも、テストの印を付けて隔離した稼働予定を作る。C4：新しい権限は admin と ops だけに既定で付ける。C7：正式の依頼書もすべて公式LINEで送る＝DEC-067）
対象コード：`feature/2026-03-31-next-work` / アプリ版 `0.46.7`（コミット `958fcb3` 以降、作業フォルダの現行ファイルで確認）
上位文書：
- 計画書 `docs/ops/LINE_WORKER_DAILY_OPERATIONS_PLAN_2026-10-21.md`（v0.9）
- 決定 `docs/decisions/DECISION_LOG.md` DEC-063〜066
- 計画書のレビュー `docs/ops/LINE_WORKER_DAILY_OPERATIONS_REVIEW*_2026-10-2*.md`

作成：Claude（計画書と現行コードの調査から作成）

---

## 0. この文書の範囲と読み方

- 対象は**A0（依頼書の除外日・個人不参加日の入力）とA1（稼働予定、①起床報告、⑤受託済みの発注依頼書、⑥スケジュール確認、当日の起床状況一覧、リッチメニュー）**だけ。A1+・A2・A3・Track Bは対象外。ただし、それらを後から足せるよう、A1のモデルは上書きしない持ち方にする（計画書 §7.13）。
- 業務判断は計画書とDECで確定済み。この文書は「どう作るか」を決める。業務判断が必要になった箇所は、§12の**確認事項**に分けた。
- 現行コードの箇所は、ファイル名と関数名で示す（行番号は版で変わるため、補助としてのみ使う）。
- ラベル：【設計判断】＝この文書で決めること、【要確認】＝ユーザーまたはレビュアーに確認すること。

---

## 1. 結論（要約）

1. **A0**：依頼書の日程JSONの勤務グループに `excluded_dates`（共通の除外日）を追加する。送付先ごとの個人不参加日は、依頼書の本文とは別の列 `order_request_versions.draft_recipient_absences` に持つ（計画書ではJSON内としていたが、§3.2の理由で列に変更する）。
2. **A1の中心は「稼働予定の再構築関数」**。依頼書の確定・受諾・辞退・取消・受諾後の辞退の記録のたびに、依頼書単位のロックの中で、まず元データ（回答受付版・**適用送付行**・参加日の状態）を更新し、そこから（依頼書 × 稼働者）ごとの稼働予定を**元データだけで決まる形で**作り直す。既存の行の状態には依存しない（v0.3で修正）。
3. 追加するテーブルは6つ（`delivery_participation_states`、`order_request_worker_applications`、`worker_schedule_entries`、`wake_reports`、`line_action_tokens`、`line_rich_menu_releases`）。既存テーブルへの列追加は4つ（`order_request_documents.answerable_version_id`、`order_request_deliveries.offered_dates` と `current_participation_state_id`、`order_request_versions.draft_recipient_absences`）。
4. Webhookは「イベントごとに、処理済み記録の挿入 → 業務処理 → commit → 返信」の順に作り直す。既存の受諾・辞退も同じ順序にする。
5. 現行コードとの調整が必要だった点（§12のC1〜C7）は、2026-10-22のユーザー回答で確定した。

---

## 2. 現行コードの前提（設計に効く事実）

| 項目 | 現行の動き | 場所 |
|---|---|---|
| 日程JSON | `request_conditions`（JSON文字列、`format=additional-request-v1`）の `schedule.work_groups[]`。各グループは `id`・`date_mode`（single/range）・`from`・`to`・`start_time`・`end_time`・`end_next_day`。pydanticの `extra="forbid"`・`strict=True`。グループの日付は重複不可 | `src/domain/order_schedule.py`（`WorkGroup`、`Schedule`、`normalize_schedule`） |
| JSONの保存 | `parse_sections` → `canonical_conditions` で**既知のキーだけ**を書き戻す。未知のキーは保存時に消える | `src/services/order_request_format.py` |
| 確定 | `confirm()` が下書きの `draft_worker_ids` から送付行を作り、PDFを生成・保存する。`snapshot_json` に本文などを固定する | `src/services/order_request_service.py` |
| 改訂・取消 | `revise()` は確定版を複製してdraftを作る。`cancel()` は**版**単位で、draftにも確定版にも使える | 同上 |
| 送付 | `send_one()` が送付行ごとに期限7日のPDFトークンを発行し、プッシュで送る。受諾済みには再送しない。テスト／正式とも送れる（2026-10-06のコミット `3724948` 以降） | `src/services/line_order.py` |
| 返答 | ポストバック `or_accept:<delivery_id>` で受諾、`or_decline:<delivery_id>` で辞退の理由待ち → 次のテキストで辞退確定。版が回答受付中かどうかは判定しない | 同上（`_handle_postback`、`_accept`、`_begin_decline`、`_take_decline_reason`） |
| Webhook | イベントIDを事前SELECTで判定 → 処理 → 返信 → 処理済み記録 → ルートの最後で1回だけcommit | `src/api/line_webhook_routes.py`、`line_order._handle_event` |
| ロック | LINE登録は「申請 → 稼働者 → 紐付け」の順に行ロックを取る。依頼書には採番のadvisory lockしかない | `src/domain/line_registration_locks.py`、`order_request_service._lock_document_numbers` |
| 権限 | `Permission` 列挙と、役割ごとの既定値 `ROLE_PERMISSIONS`。独自に権限を設定した役割は `role_access_policies.permissions` が優先される | `src/models/enums.py`、`src/services/auth.py` |
| 監査 | `AuditService.log(action, target_type, target_id, actor, actor_role, before_value, after_value, reason, extra_metadata)` | `src/services/audit.py` |
| マイグレーション | Alembic。リビジョンIDは日付形式（最新 `20261020a003`） | `alembic/versions/` |
| staff-mobile | 稼働者向けの `/today`・`/schedule` は、アサイン（assignments）を読む | `apps/staff-mobile/src/app/App.tsx`、`MobileShell.tsx` |

---

## 3. A0：依頼書の入力

### 3.1 共通の除外日（休業日）

- `WorkGroup` に `excluded_dates: list[str] = []` を追加する（ISO日付の文字列）。
- 検証（`normalize_schedule`）：
  - `date_mode=single` では空でなければならない
  - 各日付は `from`〜`to` の範囲内。重複は不可。昇順に並べ替えて保存する
  - `complete=True`（確定時）では、除外したあとに勤務日が1日以上残ること
  - 期間を縮めて範囲外になった除外日は、**自動では消さずにエラー**にする（「期間外の休業日があります」）。黙って消すと、入力した人が気づかないため
- `Schedule.version` は1のまま。旧データには `excluded_dates` がないので、既定値の空配列として読む。
- **展開の共通処理**（新規）：`expand_work_days(schedule) -> list[WorkDay]`（`src/domain/order_schedule.py`）。1つの勤務グループを日ごとに展開し、除外日を除く。`WorkDay` は（`work_group_id`, `work_date`, `start_time`, `end_time`, `end_next_day`）。
  - **本文・PDFの日付表示、単価のカバー確認、提示日の計算、稼働予定の生成は、すべてこの関数を使う**（V3レビュー §4）
  - 単価のカバー確認は、除外日を除いた実勤務日について行う（除外日の単価は不要）
- 本文の表示（`schedule_text` の `date_label`）：期間に除外日があれば「2026年11月1日～2026年11月10日（休業日：11月3日、11月7日）」とする。
- 旧い確定版の本文・PDFは再生成しない（確定版は `snapshot_json` と保存済みPDFを使う既存の仕組みのまま）。
- 管理画面：`OrderScheduleEditor.tsx` の「複数日の期間」の行に「休業日を追加」ボタンと日付のチップを置く（AGENTS.md §12：追加・削除はボタンとして見えるように）。

### 3.2 個人の不参加日

**保存先**【設計判断】：新しい列 `order_request_versions.draft_recipient_absences`（JSON、nullable）に `{worker_id: ["YYYY-MM-DD", ...]}` で持つ。

計画書（§9）では依頼書の `request_conditions` JSON 内としていたが、次の理由で列に変える。
- `request_conditions` は**依頼書の本文の元データ**で、確定時に `snapshot_json` を通して全員共通の内容として固定される。個人の日付は全員共通の内容ではない
- 既存の `draft_worker_ids`（送付先の一覧）と同じく、**送付先ごとの下書きデータ**として扱うほうが自然
- `canonical_conditions` は既知のキーだけを書き戻すので、JSON内に置くと書式処理の変更が必要になり、本文の生成にも影響しやすい

**検証**（`update_draft` と `confirm` の両方）：
- キーは `draft_worker_ids` に含まれる稼働者だけ（送付先から外した人の不参加日は、保存時に取り除く）
- 日付は、その時点の**実勤務日**（`expand_work_days` の結果）に含まれること
- 確定時：その人の提示日（実勤務日 − 個人不参加日）が0日なら、確定を拒否する（「〇〇さんの稼働日が0日です。送付先から外してください」）

**改訂**：`revise()` で新しいdraftにコピーする（`draft_worker_ids` と同じ扱い）。

**管理画面**：送付先の一覧の各行に「不参加日」ボタンを置き、ポップアップで実勤務日の中から選ぶ。

**表示の範囲**：個人の不参加日は、管理画面とその本人へのLINEにだけ表示する。PDF・本文・他の送付先へのLINE・他人が呼べるAPIには含めない。

### 3.3 A0の版

既存の依頼書への項目追加なので **Z**（AGENTS.md §9、DEC-065）。

---

## 4. A1：データモデル

### 4.1 既存テーブルへの追加

| テーブル.列 | 型 | 意味・制約 |
|---|---|---|
| `order_request_documents.answerable_version_id` | String(26), nullable, FK | **回答受付版**。確定時に、その版を指す。その版を取消したら NULL。旧版へは戻さない（DEC-063）。別の依頼書の版を指せないよう、`order_request_versions` に UNIQUE(id, document_id) を追加し、複合FK (answerable_version_id, id) → versions(id, document_id) にする |
| `order_request_versions.draft_recipient_absences` | JSON, nullable | A0の個人不参加日（§3.2） |
| `order_request_deliveries.offered_dates` | JSON, nullable | **提示日**。確定時に計算して固定する。以後は変えない。NULL は「A1導入前に確定した送付行」で、稼働予定の対象外 |
| `order_request_deliveries.current_participation_state_id` | String(26), nullable, FK | 現在の参加日の状態。同じ送付行の状態だけを指せるよう、複合FK (current_participation_state_id, id) → delivery_participation_states(id, delivery_id) |
| `order_request_deliveries` の UNIQUE | — | 複合FKの参照先として UNIQUE(id, worker_id) と UNIQUE(id, version_id) を追加する（D05） |

`answerable_version_id` の既存データの埋め方（マイグレーション内）：依頼書ごとに `status='confirmed'` の版のうち `version_no` が最大のものを入れる。それより後に「確定されてから取消された版」（`confirmed_at IS NOT NULL AND status='cancelled'`）があれば NULL。運用開始前なので、対象は試験データだけ。

### 4.2 新しいテーブル

**`delivery_participation_states`**（参加日の状態。追記のみ）

| 列 | 型 | 備考 |
|---|---|---|
| id | String(26) PK | |
| delivery_id | FK → order_request_deliveries | |
| seq | Integer | 送付行ごとに1から。UNIQUE(delivery_id, seq) |
| dates | JSON | 参加日（昇順、重複なし）。0日も可（辞退の記録）。**上限**（D07）：すべての状態で、その版の**実勤務日**の部分集合。`full_accept` と `partial_accept` は**提示日**の部分集合。`change_approved`（A1+）は承認内容と実勤務日を上限とし、当初の個人不参加日を承認で追加できる（提示日のスナップショットは後から広げない） |
| source | String(30) | `full_accept`（A1）/ `ops_recorded_decline`（A1）/ `partial_accept`・`change_approved`（A1+で使用） |
| reason | Text, nullable | 受諾後の辞退の理由など |
| change_request_id | String(26), nullable | A1+の変更申請。A1では常に NULL |
| created_by | String(64) | `line-webhook` または運営のユーザーID |
| created_at | DateTime(tz) | |

- UNIQUE(id, delivery_id)（複合FKの参照先）
- CHECK(seq > 0)、CHECK(source IN (...))
- 更新・削除しない（物理削除禁止。AGENTS.md §2）
- `dates` の正規化（昇順・重複なし・ISO形式）と上限の確認はサービス側で行う（DBでは保証しない）。`offered_dates` を確定後に変えないことも、サービス側と試験で保証する

**`order_request_worker_applications`**（依頼書×稼働者の**適用送付行**。D03・D04）

| 列 | 型 | 備考 |
|---|---|---|
| id | String(26) PK | |
| document_id | FK | |
| worker_id | FK | |
| applied_delivery_id | String(26), nullable | その人に**現在適用されている**送付行（受諾済みのもの）。NULL は「現在、この依頼書で予定がない」 |
| applied_version_id | String(26), nullable | 上の送付行の版。複合FK (applied_delivery_id, applied_version_id) → deliveries(id, version_id)、(applied_version_id, document_id) → versions(id, document_id) で、別の依頼書・別の版を指せないようにする |
| ended_reason | String(40), nullable | `applied_delivery_id` を NULL にした理由：`declined_new_version` / `removed_from_recipients` / `document_ended` / `view_revoked` |
| updated_at / updated_by | | |

- UNIQUE(document_id, worker_id)
- 複合FK (applied_delivery_id, worker_id) → deliveries(id, worker_id) で、本人の送付行だけを指せるようにする
- **ロックの中の出来事だけで更新する**（受諾で設定、辞退・送付先から外れる・依頼の終了で NULL と理由）。稼働予定の行からは逆算しない。これが再構築の入力になる（§5.1）
- 受諾後の辞退（運営の記録）では NULL にせず、適用送付行に0日の参加日の状態を追記する（履歴を参加日の状態に残すため）

**`worker_schedule_entries`**（稼働予定。派生データ）

| 列 | 型 | 備考 |
|---|---|---|
| id | String(26) PK | |
| document_id / version_id / delivery_id | FK | 組み合わせも複合FKで保証する（D05）：(version_id, document_id) → versions(id, document_id)、(delivery_id, version_id) → deliveries(id, version_id) |
| worker_id | FK → workers | 複合FK (delivery_id, worker_id) → deliveries(id, worker_id) で整合を保証する（deliveries に UNIQUE(id, worker_id) を追加） |
| work_group_id | String(64) | 日程JSONの勤務グループID |
| work_date | Date | |
| start_time / end_time | Time | |
| end_next_day | Boolean | |
| status | String(20) | `active` / `changing` / `superseded` / `cancelled`（CHECK制約） |
| status_reason | String(40), nullable | `document_ended` / `removed_from_recipients` / `declined_new_version` / `ops_recorded_decline` / `view_revoked` / `not_in_participation` |
| source_state_id | String(26), nullable | 作成・更新の根拠にした参加日の状態。複合FK (source_state_id, delivery_id) → delivery_participation_states(id, delivery_id) |
| project_name / site_name / site_address / meeting_place | Text | 表示用。**その版の `snapshot_json` から**写す |
| created_at / updated_at | DateTime(tz) | |

- UNIQUE(delivery_id, work_group_id, work_date)
- 索引：(worker_id, work_date, status)、(document_id)
- **同じキーの行は作り直さず、状態を更新する**（いったん外した日が、あとで戻った場合も同じ行を `active` に戻す）。経緯は参加日の状態と監査に残る（V8レビュー §4）
- 金額の列は持たない（DEC-063）
- `is_test`（Boolean）：テストの依頼書から作った行。本人のLINEには「【テスト】」付きで表示し、運営の起床状況一覧・A2・Track Bの対象から除外する（§12-C3）

**`wake_reports`**（起床報告）

| 列 | 型 | 備考 |
|---|---|---|
| id | String(26) PK | |
| worker_id | FK | |
| report_date | Date | LINEイベントの発生時刻（`timestamp`）の日本時間の日付 |
| event_occurred_at | DateTime(tz) | LINEイベントの発生時刻 |
| received_at | DateTime(tz) | サーバーの受信時刻 |
| late_received | Boolean | 受信が発生から30分以上遅れた |
| is_test | Boolean | その日の表示対象の予定が**テストの予定だけ**のときの報告（§7.4、D08） |
| line_event_id | String(64) | |
| created_at | DateTime(tz) | |

- UNIQUE(worker_id, report_date, is_test)（テストの報告と本番の報告を分ける。§7.4）

**`line_action_tokens`**（「続きを見る」「依頼書を開く」の短命トークン）

| 列 | 型 | 備考 |
|---|---|---|
| id | String(26) PK | |
| token_hash | String(64) UNIQUE | 平文は保存しない（既存の一次コードと同じ考え方） |
| worker_id | FK | |
| action | String(30) | `schedule_next` / `open_order` |
| payload | JSON | `schedule_next`：表示範囲（開始日・終了日）と最後に表示した位置（work_date, start_time, entry_id）。`open_order`：document_id と delivery_id |
| expires_at | DateTime(tz) | 発行から30分【設計判断】 |
| created_at | DateTime(tz) | |

- 期限内は何度押しても同じ結果を返す（使い捨てにはしない。LINEのボタンは何度でも押せるため）
- 押されるたびに、トークンの稼働者とLINEの本人が一致するかを照合する

**`line_rich_menu_releases`**（リッチメニューの公開記録）

| 列 | 型 | 備考 |
|---|---|---|
| id | String(26) PK | |
| stage | String(20) | `a1` など |
| rich_menu_id | String(80) | LINE側のID |
| enabled_actions | JSON | 押せるパネルの一覧（例：`["wk_wake","wk_orders","wk_schedule"]`） |
| image_sha256 | String(64) | アップロードした画像 |
| applied_at / applied_by | | |

- `enabled_actions` に入れるのは**親の機能**（`wk_wake` / `wk_orders` / `wk_schedule` など）だけ。子のボタン（続きを見る・依頼書を開く）は親の機能に対応付けて判定する（§7.2、D01）
- サーバーは、**最新の記録の `enabled_actions`** を「有効な機能」の正本として使う。押せないはずのパネルのポストバックが届いたら「この機能はまだご利用いただけません」と返す（古いメニューが端末に残っている場合の保険。DEC-064）

### 4.3 マイグレーション

| リビジョン | 内容 | 段階 |
|---|---|---|
| `20261022a001` | `order_request_versions.draft_recipient_absences` | A0 |
| `20261022a002` | `answerable_version_id`（既存データの埋め込みを含む）、versions の UNIQUE(id, document_id)、deliveries の `offered_dates`・`current_participation_state_id`・UNIQUE(id, worker_id)・UNIQUE(id, version_id)、`delivery_participation_states`、`order_request_worker_applications`（既存の受諾済み送付行からの埋め込みを含む）、`worker_schedule_entries`、`wake_reports`、`line_action_tokens`、`line_rich_menu_releases` | A1 |

- 除外日（`excluded_dates`）は既存のJSONの中なのでDDLは不要。
- 既存の行・列は書き換えない（`answerable_version_id` の埋め込みだけは新しい列への書き込み）。
- 複合FKと部分的なUNIQUEは、PostgreSQLとSQLite（試験）の両方で動く形にする（既存の部分索引の書き方に合わせる）。
- `order_request_deliveries.current_participation_state_id` と `delivery_participation_states.delivery_id` は互いを参照する（循環）。テーブルと列を先に作り、`current_participation_state_id` のFKは最後に `ALTER TABLE` で追加する。SQLiteでは制約付きのテーブル再作成（batch）になるので、空のDBと試験データ入りのDBの両方で適用を確認する
- 試験：不正な組み合わせ（別の依頼書の版、別の送付行の状態、他人の送付行）をDBが拒否することを確認する

### 4.4 依頼書の系列（v0.5で追加）

**背景**：現行の「変更を作成」は、元の版を基に**新しい依頼書（新しい文書番号）**を作る。回答受付版とロックを依頼書単位にすると、変更を作成した新しい依頼書が確定しても、元の依頼書の稼働予定は「確定済み・受諾済み」のまま残り、同じ人に同じ日の予定が二重に出る。

**決定**：「最初の依頼書」と、そこから「変更を作成」で作った依頼書を、1つの**系列**（`order_request_series`）にまとめる。§4.1・§5・§6 で「依頼書単位」と書いている回答受付版・適用送付行・ロックは、すべて**系列単位**と読み替える。

| 項目 | 内容 |
|---|---|
| 系列の作り方 | 新規作成は新しい系列（系列IDは依頼書ID）。「変更を作成」は元の版の系列に入る。改訂（同じ依頼書の次の版）は同じ系列 |
| `order_request_versions.series_id` | 作成時に決め、以後は変えない。複合FKの参照先として UNIQUE(id, series_id)・UNIQUE(id, document_id) |
| `order_request_series.answerable_version_id` | **回答受付版**＝系列の中で最後に確定した版。その版を取消したら NULL（系列の終了）。旧版へは戻さない。複合FK (answerable_version_id, id) → versions(id, series_id) |
| `order_request_worker_applications` | 一意キーは (series_id, worker_id)。適用送付行は系列内の版の送付行だけを指せる（複合FK） |
| `worker_schedule_entries.series_id` | 系列。旧い版・別の依頼書の予定は、より新しい版に受諾があれば `superseded`（R3-03） |
| ロック | 系列の行を `SELECT … FOR UPDATE`。確定・取消・受諾・辞退・受諾後の辞退・送付・PDF発行・一覧から外す、をこのロックで直列化する |
| 送付 | 回答受付版の送付行だけ送れる（旧い版・別の依頼書の旧い版は 409） |
| 既存データ | マイグレーションで依頼書ごとに系列を作る。A1以前の「変更を作成」の依頼書は別系列のまま（正式運用前のため） |

例：依頼書 A（第1版を受諾）→「変更を作成」で依頼書 B を確定 → A の予定は「変更あり（新しい依頼書の確認待ち）」→ B を受諾すると B の予定が有効、A の予定は `superseded`。B を辞退すると A の予定は取消（`declined_new_version`）。

---

## 5. A1：稼働予定の作り方

### 5.1 再構築関数（D04で全面的に修正）

`rebuild_schedule_entries(session, document_id, worker_id)`（新規 `src/services/worker_schedule.py`）

呼び出し元は、必ず依頼書単位のロック（§6）の中。**元データだけから「あるべき稼働予定」を計算し、既存の行と突き合わせて合わせる**。既存の行の状態は判断の根拠にしない（行のIDと一意キーを保つためだけに使う）。

**入力（元データ）**
- 依頼書：区分（formal/test）、`answerable_version_id`、確定した版があるか
- 適用送付行の表（`order_request_worker_applications`）：その人の `applied_delivery_id` と `ended_reason`
- 適用送付行の現在の参加日の状態（`current_participation_state_id` の `dates`）
- 適用送付行の版の日程（`snapshot_json` の日程を `expand_work_days` で展開したもの）

**手順1：あるべき集合を計算する**
- 適用送付行がない（NULL）→ あるべき集合は空
- 適用送付行 `P` がある →
  - 実勤務日のうち、`P` の現在の参加日に含まれる日だけを、あるべき行とする（キー：`P` の delivery_id × work_group_id × work_date）
  - 状態：`P` の版が回答受付版なら `active`。そうでなければ `changing`（新しい版への返事待ち。L-26）
  - `is_test`：依頼書が `test` なら true

**手順2：既存の行と突き合わせる**
- あるべき集合にある行 → なければ作る。あれば、状態・時刻・表示用の値・`source_state_id` を合わせる（`cancelled` だった行も、あるべき集合に入っていれば戻す。根拠は現在の適用送付行と参加日の状態だけ）
- あるべき集合にない既存の行 → 状態を決める：
  - その行の送付行が、適用送付行より**古い版で**、適用送付行が受諾によって置き換わった場合 → `superseded`
  - それ以外 → `cancelled`。`status_reason` は、適用送付行がNULLなら `ended_reason`、適用送付行の参加日から外れた日なら `not_in_participation`（参加日0日なら `ops_recorded_decline`）
- 既に同じ状態の行は書き換えない（更新日時も変えない）

**性質**
- 同じ元データなら、稼働予定の行が1件もない状態からでも、途中の状態からでも、同じ結果になる
- 一度送付先から外れたり辞退したりした人の古い受諾は、適用送付行が置き換わっているので復活しない
- 各行の表示用の値（案件名・会場・住所・集合場所）は、その行の版の `snapshot_json` から取る

**監査**：状態を変えた行ごとに（キー、変更前、変更後、理由）の一覧を `worker_schedule_entries_rebuilt` に記録する（件数だけにしない）。LINEのIDは記録しない。

### 5.2 呼び出す場所（適用送付行の更新を含む）

どの操作も、依頼書のロックを取り、元データを読み直してから行う。

| 操作 | 場所（現行の関数） | 元データの更新 → 再構築 |
|---|---|---|
| 依頼書の確定 | `OrderRequestService.confirm()` | 送付行ごとに `offered_dates` を保存 → `answerable_version_id` を新しい版へ → 新しい版の送付先に**いない**人で適用送付行がある人は、適用送付行を NULL（`removed_from_recipients`）にし、旧い版で発行したPDFトークンを無効にする → 関係する全員を再構築（残った人は `changing` になる） |
| 版の取消 | `cancel()` | 取り消す版が回答受付版なら `answerable_version_id = NULL` とし、その依頼書の全員の適用送付行を NULL（`document_ended`）にする。回答受付版でない版・draftの取消は元データを変えない → 再構築 |
| 受諾（LINE） | `line_order._accept()` | 回答受付版の送付行かを確認（違えば「新しい依頼書が届いています。そちらで回答してください」）→ 参加日の状態 seq=1（`full_accept`、dates＝提示日の全部）→ `current_participation_state_id` → 適用送付行をこの送付行にする → 再構築 |
| 辞退（LINE） | `_begin_decline()`・`_take_decline_reason()` | 回答受付版かを確認 → 辞退が確定したら（理由の受信時）、その人の適用送付行を NULL（`declined_new_version`）→ 再構築 |
| 受諾後の辞退（運営の記録） | 新規 `POST /api/order-requests/documents/{document_id}/workers/{worker_id}/withdraw-acceptance`（理由必須、`ORDER_WRITE`） | **対象は回答受付版ではなく、その人の適用送付行**（D03）。適用送付行がなければ拒否 → 適用送付行に参加日0日の状態を追記（`ops_recorded_decline`、理由・実行者）→ 回答受付版にその人の未返事の送付行があれば、それを `declined`（理由「運営記録：…」）にして、あとから受諾できないようにする → 再構築。現在の状態が既に0日なら何もしない（冪等） |
| 閲覧停止 | `revoke_view()` | **撤去する**（画面のボタンとAPIの両方。§12-C1、DEC-068） |
| 送付 | `send_one()` | 依頼書のロックを取り、**回答受付版の送付行だけ**送れるようにする（D02）。旧い版の送付行は「新しい版が確定しています」で拒否。本文に「あなたの稼働日」を追加する（§7.3） |
| 一覧から外す | `hide_document()` | 依頼書のロックの中で、今日以降の `active`・`changing` の行がある場合は拒否する（§12-C2） |

既存の受諾済みの送付行（A1導入前の試験データ）からの適用送付行の埋め込みは、マイグレーションで行う（回答受付版の送付行で `acked` かつ `offered_dates` があるものだけ。それ以外は NULL）。

### 5.3 回答受付版の照合とPDFの閲覧条件

`_delivery_for_reply()` に次の確認を追加する（ロックの取得後に読み直す）。
- 送付行の版が、その依頼書の `answerable_version_id` と一致すること
- 依頼書が `deleted_at` 付きでないこと（§12-C2）
- 既存の確認（紐付けの本人、取消、送付停止、閲覧停止）は維持する

**PDFの閲覧条件**（D02）：PDFトークンの発行（`send_one`・⑤の再発行）と読み出し（`read_shared_pdf`）の両方で、共通の関数 `pdf_viewable(delivery)` を使う。条件は次のすべて。
- 依頼書が終了していない（`answerable_version_id` がある）
- その人が、回答受付版の送付先に含まれている
- トークンの送付行の版が、回答受付版、またはその人の適用送付行の版である（変更確認中の人が旧い内容を見られるようにするため）
- 版が取消・送付停止でなく、送付行が閲覧停止（古いデータ）でない

読み出しのたびにこの条件を確認するので、送付先から外れた人の旧いリンクは、トークンの無効化に漏れがあっても開けない。URLを開く人にログインは求めない（今の方式のまま）。

---

## 6. ロックと同時実行

### 6.1 ロックを取る順序【設計判断】

すべての処理で、次の順序だけを使う。
1. `order_request_documents` の対象行（`SELECT ... FOR UPDATE`）
2. （必要な場合だけ）`workers` の行
3. （必要な場合だけ）`line_worker_links` の行

- 既存のLINE登録は「申請 → 稼働者 → 紐付け」の順で、依頼書の行は取らないので、この順序と衝突しない。
- 依頼書の行ロックで、同じ依頼書に対する確定・取消・受諾・辞退・受諾後の辞退の記録・送付（`send_one`）・PDFの再発行・一覧から外すを直列化する（V2-04、D02）。
- ロックを取ったあとに、回答受付版・送付行・参加日の状態・紐付けを**読み直してから**判断する。
- SQLite（試験）では行ロックが効かないので、競合の試験はPostgreSQLで行う（既存の競合試験と同じ扱い）。

### 6.2 Webhookの処理手順（R06・V2-04・D06）

`line_webhook_routes.line_webhook` と `LineOrderService.handle_webhook` を次の形に変える。

```text
署名を検証する（既存）
events が空なら 200 を返す（LINEの接続確認。既存の動きを維持）
for each event:
    begin transaction
      1. LineWebhookEvent を挿入（outcome='processing'）して flush
         → event_id の一意制約違反なら「処理済み」として rollback し、次のイベントへ
      2. source.type が 'user' でなければ outcome='ignored_non_user'
      3. 種類ごとの処理（必要なら §6.1 のロック）→ 返信内容を作る（まだ送らない）
         - 業務上の拒否（回答受付版でない、連携がない、まだ使えない機能など）は「拒否」という結果として記録し、返信を作る
      4. outcome を確定する
    commit
    → 3または commit で予期しない例外（DBエラーなど）が起きたら rollback し、エラーを記録して次のイベントへ（返信しない。このイベントは「再試行が必要」）
    commit が成功したら、返信を送る（失敗は記録するだけ。業務の結果は巻き戻さない）
「再試行が必要」なイベントが1件でもあれば HTTP 500、なければ 200 を返す
```

- **再送の単位**：LINEは再送のときに、処理済みのイベントを含めて送ってくることがあり、順序も変わりうる。処理済みのイベントは、手順1のイベントIDの記録で必ず飛ばす。「失敗したイベントだけが再送される」とは前提にしない。
- **業務上の拒否**は、結果をcommitして返信する。500にしない（同じ内容で何度再送されても、結果は変わらないため）。
- **返信の失敗**は、確定した業務を巻き戻さない。本人が押し直せば、保存済みの結果（「報告済みです」など）が返る。
- イベントIDの一意制約違反**だけ**を「処理済み」とみなす。それ以外の制約違反は、処理の中で明示的に扱う（起床報告の二重押しは、挿入前に存在を確認し、競合した場合も「報告済み」として扱う）。
- 既存の受諾・辞退・紐付けコード・登録キーワードも、この手順に乗せる（返信をcommitの後にする）。
- イベントIDが欠けたイベントには、既存の合成ID（`missing-...`）を使う。
- LINEの再送は到達が保証されないので、500を返したイベントと例外のログの確認手順をRUNBOOKに書く。

---

## 7. A1：LINEの各機能

### 7.1 本人の特定（共通）

1. `source.type == "user"` であること
2. `source.userId` で、有効な `LineWorkerLink` を探す
3. その `worker_id` の `Worker` が `is_active` かつ `deleted_at IS NULL`
- どれかを満たさなければ「連携が確認できません。運営までお問い合わせください」（DEC-064）。

### 7.2 ポストバックの割り当てと有効判定（D01）

| 受信する data | 有効判定に使う親の機能 | 追加の確認 | 段階 |
|---|---|---|---|
| `wk_wake` | `wk_wake` | — | A1 |
| `wk_orders` | `wk_orders` | — | A1 |
| `wk_schedule` | `wk_schedule` | — | A1 |
| `wk_next:<token>` | `wk_schedule` | トークンの action が `schedule_next`、本人、期限、範囲 | A1 |
| `wk_open:<token>` | `wk_orders` | トークンの action が `open_order`、本人、期限、§5.3 の閲覧条件 | A1 |
| `wk_checkin` / `wk_checkout` / `wk_sales` | それぞれ自身 | — | B3 / C1 |
| `or_accept:` / `or_ack:` / `or_decline:` | （対象外。既存の返事の処理） | §5.2・§5.3 の変更 | 既存 |

- 受信した data を解析して**親の機能**を決め、それが最新の `line_rich_menu_releases.enabled_actions` に含まれていなければ「この機能はまだご利用いただけません」と返す。親の機能を無効にすると、子のボタンも使えなくなる。
- トークンそのものは `enabled_actions` に登録しない。
- トークンの action が、受信した data の種類と一致しない場合は拒否する（`schedule_next` のトークンを `wk_open:` で使い回せない）。

### 7.3 依頼書の送付文と受諾の返信（個人の稼働日の明示）

- `send_one()` の `_push_messages` に「あなたの稼働日：…」の行を追加する。`offered_dates` を整形して表示する（連続した日は「11/1〜11/5」とまとめ、抜けている日は「（11/3を除く）」と示す）。整形は共通の関数 `format_date_set()` にする。
- 受諾の返信：「受諾ありがとうございます。よろしくお願い致します。あなたの稼働日：…」。

### 7.4 ①起床報告

1. 本人を特定する（§7.1）。
2. `report_date` ＝ イベントの `timestamp`（ミリ秒）を日本時間に変換した日付。`received_at` との差が30分以上なら `late_received=true`。
3. `wake_reports` に（worker_id, report_date）がすでにあれば、「報告済みです（HH:MM）」と、その日の予定を返す。
4. なければ挿入する。その日の表示対象の予定が**テストの予定だけ**なら `is_test=true` にする（D08）。正式の予定が1件でもあれば、本番の報告として扱う。
   - テストの報告は、運営の起床状況一覧・A2の監視で使わない
   - 同じ人・同じ日にあとから正式の予定ができても、`is_test=true` の報告は本番の報告として数えない（その日の本番の報告は、改めて押してもらう。二重押しの判定は「同じ区分の報告があるか」で行う）。このため一意制約は UNIQUE(worker_id, report_date, is_test) にする
   - 運用では、**検証用の稼働者（実際には稼働しない人）**をLINEと連携して使い、通常の稼働者と混ぜないことを推奨する（§12-C8）
5. 返信：計画書 §7.7 の文面。`report_date` の稼働予定（`active`・`changing`）を開始時刻順にすべて並べる。`changing` には「内容が変更されています。新しい依頼書を確認してください」を添える。予定がなければ「本日の予定は登録されていません。運営へご確認ください」。
6. 監査：`wake_reported`（worker_id・report_date・late_received）。

### 7.5 ⑥スケジュール確認

- 範囲：今日（日本時間）から6日後までの7日間。最初に押した時点で固定する。
- 対象：本人の `active`・`changing` の稼働予定。並び順は（work_date, start_time, id）。
- Flex Messageのカルーセル。1ページ最大10件（カルーセルの上限12件より少なくする）。11件目以降があれば、10件目の後ろに「続きを見る」のカードを置き、`line_action_tokens`（`schedule_next`、範囲と最後の位置）のトークンを渡す。
- 「続きを見る」：トークンを検証し（期限・本人）、最後の位置より後の行を返す。トークンの期限切れは「もう一度スケジュール確認を押してください」。
- 1件のカード：日付（曜日）、開始〜終了（翌日終了なら「翌」）、案件名、稼働場所、集合場所（あれば）、変更確認中の表示。

### 7.6 ⑤受託済みの発注依頼書

- 一覧の対象：本人の稼働予定のうち、今日以降の `active`・`changing` が1件以上ある依頼書。
- 1件ずつ：案件名、稼働期間（本人の参加日の最初と最後）、受諾日時、状態（変更確認中なら「新しい依頼書の確認待ち」）。
- 「依頼書を開く」：`line_action_tokens`（`open_order`）のトークンを渡す。押されたら、依頼書のロックを取り、§5.3 の閲覧条件（`pdf_viewable`）と紐付けの有効性を確認してから、**新しいPDFトークン**（既存の `order_request_file_tokens`、期限7日）を発行し、URLを返信する（D02）。
  - 開けるのは、その人の**適用送付行の版**と、その人が送付先になっている**回答受付版**（未受諾でもよい）
  - 送付先から外れた人・依頼が終了した人には発行しない
- `send_one()` は呼ばない（受諾済みには再送を拒否するため。V3-02）。受諾状態・送信状態は変えない。
- 発行したURLは、今の方式（期限付きの秘密URL）のまま。本人確認をするのは発行の時点（計画書 §7.9）。
- 変更確認中の依頼書は、新しい版と旧い版の両方を開けるようにする（ボタンを2つ）。

### 7.7 当日の起床状況一覧（管理画面）

- API：`GET /api/line-daily/wake-status?date=YYYY-MM-DD`（新しい権限 `wake_status_read`）。
- 1行：稼働者・案件名・開始時刻・状態（active / changing）・起床報告の時刻・遅延受信・同じ時間帯の重複の警告。
- 重複の警告：同じ人の同じ日に、時間帯が重なる `active` の予定が2件以上ある場合。
- `is_test=true` の稼働予定は表示しない（テストの確認は、本人のLINE側で行う）。
- 画面：admin-webに「起床状況」ページを追加し、日付の切り替えと30秒ごとの再取得を持つ（既存の一覧の再取得の作法に合わせる）。
- 新しい権限：`Permission.WAKE_STATUS_READ = "wake_status_read"`。既定では admin と ops に付与する（§12-C4）。

---

## 8. リッチメニュー

- 設定スクリプト：`scripts/line/rich_menu.py`（新規）。
  - `create --stage a1 --image <path>`：段階ごとの定義ファイル（`scripts/line/rich_menu/a1.json`）からメニューを作成し、画像をアップロードする
  - `apply --stage a1`：全員のデフォルトに切り替え、`line_rich_menu_releases` に記録する
  - `status`：現在のデフォルトと記録を表示する
- 定義ファイル：2500×1686（2行×3列）。押せるパネルだけ `areas` を定義する（押せないパネルには領域を作らない。DEC-064）。
- 画像は運営が用意する。画像の寸法とパネルの位置は `docs/ops/` のRUNBOOKに書く。
- チャネルの認証情報は既存の環境変数を使い、スクリプトで表示・保存しない。
- メニューの適用は**A1の公開時**。それまで設定しない。
- LINE側の切り替えと `line_rich_menu_releases` の記録は別のシステムへの更新なので、途中で失敗することがある。`apply` は**LINE側の現在のデフォルトを確認してから記録**し、失敗した場合は再実行で状態を合わせられるようにする（RUNBOOKに手順を書く）。記録が空のまま公開しない

---

## 9. staff-mobileの公開範囲

- 稼働者の役割では、`/today`・`/schedule` を**ナビゲーションから外し、直接URLで開いた場合は「予定は公式LINEで確認してください」の案内ページに切り替える**（`App.tsx` のルートと `MobileShell.tsx` のナビゲーション）。
- APIの `/api/assignments` はそのままにする（Track Bでアサインを生成するまで、稼働者のアサインは存在しない）。
- 運用開始前なので、稼働者にstaff-mobileのアカウントを配っていない可能性がある。配っていないなら、この変更は保険として行う。

---

## 10. 監査

| action | 対象 | 記録する値 |
|---|---|---|
| `order_request_answerable_changed` | 依頼書 | 変更前後の回答受付版ID |
| `delivery_participation_recorded` | 送付行 | seq・source・日数・理由（受諾後の辞退）・実行者 |
| `worker_schedule_entries_rebuilt` | 依頼書×稼働者 | 変更した行ごとの（キー、変更前、変更後、理由）（変更があった場合だけ） |
| `order_request_application_changed` | 依頼書×稼働者 | 適用送付行の変更前後と `ended_reason` |
| `wake_reported` | 稼働者 | report_date・late_received |
| `order_request_file_token_reissued` | 送付行 | 期限（URLは記録しない） |
| `line_rich_menu_applied` | メニュー | stage・enabled_actions・image_sha256 |

LINEのユーザーID・トークンの平文・個人の住所は記録しない（既存の方針）。

---

## 11. 受入試験の一覧

### A0

| # | 内容 |
|---|---|
| A0-1 | 期間に除外日を追加して保存・再読込できる。範囲外・重複・1日ごとの行の除外日は拒否される |
| A0-2 | 除外日で全日がなくなる期間は確定できない |
| A0-3 | 期間を縮めて範囲外になった除外日はエラーになり、自動では消えない |
| A0-4 | 本文・PDFに休業日が表示される。旧データ（除外日なし）はそのまま読め、旧い確定版のPDFは変わらない |
| A0-5 | 単価のカバー確認は、除外日を除いた日について行われる |
| A0-6 | 個人の不参加日を保存できる。実勤務日以外の日、送付先でない人の日は拒否（または取り除かれる） |
| A0-7 | 提示日が0日になる人がいると確定できない |
| A0-8 | 改訂で個人の不参加日が新しい下書きに引き継がれる |
| A0-9 | 個人の不参加日がPDF・本文・他の人に返すAPIに含まれない |

### A1：生成・版・取消

| # | 内容 |
|---|---|
| A1-1 | 正式区分の確定で、送付行ごとに提示日が保存される。Aさんだけ2日目が不参加でも、Bさんの提示日に影響しない |
| A1-2 | テストの依頼書を受諾すると、`is_test=true` の稼働予定ができる（A1-35） |
| A1-3 | 受諾で参加日の状態 seq=1（提示日の全部）ができ、稼働予定が `active` になる |
| A1-4〜10 | 計画書 §7.4 の E1〜E7（新版の確定、未回答で次の版、旧版の取消、draftの取消、回答受付版の取消、受諾後に次の版、送付先から外れる） |
| A1-11 | 回答受付版でない版のボタンで受諾・辞退すると拒否され、案内が返る |
| A1-12 | 運営が受諾後の辞退を記録すると0日の状態が追記され、予定が `cancelled` になる。再構築しても復活しない。同じ記録の再送で状態が重複しない |
| A1-12a | v1受諾 → v2確定（未回答）の人について、運営が受諾後の辞退を記録できる。v1の `changing` の予定が取り消され、v2の未返事の送付行は辞退になり、あとから受諾できない（D03） |
| A1-13 | いったん外れた日が、あとで戻った場合も、同じ行が `active` に戻る（重複行ができない） |
| A1-14 | 同じ元データなら、稼働予定の行が1件もない状態から再構築しても、途中の状態（`changing` など）から再構築しても、同じ結果になる（D04） |
| A1-14a | 適用送付行の参加日が0日になると、`changing` の行も取り消される |
| A1-14b | 一度送付先から外れた人・辞退した人の古い受諾が、再構築で復活しない |
| A1-15 | A1導入前に確定した送付行（提示日がNULL）からは稼働予定ができない |

### A1：同時実行・Webhook（PostgreSQLで実施）

| # | 内容 |
|---|---|
| A1-16 | 受諾と取消が同時に起きても、取消済みの依頼の予定が復活しない |
| A1-17 | 旧版の受諾と新版の確定が同時に起きても、変更確認中への移行が漏れない |
| A1-18 | 同じイベントの同時再送で、二重に記録されない |
| A1-19 | 複数イベントのうち1件が失敗しても、他のイベントは確定し、失敗したものだけが500で再送される |
| A1-20 | commitが失敗したイベントには返信しない。commit後に返信する |
| A1-21 | グループ・複数人トークからのイベントは処理しない |
| A1-21a | 複数イベントの1件目がcommit済み・2件目が失敗 → 処理済みを含むイベント群が再送される → 1件目は重複せず、2件目だけが処理される。業務処理中の例外も同じ（D06） |
| A1-21b | 業務上の拒否（旧い版のボタンなど）は200で応答し、拒否の結果が記録される。空のeventsには200を返す |
| A1-21c | 不正な組み合わせ（別の依頼書の版を指す回答受付版、別の送付行の参加日の状態、他人の送付行を指す適用送付行・稼働予定）をDBが拒否する（D05） |

### A1：LINEの機能

| # | 内容 |
|---|---|
| A1-22 | 起床報告：記録、二重押し、予定なし、複数案件、変更確認中、遅延受信（30分以上） |
| A1-23 | 起床報告：未連携・解除・無効・削除済みの稼働者には「連携が確認できません」 |
| A1-24 | スケジュール確認：本人の分だけ。取消・supersededは出ない。7日間。11件以上で「続きを見る」。同じ日の境界をまたいでも抜け・重複がない。範囲が固定される。期限切れの案内 |
| A1-25 | 受託済み依頼書：一覧は今日以降の予定がある依頼書だけ。PDFトークンを再発行して開ける（元のURLが期限切れでも）。受諾状態・送信状態は変わらない |
| A1-26 | 受託済み依頼書：本人宛ての未受諾の新しい版を開ける。他人宛て・取消済み・送付先から外れた・閲覧停止・紐付け解除では発行しない。他人のトークンを使えない |
| A1-27 | 有効でない機能のポストバックに「まだご利用いただけません」と返す |
| A1-27a | A1の通常の設定で「続きを見る」と「依頼書を開く」が動く。親の機能を無効にすると子のボタンも拒否される。`schedule_next` のトークンを `wk_open:` で使えない（D01） |
| A1-27b | 送付先から外れた人の旧い版への送付（`send_one`）と再発行が拒否される。旧い版の送付と新しい版の確定が同時に起きても、外れた人に有効なリンクが残らない。残った人は適用送付行の旧い版を開ける（D02） |
| A1-28 | 送付文と受諾の返信に「あなたの稼働日」が表示される |

### A1：管理画面・公開範囲・会計

| # | 内容 |
|---|---|
| A1-29 | 起床状況一覧：権限がないとAPI・画面とも拒否。日付の切り替え、重複の警告、変更確認中の表示 |
| A1-30 | staff-mobile：稼働者には予定のナビゲーションがなく、直接URLでは案内ページになる |
| A1-31 | リッチメニューの設定スクリプトで作成・適用・状態確認ができ、記録が残る |
| A1-32 | 既存の締め・請求・支払・アサインの回帰試験が通る（Track Aは金額に触れない） |
| A1-33 | 既存の依頼書のLINE送付・受諾・辞退・催促・紐付けの試験が通る |
| A1-34 | 今日以降の稼働予定がある依頼書は「一覧から外す」が拒否され、取消を案内される。予定がない依頼書は従来どおり外せる |
| A1-35 | テストの依頼書を受諾すると、`is_test` の稼働予定ができ、本人のLINEには「【テスト】」付きで表示される。運営の起床状況一覧・重複の警告には出ない |
| A1-35a | テストの予定だけの日の起床報告は `is_test=true` で記録され、本番の起床状況一覧に出ない。同じ日に正式の予定がある場合は本番の報告になる（D08） |
| A1-36 | 送付状況の表に「閲覧を停止」ボタンがなく、APIも撤去されている。修正版で送付先から外れた人の旧いPDFリンクは開けず、残った人の旧いリンクは開ける |

試験ファイル（案）：`tests/test_order_schedule_exclusions.py`、`tests/test_order_recipient_absences.py`、`tests/test_worker_schedule_rebuild.py`、`tests/test_line_daily_postbacks.py`、`tests/test_line_webhook_transactions.py`、`tests/test_wake_status_api.py`。競合の試験は既存の PostgreSQL 試験の作法に合わせる。

---

## 12. 確認事項（実装前に決めたいこと）

| # | 内容 | 作成者の推奨 | 確認先 |
|---|---|---|---|
| C1 | 発注依頼書の画面の「送付状況」の表にある、送付先ごとの「閲覧を停止」ボタン（`view_revoked`）の扱い | **確定（2026-10-22 ユーザー提案、DEC-068）**：ボタンとAPIを撤去する。依頼書の作成後に必要な操作は「送付先を選んで送付する」だけにする。送付先から外す・やめる場合は修正版または取消で行い、修正版で外れた人の旧いPDFリンクは確定時に自動で無効にする | ユーザー |
| C2 | 「一覧から外す」（`hide_document`）は、確定済みで受諾者がいる依頼書にも使える。外した依頼書の予定はどうするか | **確定（2026-10-22 ユーザー回答）**：今日以降の稼働予定（active・changing）がある依頼書は「外す」を拒否し、先に取消を求める。`hide_document()` に、依頼書のロックを取ったうえでの確認を追加する。受入試験 A1-34 | ユーザー |
| C3 | A1の動作確認をどう行うか | **確定（2026-10-22 ユーザー回答、DEC-063補記）**：テストの依頼書でも稼働予定を作り、`is_test` の印で隔離する。検証用のLINE（公式LINEと連携済み）で、本番の正式データを汚さずに確認する | ユーザー |
| C4 | 新しい権限「起床状況の閲覧」を、既存の独自役割（権限を個別に設定した役割）に自動で付けるか | **確定（2026-10-22 ユーザー回答）**：自動では付けない。既定の ops と admin だけに付け、他は管理者が設定する | ユーザー |
| C5 | 個人不参加日の保存先を、計画書の「request_conditions JSON内」から「専用の列」に変える（§3.2） | 列に変える | レビュアー |
| C6 | `line_action_tokens` の期限30分、PDFトークン7日（既存と同じ） | このまま | レビュアー |
| C8 | テストの確認に使う「検証用のLINE」は、**実際には稼働しない検証用の稼働者**と連携しているか。実際に稼働する人の記録と連携しているなら、テストの起床報告と本番の報告が同じ人に混ざりうる（D08） | **回答（2026-10-22）**：検証用のLINEはユーザー本人のLINE。本人のLINEと連携している稼働者の記録に、実際の稼働の正式な依頼書を送らない限り、検証用の稼働者として扱える（テストと本番の報告は混ざらない）。実際の稼働の依頼を送ることがあれば、別に検証用の稼働者を登録する | ユーザー |
| C7 | DEC-028は「公式LINEで送れるのはテストの依頼書だけ」としていたが、コードは2026-10-06から正式の依頼書も送っている | **確定（2026-10-22 ユーザー回答、DEC-067）**：すべての依頼書（正式・テストとも）を公式LINEで送付する。`line_order.py` の冒頭コメントも実装時に直す | ユーザー |

---

## 13. 作業の順序（案）

1. A0：除外日（日程JSON・展開関数・本文・単価のカバー確認・画面）→ 個人不参加日（列・検証・画面）→ 版Z
2. A1-基盤：マイグレーション → ロック → Webhookの手順の作り直し（既存の受諾・辞退を含む）→ 既存の試験を通す
3. A1-予定：参加日の状態 → 再構築関数 → 確定・取消・受諾・辞退・受諾後の辞退への組み込み → E1〜E7
4. A1-LINE：起床報告 → スケジュール確認 → 受託済み依頼書 → 送付文の「あなたの稼働日」
5. A1-管理画面：起床状況一覧・権限 → staff-mobileの案内ページ → リッチメニューのスクリプトとRUNBOOK
6. 版Y・CHANGELOG・DECISION_LOG（実装の記録）→ デプロイ（AGENTS.md §11）

---

## 14. 参照

- 計画書 v0.9 §5・§7・§9・§10
- DEC-027/028/037/042/044/046/053/056/057/062/063/064/065/066/067/068
- `src/domain/order_schedule.py`、`src/services/order_request_format.py`、`src/services/order_request_service.py`、`src/services/line_order.py`、`src/api/line_webhook_routes.py`、`src/api/order_request_routes.py`、`src/models/order_request.py`、`src/models/line_order.py`、`src/domain/line_registration_locks.py`、`src/services/auth.py`、`src/models/enums.py`
- LINE公式：リッチメニュー、Flex Message（カルーセルの上限）、Webhookの再送

---

## 15. 設計レビュー（v0.2）への対応

レビュー：`docs/ops/LINE_WORKER_DAILY_OPERATIONS_DESIGN_A0_A1_REVIEW_2026-10-22.md`。判定は「A0は実装へ進める。A1はD01〜D04を補正してから」。

| 指摘 | 判断 | 対応 |
|---|---|---|
| D01 子のボタンが常に拒否される | 同意 | §7.2：親の機能への対応表、トークンのactionの照合。試験A1-27a |
| D02 外れた人の旧いリンクが発行経路から漏れる | 同意（`send_one` が回答受付版を確認しないことを確認） | §5.2：`send_one` を回答受付版に限定し、ロックの中で行う。§5.3：発行と読み出しで共通の閲覧条件 `pdf_viewable`。試験A1-27b |
| D03 変更確認中の人の辞退を記録できない | 同意 | §5.2：受諾後の辞退の対象を、回答受付版ではなく**適用送付行**にする。新しい版の未返事の送付行も辞退にする。APIを依頼書×稼働者の単位に変更。試験A1-12a |
| D04 再構築が既存の行の状態に依存している | 同意 | §4.2：適用送付行の表 `order_request_worker_applications` を新設し、ロックの中の出来事だけで更新する。§5.1：元データからあるべき集合を計算し、既存の行と突き合わせる形に全面修正。試験A1-14・14a・14b |
| D05 生成元の組み合わせの保証 | 同意 | §4.1・§4.2：(version, document)、(delivery, version)、(state, delivery)、(applied_delivery, worker / version) の複合FK。CHECK制約。循環FKの作成順序。試験A1-21c |
| D06 再送の単位とHTTPの応答 | 同意 | §6.2：処理済みを含む再送を前提にする。業務上の拒否は200、予期しない例外だけ500。返信の失敗は業務を巻き戻さない。空のeventsは200。試験A1-21a・21b |
| D07 合意日の上限 | 同意 | §4.2：すべての状態の上限は実勤務日。受諾は提示日、承認済みの増加は承認内容と実勤務日が上限 |
| D08 テストの起床報告の隔離 | 同意 | §7.4：`wake_reports.is_test`、一意制約に区分を含める。検証用の稼働者を使う運用を推奨（§12-C8）。試験A1-35a |
| C5（個人不参加日の列） | 賛成を受領 | §3.2のまま |
| C6（トークンの期限） | 採用を受領。期限だけで認可を代替しない | §7.2・§5.3 で操作ごとに本人・action・状態を照合 |
| 低：リッチメニューの適用の失敗 | 同意 | §8：LINE側を確認してから記録、再実行で合わせる |
| 低：監査を件数だけにしない | 同意 | §10：変更した行ごとの記録、適用送付行の変更の記録 |
| 低：参照のそろえ | 同意 | DEC-067/068を§14に追加 |

---

## 16. 実装メモ（0.47.0）

設計から変えた点・補った点。

| # | 内容 | 理由 |
|---|---|---|
| I-01 | 回答受付版・適用送付行・ロックを系列単位にした（§4.4） | 「変更を作成」の二重予定を防ぐ（ユーザー指示） |
| I-02 | 既存の受諾済み送付行から適用送付行を埋め込まない | A1以前の送付行は提示日が NULL で稼働予定の対象外のため、埋めても予定は作られない |
| I-03 | 受諾後の辞退の記録は、文書×稼働者のAPI（`POST /api/order-requests/documents/{document_id}/workers/{worker_id}/withdraw-acceptance`、理由必須、発注依頼書の編集権限）。参加日0日の状態を追記し、確認待ちの新しい版の送付行は「運営記録：理由」で辞退にする。2回目は記録しない | §5.2 の手順のとおり。画面は送付状況の表の「受諾後の辞退を記録」 |
| I-04 | 起床状況の「重複の警告」は、同じ人の予定の時間が重なるときだけ出す | 1日に2つの稼働は正当（ユーザー回答） |
| I-05 | staff-mobile の「今日」「予定」をメニューから外し、旧URLは「予定は公式LINEで確認してください」の案内を出す。最初の画面は「事前予定」 | §9。旧画面の出勤・退勤ボタンも使えなくなる（出勤・退勤はLINEの②③で後日） |
| I-06 | リッチメニューは `scripts/line/rich_menu.py`（status / check / apply）と `scripts/line/rich_menu/a1.json`。2500×1686 の6分割で、上段①②③・下段④⑤⑥を想定し、①⑤⑥だけに押せる範囲を定義 | 画像の配置が違う場合は a1.json の座標を直す |
| I-07 | 権限 `wake_status_read`（起床状況：閲覧）。運用担当に既定で付与。役割の権限を個別に保存済みの場合は、ID・権限管理で追加が必要 | C4 |
| I-08 | マイグレーションはローカルの PostgreSQL 16 で、試験データを入れた状態から upgrade → downgrade → upgrade を確認。行ロック（FOR UPDATE）の同時実行試験は未実施（この作業環境にPostgreSQLの接続ドライバがないため） | 本番反映後の確認事項 |

