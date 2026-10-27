# React前提 Kintone全面移行計画書

更新日: 2026-04-01

## 1. 目的
Kintone ベースで運用している現行業務を、既存 FastAPI + PostgreSQL 資産を活かしながら、React ベースの Web システムへ段階移行する。

主眼はバックエンドの作り直しではなく、既存業務ロジックを再利用しつつ、画面層を Kintone から自前 Web へ置き換えることにある。

## 2. 背景
現状の VANZAI は、業務ロジック、REST API、DB モデル、請求・支払・締め・監査・CSV 取込が FastAPI + PostgreSQL 側にあり、Kintone は主に画面層として利用している。

このため、全面移行の中心作業は UI と運用導線の再構築であり、バックエンドの再実装ではない。既存資産を活かしつつ、管理画面とスタッフ向けモバイル画面を段階導入し、最終的に Kintone を停止または参照専用化する。

## 3. 前提
- Kintone は恒久的な二重運用を前提にしない
- 最終的には Kintone を停止または参照専用化する
- 既存の FastAPI + PostgreSQL の業務ロジックを再利用する
- フロントエンドは React 系で進める
- 管理画面とスタッフモバイルは別アプリにする
- Phase 1 は管理画面の参照系から始める
- 既存の WebA は全面流用せず、UI 参考資産に留める

## 4. 全体方針
1. React + FastAPI + PostgreSQL の 3 層構成に固定する
2. React 管理画面を apps/admin-web、スタッフ向けモバイルを apps/staff-mobile として分離する
3. FastAPI は API 専用サーバーとして運用し、React ビルド成果物は Nginx で配信する
4. ファイルは最終的に Cloudflare R2 に保存し、DB には参照キーのみ保持する
5. 別系統バックアップとしてさくらインターネットに日次複製する
6. Phase 1 では編集系ではなく参照系を優先して Kintone 依存を減らす
7. 参照系が安定した後に月次運用 UI、マスタ管理、案件運用、スタッフモバイルへ進む

## 5. インフラ構成
- VPS: Xserver VPS
- 推奨プラン: 6GB
- 余裕案: 12GB
- 本番非推奨: 2GB
- OS: Linux
- Web: Nginx
- API: FastAPI
- DB: PostgreSQL
- プロセス管理: systemd
- SSL: HTTPS 前提
- 本保存: Cloudflare R2（Phase 5 完了後に切替）
- 別系統バックアップ: さくらインターネット オブジェクトストレージ

## 6. フェーズ計画

### 6.0 現在の実装進捗メモ（2026-03-31）
- Phase 1 の参照系画面は admin-web 側で実装済み
- 追加で CSV取込、差戻し文面作成、請求生成/発行、支払生成/確定/支払済み更新、PDFダウンロード、支払明細メール送信導線まで実装済み
- 請求一覧と支払一覧では保存済み PDF の storage key を参照可能で、請求発行時と支払確定時に storage/pdfs 配下へ PDF を保存する
- 支払一覧では最終送信ステータス、送信日時、送信先を参照可能で、送信結果は payout_deliveries と監査ログに記録する
- 支払一覧から送信履歴パネルを開き、再送を含む送信試行履歴を確認できる
- 履歴パネルでは宛先メールアドレスを上書きして送信でき、空欄時は既定宛先へフォールバックする
- 履歴パネルには payee に紐づく既定送信先メールを表示し、送信前に候補と未設定状態を確認できる
- 履歴パネルでは既定送信先に加え、過去送信先から再利用候補を出し、ワンクリックで宛先入力へ反映できる
- 支払一覧には既定送信先未設定のみの絞り込みを追加し、未設定支払を月次運用で先に洗い出せるようにした
- 支払一覧には未送信のみ / 送信失敗のみの絞り込みも追加し、再送対象を最終送信状態から絞り込める
- 送信時の理由メモと内部メモは payout_deliveries と監査ログへ残し、再送時の判断文脈を継続参照できる
- ダッシュボードと支払一覧に未設定送信先件数のサマリーを出し、送信前の整備漏れを月次画面から把握できる
- 監査ログ一覧の概要には支払明細送信の宛先、送信理由メモ、内部メモを表示し、一覧だけで送信判断の文脈を追えるようにした
- ローカル検証は `alembic upgrade head` 後に uvicorn と admin-web を起動し、`apps/admin-web/e2e/phase1-smoke.spec.ts` を `npm run smoke:e2e` で流す手順に統一した
- スモーク実行前に `scripts/ensure_local_admin.py` と `scripts/ensure_browser_smoke_data.py` を自動実行し、ログインユーザーと支払送信確認用データを再現可能に投入する
- Phase 3 は admin-web のマスタ一覧からクライアント、現場、案件種別、役割の新規登録に着手済み
- 追加した POST /api/clients、/api/sites、/api/project-types、/api/roles は MASTER_WRITE 権限で保護し、作成時に監査ログを残す
- Phase 3 はさらに稼働者 / 下請けの新規登録・編集と、売上単価 / 外注単価 / 単価ルールの新規登録・編集まで拡張済み
- 追加した POST/PUT /api/workers、/api/suppliers、/api/price-rules、/api/price-sales、/api/price-outsource は admin 権限に限定し、作成・更新の監査ログを残す
- `apps/admin-web/e2e/phase1-smoke.spec.ts` は下請け作成 / 更新に加え、単価ルール、売上単価、外注単価の作成 / 更新も検証するよう拡張済み
- ローカル既存 DB で server default が不足していても作成系が通るよう、`src/models/base.py` の `TimestampMixin` に Python 側 timestamp default を追加した
- Phase 4 は案件登録 / 編集、シフト枠作成 / 編集、アサイン作成、アサイン編集、単件/一括のアサイン状態変更まで実装済み
- canceled 変更時は取消理由が必須で、有効な実績が残るアサインは取消不可
- 一括状態更新は対象月内でページ・ステータス切替をまたいで選択保持でき、保存済み選択セットの再利用も可能
- 保存済み選択セットは /api/assignments/selection-sets でサーバー保存され、共有セットは admin / ops が再利用用に公開できる
- 一括更新は取消不可条件が1件でもあれば全件をロールバックする
- 状態変更パネルで対象アサインの監査ログを参照でき、対象月の取消履歴専用一覧と canceled 行からの再開導線を追加済み
- canceled から tentative / confirmed へ戻す際は復帰理由が必須で、監査ログと取消履歴一覧に復帰日時・実行者・理由を表示する
- active な実績があるアサインは、枠・稼働者・役割の差し替えも不可
- 案件一覧とシフト枠一覧では主要項目と運用メモを直接編集でき、既存 notes を Kintone を介さず管理できる
- `apps/admin-web/e2e/phase1-smoke.spec.ts` は案件 / シフト枠の作成・更新も検証するよう拡張済み
- Phase 5 の初手として `apps/staff-mobile` を追加し、worker ロール向けにログイン、当日アサイン確認、今月の実績確認を既存 API で提供開始した
- Phase 5 を進め、worker 向けの出勤 / 退勤 API、経費申請 API、領収書アップロード、staff-mobile の打刻 / 経費画面を追加した
- Phase 5 をさらに進め、worker 向けの予定確認画面、稼働可否入力画面、経費一覧からの領収書参照導線を追加した
- Phase 5 をさらに進め、assignment に worker 応答状態を持たせて `POST /api/assignments/{id}/worker-response` を追加し、staff-mobile の予定画面から参加可 / 辞退返信と未回答バッジ表示を行えるようにした
- Phase 5 の reminder 配信として、scheduler の週次催促を pending assignment の worker 向けメール送信へ接続し、対象期間を `SCHEDULER_WEEKLY_LOOKAHEAD_DAYS` で制御できるようにした
- backend には `worker_availability` と `GET/POST /api/worker-availability`、expense 承認 / 却下 / 領収書ダウンロード API を追加し、admin-web 経費一覧から承認運用へ移行できるようにした
- 領収書保存は `ObjectStorage` に寄せて object key 契約を明示し、Cloudflare R2 への保存先切替を後段で差し替えやすい形へ整理した
- 締め・締め解除は専用ページではなく、ダッシュボードの締め状況セクションで運用可能
- `alembic upgrade head` をローカル DB に適用し、Alembic head は `4b6f2d1c9a0e` に統一した
- Focused pytest 35件、admin-web build、Playwright smoke、staff-mobile build で、案件 / シフト枠更新と Phase 5 attendance / expense / availability / assignment response 追加を検証済み
- 次の主課題は Phase 5 のリマインド配信実装と、Cloudflare R2 切替の実装計画具体化である
- Cloudflare R2 への PDF 本保存切替は計画上 Phase 5 完了後へ後ろ倒しする

### 6.1 Phase A: 技術基盤確定
Sprint 1 着手前に、以下を確定する。

1. React スタック
2. Xserver VPS 構成
3. API 境界
4. 認証方式
5. トークン更新方針
6. 同一オリジン構成と CORS 方針
7. CSRF の扱い
8. site_manager 紐付けモデル
9. 共通エラーレスポンス形式
10. sort_by 許可カラム方式
11. limit のデフォルト値と最大値
12. ファイル保存とバックアップ方針

認証方式は Bearer token を前提とする。初期方針としては silent refresh を必須とせず、期限切れ時は再ログインへ戻す方式を標準案とする。

配信構成は Nginx のリバースプロキシで /api を同一オリジン配下へ寄せる前提とし、Cookie セッションを採用しない限り CSRF 対策は不要と整理する。

site_manager の担当案件紐付けは、第一候補として Project.primary_manager_id / secondary_manager_id を正本とする。これで運用要件を満たせない場合のみ、中間テーブル方式を再検討する。

関連する決定待ち事項は [docs/decisions/DECISION_LOG.md](docs/decisions/DECISION_LOG.md) の DEC-011、DEC-012、DEC-013 を参照する。

### 6.2 Phase 1: 管理画面の参照系
目的は、Kintone を見なくても運用担当が日常確認できる状態を先に作ることにある。

Phase 1 の想定期間は Sprint 1 から Sprint 3 までの 3 スプリントとする。参照専用期間が長引くと Kintone 側の書き込み運用が固定化するため、Phase 1 完了後は速やかに Phase 2 判定へ進む。

対象画面は以下の 9 画面とする。

1. ダッシュボード
2. 案件一覧
3. シフト枠一覧
4. アサイン一覧
5. 実績一覧
6. 経費一覧
7. 請求一覧
8. 支払一覧
9. 監査ログ一覧

初期ルートは以下とする。

1. /login
2. /dashboard
3. /operations/actuals
4. /operations/assignments
5. /operations/projects
6. /operations/shift-slots
7. /billing/invoices
8. /billing/payouts
9. /billing/expenses
10. /audit-logs
11. /403

優先順は以下とする。

1. ダッシュボード
2. 実績一覧
3. アサイン一覧
4. 請求一覧
5. 支払一覧
6. 監査ログ
7. 案件一覧
8. シフト枠一覧
9. 経費一覧

### 6.3 Phase 2: 月次運用画面
- CSV アップロード
- 差戻し
- 洗い替え
- 請求生成
- 支払生成
- 締め
- 締め解除
- PDF ダウンロード

### 6.4 Phase 3: マスタ管理
- 稼働者
- クライアント
- 現場
- 役割
- 案件種別
- 単価
- 単価ルール
- 紹介者
- 備品

### 6.5 Phase 4: 案件・シフト運用
- 案件登録 / 編集
- シフト枠作成 / 編集
- アサイン
- 予定 / 確定の状態管理
- 取消理由管理
- 運用メモ管理

### 6.6 Phase 5: スタッフ向けモバイル
- worker ロール向けログイン
- 当日アサイン確認
- 今月の実績確認
- 出勤 / 退勤
- 予定確認
- 稼働可否入力
- 経費申請
- 領収書アップロード

### 6.7 Phase 6: ファイル保存先・配信基盤の本番切替
- PDF 保存先をローカル storage/pdfs から Cloudflare R2 へ切替
- 参照キー管理、アップロード、ダウンロード経路を本番保存前提で整備
- R2 保存データのバックアップと監視を整備
- 切替前に admin-web / staff-mobile の主要導線で回帰確認を行う

## 7. バックエンド方針

### 7.1 既存資産を再利用する領域
- 認証 API
- dashboard
- CSV import
- invoice generation
- payout generation
- closing
- aggregation
- audit search

### 7.2 Sprint 1 から 3 で追加する一覧 API
1. GET /api/projects
2. GET /api/shift-slots
3. GET /api/assignments
4. GET /api/actuals
5. GET /api/expenses
6. GET /api/invoices
7. GET /api/payouts
8. GET /api/closings は候補
9. 監査ログは既存の POST /api/audit/search を継続利用するが、Sprint 2 着手前に actor、action、date range、period_key を満たすか確認する

### 7.3 共通 API 仕様
- クエリは offset、limit、sort_by、sort_order を共通化する
- フィルタ名は entity_id、status、search、period_key、xxx_from、xxx_to に統一する
- レスポンスは items、total、offset、limit を共通化する
- 表示用の関連名は API 側で解決する
- React 側で複数リソース join はしない
- status は enum value をそのまま返す
- 金額は数値、日時は ISO 8601、日付は YYYY-MM-DD、時刻は HH:MM:SS、期間キーは YYYYMM に統一する
- sort_by は API ごとの許可リスト方式にする
- limit はデフォルト値と最大値を設定する
- search を使う API では対象カラムを明示する

### 7.4 共通エラーレスポンス
400、401、403、404、500 は次の JSON 形式を標準とする。

- error_code
- message
- detail

画面側は error_code をもとに表示分岐し、message はユーザー表示、detail は開発・調査用として扱う。

## 8. フロントエンド方針

### 8.1 推奨スタック
- React
- Vite
- TypeScript
- React Router
- TanStack Query
- フォームライブラリ
- 日付操作ライブラリ
- lint / typecheck

### 8.2 apps/admin-web の基本構成
- src/app
- src/routes
- src/pages
- src/features
- src/components
- src/lib/api
- src/lib/auth
- src/lib/query
- src/lib/formatters
- src/styles
- src/types

### 8.3 共通 UI 部品
- AppShell
- SideNav
- AuthGuard
- PageHeader
- DataTable
- FilterBar
- StatusBadge
- SummaryCard
- EmptyState
- ErrorState
- LoadingOverlay
- DateRangePicker

### 8.4 ルーティング / 認証
- /login で認証する
- ログイン成功後に /dashboard へ遷移する
- 起動時に /api/auth/me でセッション復元する
- 401 はログインへ戻す
- 403 は権限不足画面を出す
- ナビ非表示とルートガードの両方で権限制御する

## 9. 権限方針
標準案は以下とする。

- admin: 全参照画面可
- ops: 全参照画面可
- accounting: 原則参照画面可。監査ログ閲覧可否は Phase A の確認事項とする
- site_manager: 担当案件に限定した dashboard / actuals / assignments / projects / shift-slots
- worker: 管理画面対象外

Phase 1 の画面別可視範囲は以下とする。

1. Dashboard - admin, ops, accounting, site_manager
2. Actuals - admin, ops, accounting, site_manager
3. Assignments - admin, ops, accounting, site_manager
4. Invoices - admin, ops, accounting
5. Payouts - admin, ops, accounting
6. Expenses - admin, ops, accounting
7. Projects - admin, ops, accounting, site_manager
8. Shift Slots - admin, ops, accounting, site_manager
9. Audit Logs - admin, ops, accounting pending decision

## 10. 既存不整合 blocker
既存不整合として、Sprint 1 着手前に整理または着手順を確定する blocker は以下とする。

1. 認証コードと User モデルのパスワードフィールド不整合
   - User モデルは hashed_password だが、認証実装は password_hash を参照している
2. OAuth2 の tokenUrl 不整合
   - tokenUrl が token だが、実エンドポイントは /api/auth/token
3. DB 依存の固定値問題
   - DB 接続が sqlite 固定で、環境変数ベースになっていない
4. site_manager 権限制御の幽霊参照
   - ShiftSlot.site_manager_id を参照しているが、モデルにそのフィールドが存在しない

対象ファイルは以下とする。

- [src/api/jwt_auth.py](src/api/jwt_auth.py)
- [src/api/deps.py](src/api/deps.py)
- [src/services/auth.py](src/services/auth.py)
- [src/models/master.py](src/models/master.py)
- [src/models/transaction.py](src/models/transaction.py)

## 11. Sprint 計画

### 11.1 Sprint 1
目的は、認証・権限・共通一覧基盤を整え、Dashboard / Actuals / Assignments を React 管理画面で参照可能にすることとする。

#### バックエンド
- 認証不整合の解消
- tokenUrl 修正
- DB 接続を環境変数化
- site_manager 判定の見直し
- 一覧 API 共通ページング設計
- 共通エラーレスポンス設計
- GET /api/actuals 実装
- GET /api/assignments 実装
- /api/dashboard のフロント変換しやすさを整理

#### フロントエンド
- apps/admin-web 初期化
- 認証ストア実装
- /login 実装
- ProtectedRoute 実装
- PermissionRoute 実装
- AppShell 実装
- SideNav 実装
- DashboardPage 実装
- ActualsPage 実装
- AssignmentsPage 実装

#### Sprint 1 完了条件
1. /api/auth/token と /api/auth/me が整合している
2. GET /api/actuals と GET /api/assignments が共通ページング形式で返る
3. /login、/dashboard、/operations/actuals、/operations/assignments が動く
4. 401 はログインへ、403 は権限不足表示になる
5. Dashboard、Actuals、Assignments について件数比較、代表データ比較、権限確認が完了している

### 11.2 Sprint 2
目的は、請求・支払・監査の主要参照画面を揃えることとする。

#### バックエンド
- GET /api/invoices 実装
- GET /api/payouts 実装
- 監査ログ検索 API の対応条件確認
- 必要であれば audit search の request schema と query service を補強

#### フロントエンド
- InvoicesPage 実装
- PayoutsPage 実装
- AuditLogsPage 実装
- SideNav と権限制御に統合

#### Sprint 2 完了条件
1. /billing/invoices が表示できる
2. /billing/payouts が表示できる
3. /audit-logs が表示できる
4. invoices / payouts がフィルタ、ページング、ソートに対応している
5. audit search が actor、action、date range、period_key で使える
6. Invoices、Payouts、Audit Logs について件数比較、代表データ比較、権限確認が完了している

### 11.3 Sprint 3
目的は、補助参照画面を追加して Phase 1 の対象画面を揃えることとする。

#### バックエンド
- GET /api/projects 実装
- GET /api/shift-slots 実装
- GET /api/expenses 実装

#### フロントエンド
- ProjectsPage 実装
- ShiftSlotsPage 実装
- ExpensesPage 実装

#### Sprint 3 完了条件
1. /operations/projects が表示できる
2. /operations/shift-slots が表示できる
3. /billing/expenses が表示できる
4. Phase 1 対象 9 画面が React 管理画面で参照できる
5. 主要画面の件数と状態が既存運用と一致する
6. Projects、Shift Slots、Expenses について件数比較、代表データ比較、権限確認が完了している
7. Phase 2 へ進む条件が揃っている

## 12. 画面別仕様

### 12.1 Dashboard
- 未処理カード群
- 差異アラート表
- 締め状況表
- period selector を持つ
- カードから actuals / assignments / invoices / payouts へ遷移する

### 12.2 Actuals
フィルタ:
- period_key
- project_id
- worker_id
- status
- needs_review
- work_date_from
- work_date_to
- page
- limit
- sort

表示列:
- work_date
- project_name
- worker_name
- role_name
- start_time
- end_time
- calc_minutes_billable
- applied_price_sales
- applied_price_outsource
- status
- needs_review
- review_reason

### 12.3 Assignments
フィルタ:
- project_id
- worker_id
- role_id
- status
- work_date_from
- work_date_to
- page
- limit
- sort

表示列:
- work_date
- project_name
- shift_label
- worker_name
- role_name
- status
- cancel_reason
- locked_price_sales
- locked_price_outsource

### 12.4 Invoices
フィルタ:
- period_key
- client_id
- project_id
- status
- version
- page
- limit
- sort

表示列:
- invoice_number
- client_name
- project_name
- period_key
- version
- status
- total_amount
- issued_at
- has_pdf

### 12.5 Payouts
フィルタ:
- period_key
- worker_id
- supplier_id
- project_id
- status
- page
- limit
- sort

表示列:
- payout_number
- payee_name
- payee_type
- project_name
- period_key
- version
- status
- total_amount
- approved_at
- paid_at

### 12.6 Audit Logs
フィルタ:
- period_key
- action_type
- actor
- date_from
- date_to
- page
- limit

表示列:
- timestamp
- action
- actor
- target_type
- target_id
- details summary

### 12.7 Projects
表示列:
- code
- name
- client_name
- site_name
- project_type_name
- start_date
- end_date
- is_active

### 12.8 Shift Slots
表示列:
- project_name
- work_date
- start_time
- end_time
- shift_label
- required_count
- assigned_count
- notes

### 12.9 Expenses
表示列:
- expense_date
- project_name
- worker_name
- category
- amount
- status
- approved_by
- approved_at
- has_receipt

## 13. テスト方針

### 13.1 バックエンド
- 認証整合テスト
- 正常ログイン
- パスワード不一致
- 非アクティブ拒否
- JWT type 不正
- トークン期限切れ
- 一覧 API のフィルタ・ページング・ソート
- audit search の API 層整合
- site_manager の担当案件アクセス判定

参考テスト:
- [tests/test_auth.py](tests/test_auth.py)
- [tests/test_dashboard.py](tests/test_dashboard.py)
- [tests/test_audit_search.py](tests/test_audit_search.py)

### 13.2 フロントエンド
- ログイン
- セッション復元
- 401 時のログアウト
- 403 表示
- Dashboard から各画面への遷移
- フィルタと URL search params の同期
- 空状態表示
- API エラー表示
- 権限外メニュー非表示

## 14. Phase 1 受入基準
1. ログインできる
2. 権限に応じてメニューが出し分けされる
3. 9 画面が表示できる
4. 各一覧で絞り込みできる
5. ページングとソートが動く
6. 主要件数は既存運用と完全一致する
7. 主要列は既存運用と一致する
8. 代表データは既存運用と一致する
9. 権限外 URL に直接アクセスすると 403 になる
10. 未認証状態では /login に戻る
11. 運用担当が Kintone なしで日常確認を回せる
12. 管理画面の対応環境は PC + Chrome 最新版を標準とする
13. ダッシュボード初期表示と一覧初回表示の性能目標を設定し、測定結果を残す

## 15. Phase 1 の非対象
- 新規作成
- 編集
- 削除
- 状態変更
- ファイル再アップロード
- 締め実行
- 請求生成
- 支払生成
- PDF ダウンロード操作の本格実装
- モバイル画面

## 16. Phase 2 着手条件
1. Phase 1 の受入基準を満たしている
2. 運用担当レビューが完了している
3. バックアップ / リストア手順の確認が完了している
4. ステージング環境が確保されている
5. Kintone の参照専用化または継続利用の判断ポイントが明文化されている

## 17. Phase 1 完了判定
- React 管理画面で参照系 9 画面が成立している
- 主要な read-only API が実装済みである
- ロール別表示が制御されている
- 運用担当が Kintone なしで日常確認できる
- 既存運用との差異確認チェックが通っている
- Phase 2 着手条件が満たされている

## 18. レビュー反映による未決事項
1. accounting に audit log 閲覧権限を与えるか
2. token refresh を将来導入するか
3. site_manager の中間テーブルが必要になる運用要件があるか
4. Phase 1 の性能目標値を何秒 / 何ミリ秒に置くか

上記に関連する Proposal は [docs/decisions/DECISION_LOG.md](docs/decisions/DECISION_LOG.md) の DEC-011、DEC-012、DEC-013、DEC-014 を参照する。

## 19. 次アクション
1. Phase A の未確定事項を決定ログへ落とす
2. blocker 4 件の修正方針を固める
3. Sprint 1 の API 共通仕様を schema へ反映する
4. apps/admin-web の初期構成に着手する