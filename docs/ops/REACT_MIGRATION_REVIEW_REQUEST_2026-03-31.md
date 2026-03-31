# React前提 Kintone全面移行計画 レビュー依頼

更新日: 2026-03-31

## 1. 依頼文
以下の計画書について、技術レビューをお願いします。

現在、Kintone ベースで運用している業務システムを、既存の FastAPI + PostgreSQL 資産を活かしながら、React ベースの Web システムへ段階移行する計画を作成しています。主眼は、バックエンドを作り直すことではなく、既存業務ロジックを再利用しつつ、画面層を Kintone から自前 Web へ置き換えることです。

今回見てほしいのは実装内容ではなく、計画そのものの妥当性です。特に、Phase 1 を参照系に絞る切り方、blocker の優先順位、認証と権限の設計、一覧 API の粒度、Sprint 1 から Sprint 3 の進め方、受入基準の十分性について、厳しめにレビューしてください。

次の観点で、問題点、抜け漏れ、順序の不整合、将来の手戻りリスクがあれば指摘してほしいです。

1. Phase 1 を参照系に絞る判断が妥当か
2. blocker の優先順位が適切か
3. 認証、権限、一覧 API 設計に抜けがないか
4. Sprint 1 から Sprint 3 の順序に無理がないか
5. 将来の手戻りリスクや見落としがないか
6. 受入基準が十分か
7. 過剰設計または不足設計になっていないか

可能であれば、単なる感想ではなく、次の形式で返してください。

1. 大きな懸念点
2. 優先的に修正すべき点
3. このまま進めてよい点
4. Phase 2 以降で注意すべき点

## 2. 背景
現状の VANZAI は、業務ロジック、REST API、DB モデル、請求・支払・締め・監査・CSV 取込がすでに FastAPI + PostgreSQL 側にあり、Kintone は主に画面層として利用している状態です。

このため、Kintone 全面移行の主作業はバックエンド再構築ではなく、画面層の置き換えです。方針としては、既存バックエンド資産を活かしつつ、React 管理画面とスタッフ向けモバイル画面を段階導入し、最終的に Kintone を停止または参照専用化することを目指しています。

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
4. ファイルは Cloudflare R2 に保存し、DB には参照キーのみ保持する
5. 別系統バックアップとしてさくらインターネットに日次複製する
6. Phase 1 では編集系ではなく参照系を優先して Kintone 依存を減らす
7. 参照系が安定した後に月次運用 UI、マスタ管理、案件運用、スタッフモバイルへ進む

## 5. 段階計画

### 5.1 Phase A: 技術基盤確定
- React スタックを確定する
- Xserver VPS 構成を確定する
- API 境界を整理する
- 認証と権限の前提を整える
- ファイル保存とバックアップ方針を確定する

### 5.2 Phase 1: 管理画面の参照系
目的は、Kintone を見なくても運用担当が日常確認できる状態を先に作ることです。

対象画面は以下の 9 画面です。

1. ダッシュボード
2. 案件一覧
3. シフト枠一覧
4. アサイン一覧
5. 実績一覧
6. 経費一覧
7. 請求一覧
8. 支払一覧
9. 監査ログ一覧

初期ルートは以下です。

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

優先順は以下です。

1. ダッシュボード
2. 実績一覧
3. アサイン一覧
4. 請求一覧
5. 支払一覧
6. 監査ログ
7. 案件一覧
8. シフト枠一覧
9. 経費一覧

### 5.3 Phase 2: 月次運用画面
- CSV アップロード
- 差戻し
- 洗い替え
- 請求生成
- 支払生成
- 締め
- 締め解除
- PDF ダウンロード

### 5.4 Phase 3: マスタ管理
- 稼働者
- クライアント
- 現場
- 役割
- 案件種別
- 単価
- 単価ルール
- 紹介者
- 備品

### 5.5 Phase 4: 案件・シフト運用
- 案件登録
- シフト枠作成
- アサイン
- 予定 / 確定の状態管理
- 取消理由管理
- 運用メモ管理

### 5.6 Phase 5: スタッフ向けモバイル
- 出勤 / 退勤
- 当日アサイン確認
- 予定確認
- 稼働可否入力
- 経費申請
- 領収書アップロード

## 6. インフラ構成
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
- 本保存: Cloudflare R2
- 別系統バックアップ: さくらインターネット オブジェクトストレージ

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

### 7.2 Phase 1 で追加が必要な一覧 API
1. GET /api/projects
2. GET /api/shift-slots
3. GET /api/assignments
4. GET /api/actuals
5. GET /api/expenses
6. GET /api/invoices
7. GET /api/payouts
8. GET /api/closings は候補
9. 監査ログは既存の POST /api/audit/search を継続利用

### 7.3 一覧 API 共通ルール
- クエリは offset、limit、sort_by、sort_order を共通化
- フィルタ名は entity_id、status、search、period_key、xxx_from、xxx_to に統一
- レスポンスは items、total、offset、limit を共通化
- 表示用の関連名は API 側で解決する
- React 側で複数リソース join はしない
- status は enum value をそのまま返す
- 金額は数値
- 日時は ISO 8601
- 日付は YYYY-MM-DD
- 時刻は HH:MM:SS
- 期間キーは YYYYMM

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
- /login で認証
- ログイン成功後に /dashboard へ遷移
- 起動時に /api/auth/me でセッション復元
- 401 はログインへ戻す
- 403 は権限不足画面を出す
- ナビ非表示とルートガードの両方で権限制御する

## 9. 権限方針
標準案は以下です。

- admin: 全参照画面可
- ops: 全参照画面可
- accounting: 全参照画面可
- site_manager: 担当案件に限定した dashboard / actuals / assignments / projects / shift-slots
- worker: 管理画面対象外

Phase 1 の画面別可視範囲は以下です。

1. Dashboard - admin, ops, accounting, site_manager
2. Actuals - admin, ops, accounting, site_manager
3. Assignments - admin, ops, accounting, site_manager
4. Invoices - admin, ops, accounting
5. Payouts - admin, ops, accounting
6. Expenses - admin, ops, accounting
7. Projects - admin, ops, accounting, site_manager
8. Shift Slots - admin, ops, accounting, site_manager
9. Audit Logs - admin, ops, accounting

## 10. 重要 blocker
1. 認証コードと User モデルのパスワードフィールド不整合
   - User モデルは hashed_password だが、認証実装は password_hash を参照している
2. OAuth2 の tokenUrl 不整合
   - tokenUrl が token だが、実エンドポイントは /api/auth/token
3. DB 依存の固定値問題
   - DB 接続が sqlite 固定で、環境変数ベースになっていない
4. site_manager 権限制御の幽霊参照
   - ShiftSlot.site_manager_id を参照しているが、モデルにそのフィールドが存在しない
5. 一覧系 API が不足
   - React 管理画面 Phase 1 を支える read-only API が未実装

## 11. blocker 対象の既存ファイル
- [src/api/jwt_auth.py](src/api/jwt_auth.py)
- [src/api/deps.py](src/api/deps.py)
- [src/services/auth.py](src/services/auth.py)
- [src/models/master.py](src/models/master.py)
- [src/models/transaction.py](src/models/transaction.py)
- [src/api/main.py](src/api/main.py)
- [src/api/schemas.py](src/api/schemas.py)

## 12. Sprint 計画

### 12.1 Sprint 1
目的は、認証・権限・共通一覧基盤を整え、Dashboard / Actuals / Assignments を React 管理画面で参照可能にすることです。

#### バックエンド
- 認証不整合の解消
- tokenUrl 修正
- DB 接続を環境変数化
- site_manager 判定の見直し
- 一覧 API 共通ページング設計
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
5. 運用担当が Dashboard、Actuals、Assignments を Kintone なしで確認できる

### 12.2 Sprint 2
目的は、請求・支払・監査の主要参照画面を揃えることです。

#### バックエンド
- GET /api/invoices 実装
- GET /api/payouts 実装
- 監査ログ検索 API の画面利用前提を整理

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

### 12.3 Sprint 3
目的は、補助参照画面を追加して Phase 1 の対象画面を揃えることです。

#### バックエンド
- GET /api/projects 実装
- GET /api/shift-slots 実装
- GET /api/expenses 実装

#### フロントエンド
- ProjectsPage 実装
- ShiftSlotsPage 実装
- ExpensesPage 実装

#### 受入
- Kintone または現行運用との件数比較
- 代表データ比較
- 主要列一致確認
- 権限制御確認
- 運用担当レビュー

#### Sprint 3 完了条件
1. /operations/projects が表示できる
2. /operations/shift-slots が表示できる
3. /billing/expenses が表示できる
4. Phase 1 対象 9 画面が React 管理画面で参照できる
5. 主要画面の件数と状態が既存運用と一致する
6. Phase 2 へ進む条件が揃う

## 13. 画面別仕様

### 13.1 Dashboard
- 未処理カード群
- 差異アラート表
- 締め状況表
- period selector を持つ
- カードから actuals / assignments / invoices / payouts へ遷移する

### 13.2 Actuals
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

### 13.3 Assignments
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

### 13.4 Invoices
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

### 13.5 Payouts
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

### 13.6 Audit Logs
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

### 13.7 Projects
表示列:
- code
- name
- client_name
- site_name
- project_type_name
- start_date
- end_date
- is_active

### 13.8 Shift Slots
表示列:
- project_name
- work_date
- start_time
- end_time
- shift_label
- required_count
- assigned_count
- notes

### 13.9 Expenses
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

## 14. テスト方針

### 14.1 バックエンド
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

### 14.2 フロントエンド
- ログイン
- セッション復元
- 401 時のログアウト
- 403 表示
- Dashboard から各画面への遷移
- フィルタと URL search params の同期
- 空状態表示
- API エラー表示
- 権限外メニュー非表示

## 15. Phase 1 受入基準
1. ログインできる
2. 権限に応じてメニューが出し分けされる
3. 9 画面が表示できる
4. 各一覧で絞り込みできる
5. ページングとソートが動く
6. 主要件数が既存運用と一致する
7. 主要列が既存運用と一致する
8. 代表データが既存運用と一致する
9. 権限外 URL に直接アクセスすると 403 になる
10. 未認証状態では /login に戻る
11. 運用担当が Kintone なしで日常確認を回せる

## 16. Phase 1 の非対象
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

## 17. Phase 1 完了判定
- React 管理画面で参照系 9 画面が成立している
- 主要な read-only API が実装済み
- ロール別表示が制御されている
- 運用担当が Kintone なしで日常確認できる
- 既存運用との差異確認チェックが通っている

## 18. レビューしてほしい論点
1. Phase 1 を参照系に絞る切り方は妥当か
2. Sprint 1 の blocker 解消順は適切か
3. API 共通仕様の粒度は十分か
4. site_manager の権限制御方針は妥当か
5. React 管理画面の route / role / permission 設計に抜けがないか
6. Invoices / Payouts / Audit Logs を Sprint 2 に置く順序は妥当か
7. 参照一致チェックの受入基準は十分か
8. Phase 2 へ進む前提条件に不足がないか