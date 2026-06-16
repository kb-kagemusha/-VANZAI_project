# CHANGELOG

バージョン管理ルール（AGENTS.md セクション9 参照）
- **X（左）**: 大きな機能追加（新ドメイン追加、画面体系の大幅変更など）
- **Y（中）**: 細かな機能追加（既存画面への機能追加、新APIエンドポイント、新ページなど）
- **Z（右）**: バグ修正・軽微な変更（修正、リファクタリング、表示調整など）

## [0.9.1] - 2026-06-16

### Changed
- **Paygateスクリーンショット OCR**（`src/services/ocr/dedupe.py`, `src/services/ocr/parsers/paygate_screenshot.py`, `src/services/ocr_service.py`）
  - 取引番号・レシート番号が重複する行を自動で統合（スクロール重なり・半分だけ写ったキャプチャ対策）
  - 複数画像を一括解析した場合もジョブ内・既存 DB 行と突合して重複を除外
  - 重複時は項目が揃っている行（レシート番号・決済方法など）を優先して保持

## [0.9.0] - 2026-04-11

### Added
- **OCR・レシート解析機能**（`apps/admin-web/src/pages/ReceiptOcrPage.tsx`, `src/api/ocr_routes.py`, `src/services/ocr/`, `src/models/ocr.py`）
  - Paygate スクリーンショットと精算レシートの画像アップロード・PaddleOCR 解析
  - 年月別保存、CSV ダウンロード、確定フロー
  - 本部 CSV 突合 API/UI（列マッピング可変）
  - 自己申告（sales_reports）比較のプレースホルダ API
- **OCR 用 DB テーブル**（`alembic/versions/20260411a001_add_ocr_receipt_tables.py`）
- **運用 Runbook**（`docs/ops/OCR_RECEIPT_RUNBOOK.md`）

### Changed
- **nginx API timeout** を OCR 向けに 300s へ延長（`tools/nginx_vanzai_new.conf`）
- **pyproject.toml** に `pillow` と optional `ocr` 依存（paddlepaddle / paddleocr / opencv）を追加

## [0.8.0] - 2026-04-09

### Added
- **請求書発行の Kintone 参照 UI 拡張**（`src/api/main.py`, `src/api/schemas.py`, `src/services/invoice_service.py`, `src/services/pdf_generator.py`, `apps/admin-web/src/pages/InvoicesPage.tsx`）
  - `/api/invoices/generate` で `document_type`、`client_staff_id`、`subject`、`fixed_office_fee_amount`、`billing_date` を受け付けるようにした
  - 請求先担当者スナップショット、件名、帳票種別、固定事務局費を invoice に保持できるようにした
  - admin-web の請求生成フォームで帳票種別、担当者、件名、固定事務局費を指定できるようにした

### Changed
- **請求 PDF と請求一覧の表示を拡張**（`src/services/pdf_generator.py`, `apps/admin-web/src/types/api.ts`, `apps/admin-web/src/pages/InvoicesPage.tsx`）
  - PDF に請求先名、担当者名、住所、件名、帳票種別、請求日を表示するようにした
  - 固定事務局費を請求明細行へ追加し、請求一覧でも確認できるようにした

## [0.7.8] - 2026-04-08

### Added
- **プレイングマネージャー支払の個別設定対応**（`src/models/master.py`, `src/services/payout_service.py`, `apps/admin-web/src/pages/MasterDataPage.tsx`, `apps/admin-web/src/pages/PayoutsPage.tsx`）
  - VANZAI担当者マスタに `playing_manager_fee_type` と `playing_manager_fixed_fee` を追加
  - プレイングマネージャー支払で `配下人工×1,000円` と `固定額` を個人別に切り替え可能にした
  - 支払生成時に運営協力費を月次手入力で別行加算できるようにした

### Changed
- **VANZAI担当者支払生成ロジックを拡張**（`src/api/schemas.py`, `src/api/main.py`, `src/services/payout_service.py`）
  - `/api/payouts/generate` が `support_fee_amount` を受け付けるようにした
  - プレイングマネージャーの支払生成を backend で完結できるようにした

## [0.7.7] - 2026-04-08

### Added
- **VANZAI担当者支払の初回生成対応**（`src/services/payout_service.py`, `src/api/main.py`, `apps/admin-web/src/pages/PayoutsPage.tsx`）
  - `/api/payouts/generate` で `recipient_type=vanzai_staff` を受け付けるように変更
  - `全体統括責任者` は drv社請求税抜売上の 8% と linked worker の本人稼働分を1件に集約
  - `事務` は 固定43,200円 と 月内暦日 × 2,160円 の支払明細を自動生成

### Changed
- **VANZAI担当者マスタに linked worker 設定を追加**（`src/models/master.py`, `src/api/main.py`, `apps/admin-web/src/pages/MasterDataPage.tsx`）
  - VANZAI担当者と worker 実績主体を明示的に紐付けできるようにした
  - 全体統括責任者の linked worker は通常の worker 支払生成を抑止し、二重計上を防止

---

## [0.7.6] - 2026-04-09

### Added
- **supplier recipient の支払生成対応**（`src/api/main.py`, `apps/admin-web/src/pages/PayoutsPage.tsx`）
  - `/api/payouts/generate` で `recipient_type=supplier` を受け付けるように変更
  - PayoutsPage で取引先を選んで支払生成できるようにした
  - supplier 支払は案件指定不要であることを UI に明示

### Changed
- **DashboardPage のボタンとリンクをスタイル統一**（`apps/admin-web/src/pages/DashboardPage.tsx`）
  - 締め処理の選択ボタン群、監査ログ導線、月次一括生成などの素のボタンを `btn` 系スタイルへ統一
  - 締め候補の一括選択ボタンをチップ風デザインへ変更

---

## [0.7.5] - 2026-04-09

### Added
- **支払一覧の recipient_type UI 移行着手**（`apps/admin-web/src/pages/PayoutsPage.tsx`）
  - 一覧フィルタと種別表示を `recipient_type` 優先へ変更
  - 支払明細生成リクエストを `recipient_type` / `recipient_id` ベースへ更新
  - worker 以外の受取人生成は未対応であることを UI で明示し、誤操作を防止

### Changed
- **登録申請ページの主要アクションをスタイル統一**（`apps/admin-web/src/pages/RegistrationRequestsPage.tsx`）
  - `リンク発行`、`承認`、`却下`、`PINロック解除`、`リンク再発行` を強弱のある共通ボタンへ変更
  - 発行カードに装飾を追加し、操作部の視認性を改善

---

## [0.7.4] - 2026-04-09

### Fixed
- **公開登録リンク発行フォームのレイアウト修正**（`apps/admin-web/src/pages/RegistrationRequestsPage.tsx`）
  - 発行フォームを余白付きカードへ変更し、左端の文字が見切れる状態を解消
  - 入力欄の最小幅を上書きし、狭い幅でも崩れにくい表示へ調整

---

## [0.7.3] - 2026-04-09

### Added
- **admin-web 口座履歴 UI 改善**（`apps/admin-web`）
  - `WorkersPage` と `MasterDataPage` の振込先口座一覧で口座番号をマスキング表示に統一
  - worker / supplier 口座の新規登録・更新フォームに `有効終了日` を追加
  - 一覧テーブルに `有効終了` 列を追加し、履歴の終了日を確認可能にした
  - `有効終了日 < 有効開始日` を UI 側でバリデーション

## [0.7.2] - 2026-04-09

### Added
- **Phase 1 DBマイグレーション適用完了**（`20260408c001` ～ `20260408e001`）
  - `project_types`: `category_level`（major/middle/minor）・`parent_id` 自己参照FK 追加
  - `payout_lines`: `recipient_type`・`payee_name_snapshot`・`bank_account_snapshot_json` フィールド追加
  - `project_documents`・`project_tasks`・`sales_reports` テーブル新規追加
- **API エンドポイント追加**（`src/api/main.py`・`src/api/schemas.py`）
  - `GET/POST/PUT /api/vanzai-staff` — VANZAI担当者マスタ CRUD
  - `GET/POST/PUT /api/clients/{client_id}/staff` — クライアント担当者 CRUD
  - `GET/POST/PUT /api/workers/{worker_id}/bank-accounts` — 稼働者振込先口座 CRUD
  - `GET/POST/PUT /api/suppliers/{supplier_id}/bank-accounts` — 下請け振込先口座 CRUD
- **admin-web UI 追加**（`apps/admin-web`）
  - マスタ一覧 → 「VANZAI担当者」タブ追加（作成・編集対応）
  - マスタ一覧 → クライアント行に「担当者管理」パネル追加（担当者一覧・追加）
  - 稼働者ページ編集パネルに「振込先口座」セクション追加（口座一覧・新規登録フォーム）
- **型定義追加**（`apps/admin-web/src/types/api.ts`）
  - `VanzaiStaffItem/CreateRequest/UpdateRequest`
  - `ClientStaffItem/CreateRequest/UpdateRequest`
  - `WorkerBankAccountItem/ListResponse/CreateRequest/UpdateRequest`
  - `SupplierBankAccountItem/ListResponse/CreateRequest/UpdateRequest`

---

## [0.7.1] - 2026-04-08

### Added
- **公開登録フォーム UI** (`/public/registrations/:formType`)
  - token + PIN による本人確認パネル
  - 4フォーム種（稼働者・個人下請け/紹介者・法人下請け・紹介者身分証）に対応した動的フィールド
  - ログイン不要のアンオーセンティケートルートとして App.tsx に追加
- **身分証ファイルアップロード**（`POST /public/registrations/{form_type}/files`）
  - document_type / document_part 指定、MIME・サイズ検証、SHA256 保存
  - 同一種類/部位の旧ファイルをソフトデリート（1件1種類1部位）
  - 監査ログ: `registration_request_file_uploaded`
- **管理者ファイルダウンロード**（`GET /api/registration-requests/{request_id}/files/{file_id}`）
  - 閲覧理由（`reason`）必須クエリパラメータ
  - 監査ログ: `registration_request_file_downloaded`
  - 承認/却下後 180 日保持ポリシー適用
- **dedupe 差分比較表示**（`RegistrationRequestsPage`）
  - 申請値 vs 既存マスタ値を項目ごとに色分けハイライト（一致: 緑 / 不一致: 赤）
  - 対象フィールド: 氏名・ふりがな・電話・メール・屋号・性別・インボイス番号 など

---

## [0.6.9] - 2026-04-07

### Added
- **公開登録フォーム バックエンド**
  - `registration_requests` テーブルを正本とした受付ドメイン実装
  - token 発行・PIN 設定・PIN ロック（5回失敗）・ロック解除・再発行 API
  - 4フォーム種の submit エンドポイント（稼働者・個人・法人・紹介者身分証）
  - dedupe 候補検索（氏名+電話、メールなどで既存 workers/suppliers を照合）
- **管理画面: 登録申請管理** (`/operations/registration-requests`)
  - 申請一覧・詳細表示
  - 承認（master INSERT/UPDATE）・却下アクション
  - dedupe 候補一覧と承認対象選択 UI
  - 公開リンク発行・再発行・PIN ロック解除

---

## [0.6.8] - 2026-04-04

### Added
- **ブラウザキャッシュ対策**（`tools/vite-plugin-version-check.ts`）
  - ビルド時に `dist/version.json` を生成し `index.html` にインラインスクリプト埋め込み
  - バージョン不一致を自動検知して `location.replace` でキャッシュバイパス
  - `window.__APP_VERSION__` / `window.__APP_BUILD_ID__` を React コンポーネントに公開
- **プッシュ通知改善**（`PersonalSettingsPage`）
  - 工程別プログレス表示・タイムアウト対応
  - 通知拒否時のブラウザ別解除手順表示

---

## [0.6.7] - 2026-04-03

### Added
- **稼働可否カレンダー管理画面** (`/operations/availability-calendar`)
  - 管理者向けスタッフ横断カレンダー（月/週トグル）
  - スタッフ行にスキル資格バッジを折りたたみ表示
  - `GET /api/availability-calendar` バックエンドエンドポイント
- **Worker スキル資格フラグ** (`workers` テーブル)
  - `smoking_area_ok`, `has_p_shirt`, `has_best`, `stores_training_done`, `pioneer_training_done` 追加
  - staff-mobile 個人設定ページから更新可能
- **staff-mobile ステータスバンド** (`MobileStatusBand`)
  - 今日のアサイン・未返答・実績・稼働可否・設定を上部バンドで一覧表示

---

## [0.6.6] - 2026-04-01

### Added
- **アサイン返答モニタリング** (`/operations/assignment-responses`)
  - 返答未回収アサインの一覧・フィルタ（月・案件・スタッフ・エスカレーション）
  - 手動リマインダー再送 (`POST /api/assignments/reminders/send`)
  - リマインダー履歴・エスカレーション履歴パネル
- **週次スケジューラー**: 未返答アサインへのリマインダーメール自動送信
- **お知らせ機能** (`/operations/notices`, staff-mobile `/notices`)
  - 管理者 → スタッフへのお知らせ CRUD
  - staff-mobile 未読バッジ表示
- **支払明細 メール送付改善**
  - 送付履歴パネル（受取人候補チップ・送付先オーバーライド）
  - `GET /api/payouts` に `delivery_state=unsent|failed` フィルタ追加
  - ダッシュボードに `missing_payout_recipient` カウント追加

---

## [0.6.5] - 2026-03-31

### Added
- **案件・シフト枠 編集** (PUT /api/projects/{id}, PUT /api/shift-slots/{id})
- **アサイン 高度化**
  - 一括ステータス更新・キャンセル→再開
  - `reopen_reason` 必須（監査ログ記録）
  - 月次キャンセル履歴 (`GET /api/assignments/cancellation-history`)
  - サーバー側選択セット保存 (`GET/POST/DELETE /api/assignments/selection-sets`)
- **スタッフ稼働可否管理** (staff-mobile `/availability`, admin-web 参照)
- **worker assignment response** (staff-mobile 承認・辞退アクション + 未返答バッジ)

---

## [0.6.4] - 2026-03-30

### Added
- **staff-mobile** 初期リリース
  - `/today` 今日のアサイン・出退勤打刻
  - `/schedule` 月次スケジュール
  - `/actuals` 実績一覧
  - `/expenses` 経費申請・添付レシート
  - `/settings` 個人設定
- **経費管理** admin-web (`/billing/expenses`)
  - 承認・却下・レシートダウンロード
  - `ObjectStorage` 経由での添付ファイル保存

---

## [0.6.3] - 2026-03-28

### Added
- **マスタ管理** admin-web 拡張 (`/masters/data`, `/masters/workers`)
  - Worker・Supplier の作成・編集
  - クライアント・現場・案件種別・役割 の作成
- **単価管理** admin-web (`/masters/prices`)
  - price_rules / price_sales / price_outsource の作成・編集

---

## [0.6.2] - 2026-03-26

### Added
- **請求書・支払明細 PDF** 生成・保存・メール送信
- **支払明細 paid 更新** (`POST /api/payouts/{id}/paid`)
- **請求書・支払明細 監査ログ** 一括クイックフィルタ追加

---

## [0.6.0] - 2026-03-24

### Added
- **ダッシュボード** 月次・案件別 締め管理（ソフト/ハードクローズ・解除）
- **CSV インポート** (`/operations/csv-import`)
  - 洗い替えモード・バッチ履歴・エラープレビュー
- **監査ログ** 全文検索・クイックフィルタ・監査対象の名称解決
- **単価スナップショット** と締め後の再計算ガード

