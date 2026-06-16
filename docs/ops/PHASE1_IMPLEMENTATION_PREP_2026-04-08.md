# VANZAI Phase 1 実装準備メモ

更新日: 2026-04-08

## 1. 目的
Phase 0 で確定した業務判断を、Phase 1 の実装へ落とすための準備資料。

この文書では次の 3 点を固定する。
1. migration 対象テーブル一覧と追加列
2. migration の分割順序と backfill 設計
3. API スキーマと画面影響範囲

## 2. 前提
- 業務判断ベースの未決事項は [docs/ops/EXPANSION_IMPLEMENTATION_PLAN_2026-04-07.md](docs/ops/EXPANSION_IMPLEMENTATION_PLAN_2026-04-07.md) 上では解消済み
- 現行モデルは worker / supplier / project_type / payout / staff_notices が既に存在する
- 既存 payout は worker_id / supplier_id 前提、project_type はフラット、dashboard は summary 前提

## 3. migration 対象一覧

### 3.1 既存テーブルの追加列

| テーブル | 追加列 | 目的 |
|---|---|---|
| users | vanzai_staff_id | ログインユーザーと VANZAI 職員の紐付け |
| workers | furigana, sole_proprietor_name, emergency_contact_name_kana, emergency_contact_phone, gender, invoice_registration_status, invoice_number | 公開登録フォームと支払前提の追加属性 |
| clients | billing_email | 請求導線の補強 |
| suppliers | supplier_type, entity_type | 紹介者 / 下請け、個人 / 法人の区分 |
| projects | vanzai_manager_id | VANZAI 側責任者の正本 |
| project_types | category_level, parent_id | 3 階層化 |
| payouts | recipient_type, recipient_id, payee_name_snapshot, bank_account_snapshot_json, tax_treatment_snapshot_json | 支払先抽象化と再現性 |

### 3.2 新規テーブル

| テーブル | 用途 |
|---|---|
| worker_bank_accounts | worker 口座履歴 |
| supplier_bank_accounts | supplier 口座履歴 |
| client_staff | クライアント職員 |
| vanzai_staff | VANZAI 職員 |
| registration_requests | 公開受付ヘッダ |
| worker_registration_request_details | 稼働者フォーム原文 |
| supplier_individual_request_details | 個人 supplier フォーム原文 |
| supplier_corporation_request_details | 法人 supplier フォーム原文 |
| introducer_identity_request_details | 身分証受付原文 |
| registration_request_files | 受付添付ファイル |
| project_type_documents | 案件種別資料 |
| task_templates | 案件種別別タスクテンプレート |
| project_tasks | 案件タスク |
| sales_reports | 販売台数報告 |

### 3.3 backfill が必要な既存データ

| 対象 | backfill 内容 |
|---|---|
| payouts | worker_id ありなら recipient_type=worker / recipient_id=worker_id、supplier_id ありなら recipient_type=supplier / recipient_id=supplier_id |
| project_types | 既存 flat 種別を major 化し、直下に minor を自動生成 |
| projects.project_type_id | 既存 project_type_id を新設 minor へ差し替える |
| users | 既存行は vanzai_staff_id を NULL で開始 |

### 3.4 DB 制約候補

| テーブル | 制約 |
|---|---|
| users | worker_id と vanzai_staff_id の同時設定禁止 |
| worker_bank_accounts | 同一 worker の有効期間重複禁止、active primary 一意 |
| supplier_bank_accounts | 同一 supplier の有効期間重複禁止、active primary 一意 |
| registration_requests | public_token_hash 一意、approved_target と status 整合 |
| sales_reports | approved current revision 一意、pending correction 多重化防止 |
| project_types | parent 循環禁止 |
| payouts | recipient 系と legacy 列の整合 |

## 4. migration 設計

### 4.1 推奨 revision 分割

#### Revision A: マスタ拡張の土台
- users に vanzai_staff_id を追加
- workers, clients, suppliers, projects に追加列を入れる
- client_staff, vanzai_staff, worker_bank_accounts, supplier_bank_accounts を追加する
- users 排他制約、bank_accounts 系 index を付ける
- 実装済み revision: 20260408a001_phase1_revision_a_master_foundations.py

理由:
- request 承認先や project 責任者の参照先を先に作る必要がある
- bank_accounts を早く分離しないと payout recipient 設計が進まない

#### Revision B: request 受付基盤
- registration_requests と 4 detail テーブルを追加する
- registration_request_files を追加する
- request status / token / dedupe の index と制約を付ける
- 実装済み revision: 20260408b001_phase1_revision_b_registration_requests.py

理由:
- 公開フォーム、管理承認、監査の基礎になるため

#### Revision C: project_type 3 階層化
- project_types に category_level, parent_id を追加する
- 既存 row を major に更新する
- 既存 row ごとに minor を 1 行自動生成する
- minor の表示名は major名 + （標準）、code は major_code + -DEFAULT を使う
- projects.project_type_id を新設 minor へ backfill する
- 実装済み revision: 20260408c001_phase1_revision_c_project_type_hierarchy.py

理由:
- 既存 project_type_id を維持したまま leaf 運用へ切り替えるためには、この backfill を単独 revision として切り出した方が安全

#### Revision D: payout recipient 抽象化
- payouts に recipient 系と snapshot 列を追加する
- 既存 payout を backfill する
- recipient 系 index を付ける
- legacy worker_id / supplier_id は残す
- 実装済み revision: 20260408d001_phase1_revision_d_payout_recipients.py

理由:
- payout 一覧、生成、送信、銀行振込への影響が大きく、独立して検証したい

#### Revision E: 運用テーブル追加
- project_type_documents, task_templates, project_tasks, sales_reports を追加する
- sales_reports の supersede 制約と index を付ける
- 実装済み revision: 20260408e001_phase1_revision_e_documents_tasks_sales_reports.py

理由:
- request / payout と比べて独立性が高く、最後に足せる

### 4.2 backfill 詳細

#### project_types backfill
1. 既存 project_types を全件取得する
2. 各 row を category_level=major に更新する
3. 各 major の直下に minor を自動生成する
4. 生成 minor に既存 projects.project_type_id を付け替える
5. major には直接 project が紐付かない状態にする

fallback:
- 既存 code が NULL の場合は migration 実装側で ID 由来の fallback code を生成する

#### payouts backfill
1. worker_id がある行へ recipient_type=worker, recipient_id=worker_id を設定する
2. supplier_id がある行へ recipient_type=supplier, recipient_id=supplier_id を設定する
3. snapshot 列は既存履歴の再構成が難しいため、過去行は NULL 許容で開始し、以後の生成で必須化する案を採る

#### bank_accounts 初期化
- worker / supplier の既存口座が DB に直置きされていないため、自動 backfill は原則なし
- 新 UI / import / request 承認から履歴を積み始める

### 4.3 migration 実装上の注意
- project_type backfill は同一 revision 内で update と insert を混ぜるため、ロールバック可能な単位で組む
- payout snapshot は過去行の完全再現を migration で無理に埋めない
- users の排他制約は DB ごとの差が出るので、SQLite fallback を考慮する
- bank account の有効期間重複禁止は PostgreSQL では exclusion 制約も候補だが、まずは実装しやすい制約かアプリ制御との分担を明示する

## 5. API スキーマ影響範囲

### 5.1 既存 API の拡張

#### workers
対象:
- /api/workers
- /api/workers/{id}

追加項目:
- furigana
- sole_proprietor_name
- emergency_contact_name_kana
- emergency_contact_phone
- gender
- invoice_registration_status
- invoice_number

推奨:
- 口座履歴は workers create / update に直接ネストせず、専用 endpoint に分離する

#### suppliers
対象:
- /api/suppliers
- /api/suppliers/{id}

追加項目:
- supplier_type
- entity_type

推奨:
- 口座履歴は supplier create / update とは分離する

#### projects
対象:
- /api/projects
- /api/projects/{id}

追加項目:
- vanzai_manager_id

影響:
- 現行 primary_manager_id / secondary_manager_id と UI 表示を分ける必要がある

#### project-types
対象:
- /api/project-types
- 新設 /api/project-types/tree

追加項目:
- category_level
- parent_id
- children または tree node 構造
- selectable フラグ

互換方針:
- 既存 /api/project-types はフラット一覧の互換 endpoint として残す
- 新 UI は /api/project-types/tree を使う

#### payouts
対象:
- /api/payouts
- /api/payouts/generate
- /api/payouts/{id}/confirm
- /api/payouts/{id}/deliver
- /api/payouts/{id}/pdf

追加項目:
- recipient_type
- recipient_id
- payee_name_snapshot
- bank_account_snapshot_json
- tax_treatment_snapshot_json

互換方針:
- 既存 worker_id 生成 request は段階的に deprecated にする
- まずは generate request に recipient_type / recipient_id を追加し、worker_id 互換を残す

#### dashboard
対象:
- /api/dashboard
- 新設候補 /api/admin-notices

追加項目:
- target_url
- severity
- assigned_role
- stale_days
- is_read
- is_resolved

注意:
- 既存 DashboardResponse の unprocessed_items は summary 向きで、未処理キューの永続状態には不十分

### 5.2 新設 API

#### bank account 系
- /api/workers/{id}/bank-accounts
- /api/workers/{id}/bank-accounts/{account_id}
- /api/suppliers/{id}/bank-accounts
- /api/suppliers/{id}/bank-accounts/{account_id}

#### client / vanzai staff 系
- /api/client-staff
- /api/vanzai-staff

#### request / link 系
- /api/registration-links
- /api/registration-links/{id}/reset-pin-lock
- /api/registration-links/{id}/reissue
- /api/registration-requests
- /api/registration-requests/{id}
- /api/registration-requests/{id}/approve
- /api/registration-requests/{id}/reject
- /public/registrations/{form_type}
- /public/registrations/worker
- /public/registrations/supplier-individual
- /public/registrations/supplier-corporation
- /public/registrations/introducer-identity

#### 運用 / 分析系
- /api/admin-notices
- /api/sales-reports
- /api/reports/pl
- /api/reports/worker-performance

### 5.3 admin-web 影響ページ

| 画面 | 影響 |
|---|---|
| DashboardPage | admin-notices 未処理キュー表示 |
| MasterDataPage | suppliers と project_types の列追加、tree 表示への段階移行 |
| WorkersPage | 追加 worker 項目と introducer / bank account 導線 |
| ProjectsPage | vanzai_manager_id と leaf project_type 選択 |
| PayoutsPage | recipient ベース表示とエラー通知連携 |

### 5.4 staff-mobile 影響ページ

| 画面 | 影響 |
|---|---|
| TodayAssignmentsPage | check-in / check-out 既存導線を維持しつつ sales report 入口を追加 |
| ActualsPage | sales report 履歴との並列表現を検討 |
| NoticesPage | staff_notices は既存のまま維持。admin-notices は管理画面専用で別物 |

### 5.5 破壊変更リスク

| 領域 | リスク | 対応 |
|---|---|---|
| project-types | フラット前提の select UI が tree 化で壊れる | /api/project-types は互換維持、tree API を新設 |
| payouts | worker_id 前提の request / service が壊れる | recipient 系追加後もしばらく worker_id 互換を残す |
| dashboard | summary と queue を同一レスポンスに混ぜると複雑化 | /api/admin-notices を分ける案を優先 |
| bank transfer | worker 口座直参照が supplier / recipient に対応できない | recipient 解決層をサービスに追加 |

## 6. 実装順の提案
1. Revision A と worker / supplier / project / project_type の API スキーマ更新
2. Revision B と registration API 下地
3. Revision C の project_type backfill と tree API
4. Revision D の payout recipient 変更と bank transfer 解決層
5. Revision E の sales_reports / task 系 API

## 7. 次アクション
1. workers / suppliers / projects / payouts / project-types の schema と CRUD API を migration 後スキーマへ追随させる
2. project_type tree API と leaf-only 選択制御を admin-web 側に実装する
3. registration_requests 系の schema / endpoint / 承認 transaction を実装する

## 8. 実装状況
- Revision A-E の Alembic ファイルは作成済み
- Alembic head は 20260408e001 の 1 本に収束済み
- alembic upgrade head --sql で static SQL 生成まで確認済み