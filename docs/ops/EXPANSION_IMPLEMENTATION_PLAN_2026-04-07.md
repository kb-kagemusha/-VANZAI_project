# VANZAI 追加要件 実装計画書

更新日: 2026-04-07

## 1. 目的
Kintone で先行運用している追加機能を、既存の FastAPI + PostgreSQL + admin-web + staff-mobile に段階導入し、Kintone 依存を減らしながら Web 側を正本へ近づける。

今回の対象は、単なるマスタ追加ではない。公開登録フォーム、管理者通知、スタッフ実績報告、案件種別ごとの資料、案件タスク、簡易 PL、個人成績まで含むため、ドメイン整理から順に導入する。

## 2. 対象範囲

### 2.1 今回の計画対象
- クライアント情報
- クライアント職員
- VANZAI 契約: マネージャー / 事務 / 全体統括管理者
- 下請け / 紹介者
- スタッフ
- 現場登録
- スタッフ登録
- 案件種別（単価、場所、種別など）
- 請求書
- 支払明細書（スタッフ / マネージャー向け）
- 公開登録フォーム 4 種
- 管理画面の「お知らせ」
- 出退勤打刻
- 販売台数報告
- 案件種別ごとの説明資料
- 案件ごとのタスク進捗
- 簡易 PL
- 個人成績表

### 2.2 今回の前提決定
- Supplier の区分は追加し、Phase 1 は supplier 自体の単一属性として扱う
- Worker の銀行口座管理は Phase 1 で追加する
- Project と VANZAI 職員の紐付けとして `projects.vanzai_manager_id` を追加する
- 公開登録フォームは 4 URL に分ける
- 公開登録フォームはログイン不要だが、個別 token + 4 桁 PIN 付き URL で公開する
- 出退勤は staff-mobile 内に実装する
- 簡易 PL は月次 + 案件種別ごとに集計する

## 3. 背景
既存システムには、認証、案件、シフト枠、アサイン、実績、請求、支払、締め、監査、経費、通知、スタッフモバイルの基盤がすでに存在する。

そのため、今回の主作業は全面再構築ではない。Kintone で別管理している追加情報と運用導線を、既存基盤へ正しく接続し、データモデルと画面導線を揃えることにある。

## 4. 追加要件の整理

### 4.1 スタッフ登録で回収する追加情報
- ふりがな
- 個人事業主屋号
- 振込先
- 振込口座（銀行名）
- 振込口座（支店名）
- 振込口座（支店番号）
- 振込口座（口座種別）
- 振込口座（口座番号 7 桁）
- 振込口座（名義）
- 緊急連絡先氏名（カナ）
- 緊急連絡先
- 性別
- インボイス取得状況
- インボイス番号

### 4.2 公開登録フォーム
- ① 稼働者の情報登録回収フォーム
- ② 個人（紹介者 + 下請け）の情報登録回収フォーム
- ③ 法人（下請け）の情報登録フォーム
- ④ 下請けからの紹介者の身分証回収フォーム

### 4.3 採用フロー分岐
- VANZAI 直契約: ①のみ回収
- 下請け経由: ②または③を回収後、採用者ごとに④を回収
- 紹介者経由: ②を回収後、採用者ごとに①を回収

### 4.4 スタッフ運用追加
- Web アプリからの出勤 / 退勤打刻
- 販売台数報告

### 4.5 案件運用追加
- 案件種別ごとの説明資料添付
- 案件ごとの必要タスク管理
- タスクの担当区分（クライアント側 / 管理側）

### 4.6 分析追加
- 簡易 PL 表
- 個人成績表

## 5. 全体方針
1. 既存 API / DB / React 資産を再利用し、追加分だけを積む
2. まずデータモデルと受付導線を固め、次に管理画面、最後に分析と高度化へ進む
3. 正本は 3 層で分離する
   - request 系: 外部入力の受付記録
   - master 系: 承認後の業務用現在値
   - payout / invoice / report 系: 月次・帳票・集計のスナップショットまたは集計結果
4. 管理者の未処理確認は dashboard の「お知らせ」へ集約する
5. 身分証ファイルや振込情報は通常マスタより高い権限制御を前提に扱う
6. 売上 / 原価 / 実績 / インセンティブは既存 invoice / payout / actual / incentive を活かして集計する
7. migration 着手前に、承認反映、支払先モデル、銀行口座履歴、分析指標定義、公開リンク運用を設計凍結する

## 5.1 正本の定義

### 5.1.1 受付正本
- `registration_requests` 系は不変の受付記録とする
- 送信内容、提出時点の端末情報、提出者導線、差し戻し / 却下理由を保持する
- 受付レコード自体を業務用現在値として直接参照しない

### 5.1.2 業務正本
- `workers`, `suppliers`, `clients`, `projects`, `vanzai_staff` などは承認後の現在値を保持する
- request 承認時はこの層へ INSERT / UPDATE / 関連付けを行う

### 5.1.3 帳票・集計正本
- 請求・支払・PL・個人成績は現在値参照だけでなく、必要箇所でスナップショットまたは確定済データを参照する
- 特に payout は受取人名・口座・税区分をスナップショット化する

## 6. 実装フェーズ

### 6.0 Phase 0: migration 前の設計凍結
目的は、中盤で schema と運用フローをやり直さないための前提確定。

#### Phase 0-1. 銀行口座履歴モデルの確定
- `workers` への直置きではなく、`worker_bank_accounts` を新設する
- 想定カラム
  - `worker_id`
  - `bank_name`
  - `branch_name`
  - `branch_code`
  - `account_type`
  - `account_number`
  - `account_holder_kana`
  - `transfer_destination_name`
  - `effective_from`
  - `effective_until`
  - `is_primary`
- 支払時は有効期間に基づく口座を参照し、帳票側には口座スナップショットを保存する
- supplier にも継続支払が発生し、過去支払の口座再現性も必須とする
- Phase 1 は `supplier_bank_accounts` を追加して worker とは別管理にする
- `recipient_bank_accounts` への統合は将来拡張として扱い、Phase 1 では行わない

#### Phase 0-2. request 承認反映ルールの確定
- request は不変記録とする
- approve 時に何をするかを先に固定する
  - 新規 worker / supplier 作成
  - 既存 master への差分反映
  - 重複時のマージ確認
  - 関連 request の supersede 処理
- request 共通ヘッダ + 種別別詳細テーブルの構造を採用する
- `dedupe_key` の実体を request 種別ごとに定義する
  - worker 候補: 電話番号、氏名 + ふりがな
  - supplier 候補: 法人名 / 屋号、電話番号
- 自動 dedupe は補助に留め、重複候補時は承認画面で差分確認 UI を出す前提にする
- approve / reject の冪等性と排他をここで確定する
  - status 更新と master 反映は 1 transaction で行う
  - 承認対象 request は `submitted` / `reviewed` のみを処理対象とする
  - approve 済み request への再 approve は `409 Conflict` を返し、「別の管理者が承認済み」と表示する
  - 差し戻し直後や二重クリック時も master 反映が重複しないよう、行ロックまたは同等の排他制御を前提にする

#### Phase 0-3. 支払先モデルの確定
- payout は staff / supplier / vanzai_staff を共通に扱えるようにする
- Phase 1 で `recipient_type`, `recipient_id`, `payee_name_snapshot`, `bank_account_snapshot_json`, `tax_treatment_snapshot_json` を追加する
- 既存 payout は migration で以下を backfill する
  - `worker_id IS NOT NULL` の既存行は `recipient_type='worker'`, `recipient_id=worker_id`
  - `supplier_id IS NOT NULL` の既存行は `recipient_type='supplier'`, `recipient_id=supplier_id`
- `worker_id` / `supplier_id` は移行期間中の後方互換列として残し、worker / supplier 向け新規作成時は recipient 系と同期する
- `vanzai_staff` 向け payout は `recipient_type='vanzai_staff'` を使い、legacy 列は NULL のまま扱う
- API / UI / 帳票の正本は `recipient_type` / `recipient_id` に切り替え、legacy 列は全利用箇所の移行完了後に廃止候補とする
- snapshot JSON は JSONB とし、検索要件は recipient 本体側で持つ前提にする

#### Phase 0-4. VANZAI 職員と認証ユーザーの関係整理
- `vanzai_staff` は業務上の人マスタとして持ち、認証主体は既存どおり `users` を正本とする
- 既存 `users.worker_id` の方針に合わせ、`users.vanzai_staff_id` を nullable FK として追加する
- `vanzai_staff` 側に `user_id` は持たず、認証情報と人マスタの参照方向を users 側へ統一する
- `users.worker_id` と `users.vanzai_staff_id` は同時設定不可とし、system / integration 用アカウントのみ両方 NULL を許容する
- admin-web にログインする実ユーザーと、案件担当者としての VANZAI 職員を分離可能にする
- Phase 1 は `vanzai_manager_id` の単一 FK で進めるが、将来 role 付き中間テーブルへ拡張する前提で命名と UI を固定する
- 権限制御や担当案件絞り込みで VANZAI 職員文脈が必要な場合は `current_user.vanzai_staff_id` を参照する

#### Phase 0-5. 分析指標定義の確定
- PL と個人成績の集計定義を migration 前に確定する
- 確定売上、見込売上、確定原価、見込原価、遅刻回数、販売台数の算出元を文書化する
- 簡易 PL は「確定値」と「締めまでの予測値」を並列表示する
- 確定値は以下を正本にする
  - 売上: 発行済み最新版 invoice / invoice_lines
  - 原価: 確定済み最新版 payout / payout_lines
  - 経費: 承認済み expenses
  - インセンティブ原価: 承認済み incentives
- 見込値は Assignment ベースの予定売上 / 予定原価を使う
- 個人成績の遅刻は assignment / shift 開始時刻から 15 分超過で 1 回と数える
- `sales_reports` の最新版判定を確定する
  - 集計正本は `superseded_by_id IS NULL AND status='approved'`
  - 訂正申請中の新 revision は旧 approved 行を即時 supersede しない
  - 訂正承認 transaction の中でのみ旧 approved 行へ `superseded_by_id` を設定する
  - `revision_no` は監査・表示順序用とし、最新版判定の主条件には使わない

#### Phase 0-6. 公開リンク・ファイル運用の確定
- token は公開リンク単位で発行し、1 URL は 1 受付導線にのみ使う
- 有効期限は初回発行から 7 日を基本とする
- PIN は 5 回失敗でロックする
- PIN ロック後は管理者が same URL のロック解除、または新 URL 再発行のどちらも実行可能にする
- 送信後の再閲覧 / 再提出可否
- 身分証ファイルは承認 / 却下後 180 日保持し、accounting を削除責任者とする
- 閲覧理由ログは必須にする
- 身分証ファイルの技術制御もここで確定する
  - 保存時暗号化
  - 認可 API または署名付き一時 URL 経由のみでダウンロード
  - MIME / 拡張子の二重検証
  - ウイルススキャン
  - 画像 / PDF の正規化方針
  - バックアップ上の保持 / 削除連動

#### Phase 0-7. project_types 3 階層化の影響調査
- 既存の project_type 参照箇所を洗い出す
- リーフのみ参照する画面 / 親含みで集計する画面を区別する
- 案件が直接選択できるのは leaf（minor）のみとする
- 既存の flat な project_type は migration で major として移行し、各 major 直下に選択用の minor を新設する
- 既存 projects.project_type_id は新設 minor 側へ backfill する前提で移行計画を組む
- 自動生成する minor の表示名は `major名 + （標準）` とする
- 自動生成する minor の code は `既存 major code + -DEFAULT` とする

#### Phase 0-8. Supplier 役割の所属先確定
- 現時点では `supplier_type` を supplier 自体の属性として固定する
- 同一 supplier が案件ごとに「紹介者でもあり下請けでもある」運用は現時点では想定しない
- 将来運用変更が出た場合のみ、`project_suppliers` または同等の関係テーブルへ拡張する

#### Phase 0-9. DB 制約・index 方針の確定
- `worker_bank_accounts`
  - 同一 worker で有効期間が重複しない制約
  - active な `is_primary=true` が複数立たない制約
- `sales_reports`
  - `1 worker × 1 assignment × 1 report_date × approved current revision` の一意性
  - `1 worker × 1 assignment × 1 report_date × pending correction` の多重化防止
  - superseded 済み旧版が集計対象に入らない条件
- `registration_requests`
  - `public_token_hash` 一意
  - `approved_target_*` と status の整合
- `project_types`
  - 親子循環禁止
- 各テーブルの主要検索列に index を付与する方針をここで固定する
- Phase 1 では上記制約を厳しめに入れる前提で進める

### 6.1 Phase 1: データモデル拡張
目的は、公開登録フォームと追加業務を支える正本データ構造を先に作ること。

#### Phase 1-1. 既存テーブル拡張
- `workers`
  - `furigana`
  - `sole_proprietor_name`
  - `emergency_contact_name_kana`
  - `emergency_contact_phone`
  - `gender`
  - `invoice_registration_status`
  - `invoice_number`
- `clients`
  - `billing_email`
- `suppliers`
  - `supplier_type` (`introducer` / `subcontractor`)
  - `entity_type` (`individual` / `corporation`)
- `projects`
  - `vanzai_manager_id` → `vanzai_staff.id`
- `users`
  - `vanzai_staff_id` → `vanzai_staff.id`
  - `worker_id` と `vanzai_staff_id` の排他制約

#### Phase 1-2. 新規マスタテーブル
- `worker_bank_accounts`
  - `worker_id`, `bank_name`, `branch_name`, `branch_code`, `account_type`, `account_number`, `account_holder_kana`, `transfer_destination_name`, `effective_from`, `effective_until`, `is_primary`
- `client_staff`
  - `client_id`, `name`, `role`, `phone`, `email`, `is_active`, `notes`
- `vanzai_staff`
  - `name`, `role`, `phone`, `email`, `is_active`, `notes`
- `project_types` 拡張
  - `category_level` (`major` / `middle` / `minor`)
  - `parent_id`

#### Phase 1-3. 公開フォーム受付テーブル
- `registration_requests`
  - `request_type`
  - `status` (`draft` / `submitted` / `reviewed` / `approved` / `rejected` / `superseded`)
  - `public_token_hash`
  - `access_pin_hash`
  - `expires_at`
  - `failed_attempts`
  - `locked_at`
  - `submitted_at`
  - `reviewed_at`
  - `reviewed_by`
  - `source_type` (`public_form` / `admin_proxy` / `api_import` / `internal_create`)
  - `dedupe_key`
  - `approved_target_type`
  - `approved_target_id`
  - `superseded_by_request_id`
  - `submitted_ip`
  - `user_agent`
  - `notes`
- `worker_registration_request_details`
- `supplier_individual_request_details`
- `supplier_corporation_request_details`
- `introducer_identity_request_details`
- `registration_request_files`
  - `document_type`
  - `document_part`
  - `original_filename`
  - `storage_key`
  - `sha256`
  - `mime_type`
  - `size_bytes`
  - `scan_status`
  - `uploaded_at`
  - `delete_after`
  - `deleted_at`

detail テーブルは Google Form 相当の入力原文を保持し、承認時に master へ正規化する。
- `worker_registration_request_details`
  - `last_name`, `first_name`, `last_name_furigana`, `first_name_furigana`
  - `sole_proprietor_name`, `gender`, `route_group`, `introducer_supplier_name_raw`
  - `email`, `phone`, `zipcode`, `prefecture`, `city_address`, `building_address`
  - `emergency_contact_name_kana`, `emergency_contact_phone`
  - `bank_name`, `bank_branch`, `bank_branch_number`, `bank_account_type`, `bank_account_number`, `bank_account_holder`
  - `invoice_registration_status`, `invoice_registration_number`, `memo`
- `supplier_individual_request_details`
  - `supplier_type`, `name`, `name_furigana`, `trade_name`
  - `email`, `phone`, `zipcode`, `prefecture`, `city_address`, `building_address`
  - `bank_name`, `bank_branch`, `bank_branch_number`, `bank_account_type`, `bank_account_number`, `bank_account_holder_kana`
  - `invoice_registration_status`, `invoice_registration_number`, `memo`
- `supplier_corporation_request_details`
  - `supplier_type`, `company_name`, `company_name_furigana`
  - `representative_name`, `representative_name_furigana`
  - `email`, `phone`, `zipcode`, `prefecture`, `city_address`, `building_address`
  - `bank_name`, `bank_branch`, `bank_branch_number`, `bank_account_type`, `bank_account_number`, `bank_account_holder_kana`
  - `invoice_registration_status`, `invoice_registration_number`, `memo`
- `introducer_identity_request_details`
  - `related_worker_request_id`, `related_supplier_request_id`
  - `subject_name`, `subject_name_furigana`, `submission_reason`, `memo`

`source_type` の意味は以下で固定する。
- `public_form`: token + PIN 付き公開 URL から本人または外部関係者が送信した受付
- `admin_proxy`: 管理者が電話 / メール / 紙資料の内容を代行入力した受付
- `api_import`: Kintone 連携、CSV 取込、外部 API 連携などで生成した受付
- `internal_create`: 認証済み内部ユーザーが admin-web 上で承認フロー対象として作成した受付

直接 master を CRUD する管理操作は `registration_requests` を経由しない。承認フローを通したい作成だけを request 化する。

`registration_request_files.document_type` は以下で開始する。
- `driver_license`
- `my_number_card`
- `residence_card`
- `passport`
- `other`

同一書類の表裏を扱うため、`document_part` は `front` / `back` / `single` を持つ。

#### Phase 1-4. 案件運用・分析テーブル
- `project_type_documents`
- `task_templates`
- `project_tasks`
  - `title`, `owner_side`, `assignee_type`, `assignee_id`, `due_date`, `status`, `completed_at`
  - optional: `evidence_file`, `blocked_reason`
- `sales_reports`
  - `worker_id`, `assignment_id`, `project_id`, `report_date`, `units_sold`, `status`, `approved_by`, `approved_at`, `revision_no`, `replaces_report_id`, `superseded_by_id`, `correction_reason`
  - 粒度は「1 worker × 1 assignment × 1 report_date」を基本とする
  - 訂正は immutable + 再提出方式を基本とし、承認済みレコードを直接上書きしない

#### Phase 1-5. 支払・集計用スナップショット拡張
- `payouts` 拡張
  - `recipient_type`
  - `recipient_id`
  - `payee_name_snapshot`
  - `bank_account_snapshot_json`
  - `tax_treatment_snapshot_json`
- 必要に応じて invoice / payout の集計対象期間と version 最新判定ルールを明文化する

### 6.2 Phase 2: バックエンド API
目的は、新しいデータモデルを管理画面と公開フォームから安全に使えるようにすること。

#### Phase 2-1. マスタ系 API
- `GET /api/client-staff`
- `POST /api/client-staff`
- `PUT /api/client-staff/{id}`
- `DELETE /api/client-staff/{id}`
- `GET /api/vanzai-staff`
- `POST /api/vanzai-staff`
- `PUT /api/vanzai-staff/{id}`
- `DELETE /api/vanzai-staff/{id}`
- `GET /api/project-types/tree`
- 既存 `/api/workers`, `/api/clients`, `/api/suppliers`, `/api/projects` の拡張

#### Phase 2-2. 公開フォーム API
- `GET /public/registrations/{form_type}`
  - トークン + PIN 検証
- `POST /public/registrations/worker`
- `POST /public/registrations/supplier-individual`
- `POST /public/registrations/supplier-corporation`
- `POST /public/registrations/introducer-identity`

#### Phase 2-2a. 公開リンク運用 API
- `POST /api/registration-links`
- `POST /api/registration-links/{id}/reset-pin-lock`
- `POST /api/registration-links/{id}/reissue`

#### Phase 2-3. 管理者確認 API
- `GET /api/registration-requests`
- `GET /api/registration-requests/{id}`
- `POST /api/registration-requests/{id}/approve`
- `POST /api/registration-requests/{id}/reject`

approve 時の基本動作を固定する。
- request は更新せず状態遷移のみ行う
- `approved_target_type` / `approved_target_id` を記録する
- 重複候補がある場合は自動承認しない
- 差し戻し / 再提出時は新 request を起こし、旧 request は superseded 扱いにする
- 承認画面では、重複候補との差分確認 UI を持つ前提にする
- approve / reject は transaction 内で実施し、二重実行は 409 または no-op に統一する

#### Phase 2-4. ファイルアップロード API
- 身分証アップロード対応
- MIME 制限
- サイズ制限
- 管理者のみダウンロード可能
- 保存期間と削除ポリシーを API / 運用の両方で管理する
- 閲覧理由ログ、ダウンロード監査、再提出時の差し替え管理を行う

#### Phase 2-5. 通知 API
- dashboard summary 拡張、または `GET /api/admin-notices`
- 公開登録 request 未審査、未確認身分証、sales_reports 未承認、期限超過 project_tasks、payout 作成 / 送信エラーを返す
- 単なる件数 summary ではなく、未処理キューの入口として設計する
  - `severity`
  - `assigned_role`
  - `created_at`
  - `stale_days`
  - `target_url`
  - `is_read`
  - `is_resolved`

#### Phase 2-6. スタッフ実績 API
- 既存 check-in/check-out API を staff-mobile へ接続
- `GET /api/sales-reports`
- `POST /api/sales-reports`

#### Phase 2-7. 分析 API
- `GET /api/reports/pl`
- `GET /api/reports/worker-performance`

分析 API の前提定義を以下で固定する。
- 確定売上: 最新版かつ発行済み invoice / invoice_lines
- 確定原価: 最新版かつ確定済み payout / payout_lines
- 経費: 承認済み expenses
- インセンティブ原価: 承認済み incentives
- 見込値: Assignment ベースの予定売上 / 予定原価
- 個人成績の販売台数は承認済み sales_reports を正本とする
- 遅刻回数は shift / assignment 開始時刻との差分で算定し、15 分超過で 1 回とする

### 6.3 Phase 3: admin-web 実装
目的は、管理者が Kintone なしで追加業務を処理できる状態にすること。

#### 追加ページ
- `/masters/clients`
- `/masters/vanzai-staff`
- `/operations/registration-requests`
- `/reports/pl`
- `/reports/worker-performance`

#### 既存ページ拡張
- DashboardPage
  - 「お知らせ」欄追加
  - 例: 「3件の新規スタッフ登録があります」
- WorkersPage
  - 追加項目表示・編集
- InvoicesPage
  - クライアント責任者・件名・帳票導線整理
- PayoutsPage
  - スタッフ / 紹介者 / VANZAI 職員の対象種別対応
- ProjectType 管理
  - 3 階層ツリー表示
  - 資料添付対応
- 案件詳細 / タスク管理
  - 必要タスクと担当区分の確認

### 6.4 Phase 4: 公開フォーム画面
目的は、Google フォーム 4 本を独立ページへ置き換えること。

#### 公開 URL
- `/register/worker`
- `/register/supplier-individual`
- `/register/supplier-corporation`
- `/register/introducer-identity`

#### 画面フロー
1. PIN 入力
2. フォーム入力
3. 確認画面
4. 送信完了

確認画面では送信前に全項目を一覧表示し、内容確認後にのみ送信できるようにする。

公開フォーム運用は以下を前提にする。
- URL は token 付き個別リンクで発行する
- URL の有効期限は初回発行から 7 日とする
- PIN は 5 回失敗でロックする
- PIN ロック時は管理者が same URL を reset するか、新 URL を再発行する
- 送信後は原則 read-only とする
- 差し戻し後の再提出は既存 request を直接編集せず、新 request を作成する

### 6.5 Phase 5: staff-mobile 実装
目的は、現場運用に必要な出退勤と販売報告を staff-mobile に寄せること。

#### 追加機能
- TodayAssignmentsPage または ActualsPage に出勤 / 退勤導線追加
- assignment 単位の打刻状態表示
- 販売台数報告画面追加
- 必要に応じて notices 連携
- 締め済み期間の sales_reports は修正不可、訂正は再提出 + 再承認で扱う

### 6.6 Phase 6: 分析・運用高度化
目的は、月次運用と評価に使える集計を揃えること。

#### 簡易 PL
- 月次
- 案件種別ごと
- 売上、支払、経費、インセンティブ、粗利

#### 個人成績表
- 販売台数
- 出勤日数
- 遅刻回数
- インセンティブ額

## 6.7 Phase 7: 支払先拡張の UI/運用反映
目的は、staff / supplier / vanzai_staff を同一支払導線で扱えるようにすること。

- PayoutsPage のフィルタ、明細、PDF 導線を recipient_type ベースへ移行する
- 受取人名、口座、税区分は payout 生成時点で固定する
- 銀行口座の現在値変更が過去支払へ影響しないことを保証する
- supplier 口座は `supplier_bank_accounts` の有効口座から解決する

## 7. データモデル方針

### 7.1 Worker
Worker は単なる稼働者マスタではなく、採用後の支払・緊急連絡・インボイス管理まで持つ。

### 7.1.1 銀行口座
銀行口座は `workers` へ直置きしない。`worker_bank_accounts` で履歴管理し、支払時に有効な口座を解決する。

supplier も同様に `supplier_bank_accounts` で履歴管理する。Phase 1 は worker / supplier を別テーブルで持ち、recipient 共通化は将来課題とする。

### 7.2 Supplier
Supplier は「紹介者 / 下請け」と「個人 / 法人」の 2 軸を持つ。notes への埋め込みではなく、明示カラムで扱う。

Phase 1 では `supplier_type` を supplier 自体の属性として扱う。将来、案件ごとに role が変わる運用が発生した場合のみ、案件との関係に role を持つモデルへ拡張する。

### 7.3 Project と VANZAI 職員
案件の VANZAI 側責任者は `projects.vanzai_manager_id` を正本とする。既存の `primary_manager_id` / `secondary_manager_id` は workers ベースの現場管理用途として残す可能性があるため、役割を明確に分ける。

Phase 1 は単一責任者 FK で進めるが、将来 role 付き中間テーブルへ拡張可能な前提で進める。

### 7.3.1 VANZAI 職員と認証の関係
`vanzai_staff` は業務上の人マスタとし、必要な場合のみ `users.vanzai_staff_id` で紐付ける。全 VANZAI 職員がログイン主体である前提にはしない。

既存 `users.worker_id` と同じ方向に揃えるため、認証 FK は users 側に集約する。1 ユーザーが worker と vanzai_staff を同時に指す構成は Phase 1 では許容しない。

### 7.4 公開フォームの正本
公開フォームの送信結果は request 系テーブルに保持するが、それは受付記録の正本である。承認後の業務現在値は worker / supplier などの master に反映する。

### 7.4.1 request 反映ルール
- request は不変
- 承認時に master を create / update / merge する
- 差し戻し・再提出は新 request を発行する
- どの request がどの master に反映されたかを `approved_target_*` で追跡する
- `source_type` は request 作成起点を表し、フォーム種別を表す `request_type` とは分ける
- `source_type` は `public_form` / `admin_proxy` / `api_import` / `internal_create` のみを許容する
- 承認フロー対象ではない通常の master CRUD は request を生成しない

### 7.5 支払先とスナップショット
支払先は worker / supplier / vanzai_staff のいずれでも扱えるようにする。帳票と振込の再現性のため、受取人名、口座、税区分は payout 作成時に固定値として保存する。

既存 payout は `worker_id` / `supplier_id` から `recipient_type` / `recipient_id` へ backfill する。移行期間中は legacy 列を互換目的で残すが、API と帳票の正本は recipient 系へ寄せる。

### 7.6 sales_reports の粒度
販売台数報告は `1 worker × 1 assignment × 1 report_date` を基本粒度とし、承認済み値のみ個人成績とインセンティブ計算の正本とする。

承認後の訂正は、既存レコード更新ではなく supersede 付き再提出で扱う。

最新版は `superseded_by_id IS NULL AND status='approved'` を正本条件とする。

訂正申請中は旧 approved 版を現行正本のまま維持し、新 revision の承認 transaction でのみ旧版を supersede する。`replaces_report_id` はどの approved 版を置き換える申請かを示す。

### 7.7 project_tasks の考え方
案件タスクは `task_templates` を project_type ごとに持ち、案件ごとに `project_tasks` を展開する。完全手入力だけにはしない。

`project_tasks` は ToDo 札ではなく、担当・期限・証跡・ブロッカーを持つ運用実体として扱う。

### 7.8 分析定義
PL と個人成績は画面要件ではなく算定定義を先に固定する。特に、確定値と見込値の区別、遅刻閾値、販売台数の承認要件を migration 前に決める。

簡易 PL は確定値と予測値の 2 系統を出す。確定値は invoice / payout / expenses / incentives の承認・発行済みデータを正本とし、予測値は Assignment ベースの予定売上 / 予定原価を使う。

個人成績の遅刻は開始時刻から 15 分超過で 1 回とする。

admin-notices は単なる集計箱ではなく、未処理キューとして扱う。Phase 1-2 の対象は公開登録 request 未審査、未確認身分証、sales_reports 未承認、期限超過 project_tasks、payout 作成 / 送信エラーとする。

### 7.9 主要 DB 拘束の方針
重要な整合性はアプリ実装だけに依存させず、DB 制約でも担保する。

- `worker_bank_accounts`: 有効期間重複禁止、primary 重複禁止
- `sales_reports`: approved current revision 一意性担保、pending correction 多重化防止
- `registration_requests`: token 一意、承認整合性担保
- `users`: `worker_id` と `vanzai_staff_id` の同時設定禁止
- `payouts`: recipient 系と legacy 列の整合性担保
- `project_types`: 循環禁止
- 各主要一覧 API で使う列に index を張る

## 8. セキュリティ方針
1. 公開フォームはトークン + 4 桁 PIN + 有効期限で保護する
2. PIN 試行回数制限を設ける
3. PIN ロック時の reset / 再発行手順を定義する
4. 身分証ファイルは保存先を分離し、保持期間と削除ポリシーを持つ
5. 身分証ファイルは保存時暗号化し、本番 DB にバイナリを直保存しない
6. 身分証ファイルの閲覧・ダウンロードは admin / ops のみに制限し、認可 API または署名付き一時 URL のみで扱う
7. ファイルは MIME / 拡張子二重検証、ウイルススキャン、必要に応じた正規化を通す
8. 振込口座情報は一覧上でマスキング表示する
9. 閲覧・承認・ダウンロードは監査ログへ残す
10. token は個別発行し、固定 4 URL をそのまま公開しない

## 9. 受入基準
1. Alembic migration により、追加カラム / 追加テーブルが既存データを壊さず作成される
2. `worker_bank_accounts` により口座履歴を保持でき、過去支払の再現性が壊れない
3. request 承認時に master 反映と `approved_target_*` 記録が行われ、重複時は自動反映されない
4. 公開フォーム 4 本が、PIN 認証、入力、確認画面、送信完了、ロック時の再発行または reset まで動作する
5. payout が recipient_type ベースで staff / supplier / vanzai_staff を扱え、受取人スナップショットを保持する
6. 管理画面 dashboard に「お知らせ」が表示され、未処理件数から詳細へ遷移できる
7. 管理画面で client_staff、vanzai_staff、拡張 worker / supplier / project_type を CRUD できる
8. staff-mobile から出勤 / 退勤ができ、既存 Actual に反映される
9. staff-mobile から販売台数を報告できる
10. 案件種別ごとの資料添付と案件タスク管理ができる
11. 月次 + 案件種別別の簡易 PL が表示できる
12. 個人成績表に販売台数、出勤日数、遅刻回数、インセンティブ額が表示できる
13. 振込情報と身分証ファイルが権限外ユーザーに見えない

## 10. リスクと注意点
1. 4 桁 PIN は弱いため、公開トークンや期限切れと組み合わせないと危険
2. 身分証ファイルは個人情報リスクが高いため、保存先・権限・監査に加えて保持期間と削除責任を最優先で固める必要がある
3. PL は正本の定義が曖昧だと後で数値がずれる
4. Project の `vanzai_manager_id` と既存 manager 系カラムの責務が曖昧だと UI と権限制御が崩れる
5. request から master への承認反映が曖昧だと二重登録や未反映が起こる
6. payout recipient モデルを先送りすると、支払明細と振込処理を後で大きく組み替えることになる
7. project_types の 3 階層化は既存参照箇所への影響が大きく、先に影響調査が必要
8. supplier の役割が相手属性ではなく案件関係属性だった場合、`supplier_type` 単一値では破綻する
9. `registration_request_files` に用途区分がないと、管理者確認時に書類判別が困難になる
10. sales_reports の訂正運用が曖昧だと、個人成績とインセンティブが不安定になる

## 11. 実装順の推奨
1. Phase 0: 設計凍結
2. Phase 1: モデル / migration
3. Phase 2-1 から 2-4: API とファイル保存
4. Phase 3: 管理画面の未処理確認導線
5. Phase 4: 公開フォーム
6. Phase 5: staff-mobile
7. Phase 6-7: 分析画面と支払先 UI 反映

この順序なら、まず正本データと未処理管理を固め、その後に利用者向け入力導線を足せる。先に公開フォームだけ作る進め方は、承認フローと管理導線が弱くなりやすいので避ける。

## 12. Phase 0 で確定すべき未決事項
現時点の業務判断ベースの未決事項はなし。

実装時の migration 詳細、partial unique の具体式、ジョブ実装方式などは Phase 1 設計タスクとして別管理する。

## 13. Phase 0 で確定済みの初期回答
1. supplier role は Phase 1 では supplier 自体の単一属性として扱う
2. worker の dedupe 候補キーは「電話番号」「氏名 + ふりがな」を優先する
3. supplier の dedupe 候補キーは「法人名 / 屋号」「電話番号」を優先する
4. 旧 request は superseded / rejected 後に再承認不可で固定する
5. 同じ request を別管理者が先に承認済みの場合は `409 Conflict` とし、「別の管理者が承認済み」と表示する
6. DB 制約は厳しめに入れる前提で進める
7. `vanzai_staff` と認証ユーザーの紐付けは `users.vanzai_staff_id` で持ち、`vanzai_staff` 側に auth FK は持たない
8. payout は `recipient_type` / `recipient_id` を正本とし、既存 `worker_id` / `supplier_id` から backfill する
9. `source_type` は `public_form` / `admin_proxy` / `api_import` / `internal_create` に固定する
10. `sales_reports` の現行正本は `superseded_by_id IS NULL AND status='approved'` とし、訂正申請中は旧 approved 版を維持する
11. 簡易 PL は確定値と予測値を併記し、確定値は invoice / payout / expenses / incentives、予測値は Assignment ベースを使う
12. 個人成績の遅刻は開始時刻から 15 分超過で 1 回とする
13. 公開リンクの有効期限は 7 日、PIN は 5 回失敗でロック、管理者は reset / 再発行の両方を実行可能とする
14. 身分証ファイルは承認 / 却下後 180 日保持し、accounting を削除責任者とする
15. request detail は原文保存を優先し、承認時に master へ正規化する
16. `registration_request_files.document_type` は `driver_license` / `my_number_card` / `residence_card` / `passport` / `other` で開始する
17. supplier 口座は Phase 1 で `supplier_bank_accounts` を追加し、過去支払の再現性も必須とする
18. project_type は leaf（minor）のみ案件へ付与し、既存 flat 種別は migration で major 化して直下に minor を新設する
19. admin-notices は `target_url` / `is_read` / `is_resolved` を持つ未処理キューとし、対象は request 未審査、身分証未確認、sales_reports 未承認、期限超過 project_tasks、payout エラーとする
20. 自動生成 minor の表示名は `major名 + （標準）`、code は `既存 major code + -DEFAULT` とする

## 14. 実装準備メモ
Phase 1 の migration 対象一覧、migration 分割、API 影響範囲は [docs/ops/PHASE1_IMPLEMENTATION_PREP_2026-04-08.md](docs/ops/PHASE1_IMPLEMENTATION_PREP_2026-04-08.md) を参照する。