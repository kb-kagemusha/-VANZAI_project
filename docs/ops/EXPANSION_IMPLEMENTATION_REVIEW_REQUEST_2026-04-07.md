# VANZAI 追加要件 実装計画 レビュー依頼文

更新日: 2026-04-07

## 1. 他 AI への依頼文
以下の実装計画について、問題点がないか厳しめにレビューしてください。

対象は、Kintone で先行運用している追加機能を、既存の FastAPI + PostgreSQL + admin-web + staff-mobile に段階導入する計画です。主眼は全面再構築ではなく、既存基盤を活かした追加実装計画の妥当性レビューです。

レビュー対象の主な追加要件は以下です。
- クライアント職員
- VANZAI 職員
- Supplier 区分（紹介者 / 下請け、個人 / 法人）
- Worker の詳細登録情報と銀行口座履歴
- 公開登録フォーム 4 本
- 管理画面 dashboard の「お知らせ」
- staff-mobile の出退勤打刻
- staff-mobile の販売台数報告
- 案件種別ごとの説明資料添付
- 案件タスク管理
- 月次 + 案件種別別の簡易 PL
- 個人成績表

すでに確定している前提は以下です。
- Supplier の区分は追加する
- Worker の銀行口座管理は Phase 1 で追加し、`worker_bank_accounts` で履歴管理する
- Project と VANZAI 職員の紐付けとして `projects.vanzai_manager_id` を追加する
- 公開登録フォームは 4 URL に分ける
- 公開登録フォームはログイン不要だが、4 桁 PIN 付き URL で公開する
- 出退勤は staff-mobile 内に実装する
- 簡易 PL は月次 + 案件種別ごとに集計する
- request は不変の受付記録、master は承認後の現在値として分離する
- request モデルは共通ヘッダ + 種別別詳細テーブルを前提とする
- payout は `recipient_type` / `recipient_id` と受取人スナップショットを正本とし、既存 `worker_id` / `supplier_id` から backfill する
- `supplier_type` は Phase 1 では supplier 側の単一属性として扱う
- VANZAI 職員と認証ユーザーの紐付けは `users.vanzai_staff_id` で持つ
- `source_type` は `public_form` / `admin_proxy` / `api_import` / `internal_create` に固定する
- `sales_reports` は immutable + 再提出方式を前提とする
- `sales_reports` の現行正本は `superseded_by_id IS NULL AND status='approved'` とし、訂正申請中は旧 approved 版を維持する
- 簡易 PL は確定値と予測値を併記し、確定値は invoice / payout / expenses / incentives、予測値は Assignment ベースを使う
- 個人成績の遅刻は開始時刻から 15 分超過で 1 回とする
- 公開リンクの有効期限は 7 日、PIN は 5 回失敗でロックし、管理者は reset / 再発行の両方を実行可能とする
- 身分証ファイルは承認 / 却下後 180 日保持し、accounting を削除責任者とする
- request detail は原文保存を優先し、承認時に master へ正規化する
- `registration_request_files.document_type` は `driver_license` / `my_number_card` / `residence_card` / `passport` / `other` で開始する
- supplier 口座は Phase 1 で `supplier_bank_accounts` を追加し、過去支払の再現性も必須とする
- project_type は leaf（minor）のみ案件へ付与し、既存 flat 種別は migration で major 化して直下に minor を新設する
- 自動生成 minor の表示名は `major名 + （標準）`、code は `既存 major code + -DEFAULT` とする
- admin-notices は `target_url` / `is_read` / `is_resolved` を持つ未処理キューとし、対象は request 未審査、身分証未確認、sales_reports 未承認、期限超過 project_tasks、payout エラーとする
- approve / reject は transaction 内で冪等かつ排他的に処理する前提とする
- `admin-notices` は件数箱ではなく未処理キューの入口として設計する

見てほしいのは実装コードではなく、計画そのものの妥当性です。特に次の観点で、抜け漏れ、順序の問題、設計上の危険、運用上の事故リスクを指摘してください。

1. フェーズ順序は妥当か
2. データモデルの切り方に問題はないか
3. `workers` / `suppliers` / `projects` / `vanzai_staff` / request テーブル群の責務分離は妥当か
4. 公開フォームを request テーブルで受けて承認後に本マスタへ反映する設計は妥当か
5. 4 桁 PIN 付き token 発行 URL のリスクは許容範囲か。追加すべき制御は何か
6. 身分証アップロードの扱いに不足はないか
7. `projects.vanzai_manager_id` と既存 manager 系カラムの併存で問題が起きないか
8. dashboard の「お知らせ」に未処理通知を集約する方針は妥当か
9. staff-mobile に出退勤と販売報告を載せる順序は妥当か
10. 簡易 PL と個人成績の正本定義に不足はないか
11. payout recipient モデルと口座スナップショット設計に不足はないか
12. `supplier_type` を相手属性で持つ設計が妥当か、それとも案件関係属性にすべきか
13. `registration_requests` detail テーブルの切り方と dedupe 定義に不足はないか
14. `registration_request_files` の file type 設計と身分証の技術制御に不足はないか
15. `sales_reports` の訂正 / supersede 運用に不足はないか
16. approve / reject API の冪等性・排他設計に不足はないか
17. DB 制約と index 方針に不足はないか
18. `admin-notices` を未処理キューの入口として扱う設計が妥当か
19. 手戻りが大きそうな箇所はどこか
20. 先に確定すべき未決事項が残っていないか

可能なら、次の形式で返してください。

1. 重大な懸念点
2. 優先的に修正すべき点
3. このまま進めてよい点
4. 将来の手戻りリスク
5. 追加で確認すべき質問

## 2. 計画の要約

### フェーズ
1. 設計凍結
2. データモデル拡張
3. バックエンド API
4. admin-web
5. 公開フォーム 4 本
6. staff-mobile
7. 分析 / 高度化

### 主要なモデル変更
- workers に登録詳細・インボイス情報を追加
- worker_bank_accounts を新設し、口座履歴を管理
- suppliers に supplier_type / entity_type を追加
- 必要に応じて supplier role を案件関係モデルへ拡張できる前提を置く
- projects に `vanzai_manager_id` を追加
- users に `vanzai_staff_id` を追加
- client_staff, vanzai_staff を新設
- registration_requests 共通ヘッダ + 種別別 detail テーブル + 身分証ファイルテーブルを新設
- payouts に recipient_type と受取人スナップショットを追加
- project_type_documents, project_tasks, sales_reports を新設

### 主要な UI 変更
- admin-web に clients, vanzai-staff, registration-requests, PL, worker-performance を追加
- dashboard に「お知らせ」欄を追加
- 公開フォーム 4 URL を追加
- staff-mobile に出勤 / 退勤と販売報告を追加

### セキュリティ方針
- 公開フォームは個別 token + 4 桁 PIN + 有効期限
- PIN 試行回数制限
- 身分証ファイルは保存先分離
- ロック解除 / URL 再発行手順を持つ
- 振込口座情報はマスキング表示
- 閲覧 / 承認 / ダウンロードは監査ログ記録

### 実装運用方針
- approve / reject は transaction 内で二重実行されても整合性が崩れない前提
- `admin-notices` は summary ではなく優先度付き未処理キューの入口とする

## 3. レビュー時に特に見てほしいポイント
- request テーブル方式が過剰か不足か
- request を共通ヘッダ + detail にした設計が妥当か
- supplier role を supplier 側へ持つか案件関係で持つか
- 公開フォームと本マスタの責務分離が妥当か
- `vanzai_manager_id` の導入が既存 project 管理と衝突しないか
- payout recipient と受取人スナップショット設計が妥当か
- detail テーブルのスキーマ粒度と dedupe キー定義が妥当か
- 身分証ファイルの技術制御が十分か
- sales_reports の immutable 訂正運用が妥当か
- approve / reject API の排他・冪等性設計が妥当か
- DB 制約 / partial unique / index 方針が妥当か
- `admin-notices` を未処理キューとして設計する粒度が妥当か
- 個人情報 / 身分証の扱いが甘くないか
- PL / 個人成績の集計定義が曖昧でないか
- この計画を 1PR = 1テーマ に分解しやすいか

## 4. 補足
レビュー対象の計画書本文は [EXPANSION_IMPLEMENTATION_PLAN_2026-04-07.md](./EXPANSION_IMPLEMENTATION_PLAN_2026-04-07.md) を参照してください。