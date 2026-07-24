# api_structure.md

> **更新**: 2026-06-10 — `src/api/main.py` コード照合により正本パスを反映。

## 1. API一覧（機能群）
- 認証
- ダッシュボード
- アサイン/予定返信・催促
- 実績/打刻
- 稼働可否
- 経費
- 案件/シフト
- CSV取込/取込履歴
- 請求/支払/送信履歴
- 締め/解除
- マスタ管理
- 登録申請（管理 + 公開）
- 監査ログ
- スタッフ通知/Push
- 集計（sales/outsource）

## 2. エンドポイント一覧（主要）
正本: `src/api/main.py`（**100エンドポイント**）。`main_simple.py` は開発用スタブ（5 EP、認証なし）。

### 2.1 認証
- POST /api/auth/token
- GET /api/auth/me
- POST /api/auth/change-password
- PUT /api/auth/profile

### 2.2 運用基盤
- GET /api/dashboard
- GET /api/health（公開）
- GET /（公開）

### 2.3 アサイン・実績
- GET/POST /api/assignments
- PUT /api/assignments/{id}
- POST /api/assignments/{id}/status
- POST /api/assignments/status/bulk
- POST /api/assignments/{id}/worker-response
- POST /api/assignments/{id}/check-in
- POST /api/assignments/{id}/check-out
- GET /api/assignments/selection-sets
- POST /api/assignments/selection-sets
- DELETE /api/assignments/selection-sets/{id}
- POST /api/assignments/reminders/send
- POST /api/assignments/reminders/history
- POST /api/assignments/reminders/escalate
- POST /api/assignments/reminders/escalations/history
- GET /api/assignments/cancellation-history
- GET /api/actuals

### 2.4 稼働可否
- GET/POST /api/worker-availability
- GET/PUT /api/worker-availability/preferences
- GET /api/workers/{worker_id}/availability-preferences（MASTER_READ）
- GET /api/availability-calendar

### 2.5 案件・シフト
- GET/POST /api/projects
- PUT /api/projects/{id}
- PATCH /api/projects/{id}/notes
- GET/POST /api/shift-slots
- PUT /api/shift-slots/{id}
- PATCH /api/shift-slots/{id}/notes

### 2.6 CSV取込
- POST /api/csv/import（Base64 JSON）
- POST /api/csv/upload（multipart）
- GET /api/import-batches

※ 旧表記 `POST /api/csv-import` は**未実装**（互換エイリアスなし）

### 2.7 請求・支払
- GET /api/invoices
- POST /api/invoices/generate
- POST /api/invoices/{id}/issue
- GET /api/invoices/{id}/pdf
- GET /api/payouts
- POST /api/payouts/generate
- POST /api/payouts/{id}/confirm（承認）
- POST /api/payouts/{id}/paid
- POST /api/payouts/{id}/deliver
- GET /api/payouts/{id}/deliveries
- GET /api/payouts/{id}/pdf
- POST /api/billing/generate-monthly（請求+支払一括）

※ 旧表記 `POST /api/invoices`, `POST /api/payouts`（生成なし）は**未実装**

### 2.8 締め（正本パス）
- POST /api/closing/soft
- POST /api/closing/hard
- POST /api/closing/soft/release
- POST /api/closing/hard/release

リクエストは `project_id` + `period_key` ベース（旧 `/api/closings/{id}/release` 形式は**未実装**）

### 2.9 集計
- GET /api/aggregation/sales
- GET /api/aggregation/outsource

**注意**: 現状認証・権限チェックなし（`CODE_VERIFIED_GAPS.md` G-005）

### 2.10 マスタ
- workers / suppliers / clients / sites / project-types / project-types/tree / roles / vanzai-staff
- client-staff / bank-accounts（worker, supplier）
- price-rules / price-sales / price-outsource

### 2.11 登録申請
**管理側**（JWT + MASTER_READ/WRITE）:
- POST /api/registration-links
- GET /api/registration-requests
- POST /api/registration-requests/{id}/approve|reject
- GET /api/registration-requests/{id}/files/{file_id}

**公開側**（token + PIN、JWT 不要）:
- GET /public/registrations/{form_type}
- POST /public/registrations/{form_type}/files
- POST /public/registrations/worker
- POST /public/registrations/supplier-individual
- POST /public/registrations/supplier-corporation
- POST /public/registrations/introducer-identity

### 2.12 監査・通知
- POST /api/audit/search（**正本**。`GET /api/audit-logs` は未実装）
- GET/POST/DELETE /api/notices
- GET /api/worker/notices
- POST /api/worker/notices/{id}/read
- POST /api/worker/notices/{id}/respond
- GET /api/worker/push/vapid-public-key
- POST/DELETE /api/worker/push/subscribe

## 3. 認証要否
- 原則: /api 配下は認証必須
- 例外:
  - GET /, GET /api/health は公開
  - /public/registrations/* は token+PIN 認証（JWT 不要）
  - GET /api/aggregation/* は現状**認証なし**（要修正）
- 認可は role + Permission enum で強制

## 4. リクエスト形式
- JSONが基本
- 認証は application/x-www-form-urlencoded（OAuth2 Password Form）
- ファイル系は multipart/form-data
  - CSV取込（/api/csv/upload）
  - 経費領収書
  - 登録申請添付

## 5. レスポンス形式
- 一覧系の共通形:
  - items
  - total
  - offset
  - limit
- 単体系:
  - ドメイン項目（id/status/timestamps等）
- ファイルDL:
  - binary + Content-Disposition

## 6. 共通処理
- 依存性注入: get_db でリクエスト単位セッション
- 認証依存: get_current_user / get_current_active_user
- 権限判定: check_permission / has_permission
- プロジェクトスコープ: can_access_project（site_manager / worker）
- 監査記録: AuditService でイベントログ化
- 月次規約: period_key(YYYYMM) による期間指定

## 7. エラーハンドリング方針
- ドメイン例外は VANZAIException 系で表現
- API層で JSON 化:
  - error_code
  - message
  - detail
- 認証失敗: 401
- 権限不足: 403
- 業務ルール違反: 400 系

## 8. 設計上の特徴
- APIは画面都合で結合しすぎず、業務単位で分割
- 一覧系は表示に必要な関連名をAPIで解決し、フロントの過剰joinを避ける
- 送信・発行系は履歴保存を前提とし、再送・再発行を業務操作として扱う
- ルート登録は `main.py` にモノリシック（APIRouter 未使用）

## 9. 移植時の推奨
- まず /api/auth, /api/dashboard, /api/actuals, /api/invoices/generate, /api/payouts/generate を最小移植
- 次に /api/closing/* + /api/audit/search + payout deliveries を追加
- 最後に notices/push / registration を導入

## 10. 旧パス対応表（ドキュメント修正用）

| 旧表記（誤） | 正本（コード） |
|-------------|---------------|
| POST /api/csv-import | POST /api/csv/import または /api/csv/upload |
| POST /api/closings/soft | POST /api/closing/soft |
| POST /api/closings/{id}/release | POST /api/closing/soft/release |
| GET /api/audit-logs | POST /api/audit/search |
| POST /api/payouts/{id}/approve | POST /api/payouts/{id}/confirm |
| POST /api/payouts/{id}/mark-paid | POST /api/payouts/{id}/paid |
| GET /api/payout-deliveries | GET /api/payouts/{id}/deliveries |
