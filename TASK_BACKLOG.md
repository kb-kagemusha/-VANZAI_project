# TASK_BACKLOG (MVP→拡張)

**注記**: 本ドキュメントはMVP時点の計画バックログです。実装タスクは完了済みのため、進捗管理は完了報告を参照してください。
- 完了報告: docs/COMPLETION_REPORT_2026-01-30_FINAL.md
- 最終サマリー: docs/FINAL_SUMMARY_2026-01-30.md

## 0. MVPのゴール
- CSV取り込み→実績確定→請求書発行→支払明細発行→締め までを月次で回せる
- 二重払い、売上漏れ、締め後改変をテストで防げる

## 1. Epic一覧（優先順）

### E1 データモデル/制約
**状態**: 完了
- DDL/マイグレーション作成
- 主要ユニーク制約とFK整備
- 物理削除禁止（soft delete / status）

Acceptance
- 主要テーブルが作成できる
- 破綻シナリオ（重複、宙づり）がDB制約とアプリで防がれる

### E2 CSV取り込み（部分取り込み・二重化防止）
**状態**: 完了
- import_batch と errors_json の実装
- 洗い替えモード（範囲無効化→投入）
- 重複検知（同日×案件×稼働者×時間帯の衝突）
- 差戻しフローに必要な出力（行番号、理由、キー）

Acceptance
- 時刻修正の再取り込みで二重化しない
- エラー行が一覧化され、成功分は確定できる

### E3 時間計算ルール（丸め・休憩・端数）
**状態**: 完了
- project/rule に time_calc_mode, rounding_unit, rounding_method, break_rule
- 適用結果の保存（hours_applied, break_applied 等）

Acceptance
- 現場運用と同じ計算結果になる
- ルール変更が過去に遡及しない（締め後固定）

### E4 単価決定とスナップショット
**状態**: 完了
- assignment/actual に applied_price_* を保存
- 再計算は対象期間/案件を明示指定
- 締め前/締め後の境界を強制

Acceptance
- マスタ変更後も過去の金額が変わらない
- 再計算の影響範囲が限定される

### E5 請求（invoice）
**状態**: 完了
- invoice/version/parent_invoice_id
- invoice_line 明細正本
- PDF生成と保管（storage_key）
- 訂正/再発行の判断基準を実装（ルール化）

Acceptance
- 発行済み請求の上書きができない
- 旧版と新版が残る

### E6 支払（payout）
**状態**: 完了
- payout/version/parent
- payout_line 明細
- 訂正の扱い

Acceptance
- 支払確定後の改変ができない

### E7 締め/締め解除ガードレール
**状態**: 完了
- 解除可能期間、回数上限、二者承認、再締め期限
- 解除履歴画面/一覧

Acceptance
- 解除乱用が検知/抑止される
- 放置されない

### E8 ダッシュボード（次の一手）
**状態**: 完了
- 未確定シフト、未提出CSV、取込残件、請求未発行、支払未確定、差分アラート
- 一覧から担当者へのアクション導線

Acceptance
- 数字ではなく「誰に何をすればいいか」が1画面で分かる

### E9 権限（Ops / Site Manager / Accounting / Admin）
**状態**: 完了
- 操作可能一覧を仕様として固定
- 画面とAPIに権限制御

Acceptance
- 役割を跨いだ誤操作ができない

### E10 RUNBOOK/テンプレート
**状態**: 完了
- 月次/週次チェックリスト
- 催促メールテンプレ
- エラー差戻しテンプレ

Acceptance
- RUNBOOKだけで運用が回る

