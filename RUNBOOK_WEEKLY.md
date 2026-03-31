# RUNBOOK_WEEKLY

## 目的
- 未確定シフトと期限超過タスクを早めに潰し、月末の爆発を防ぐ

## 自動実行（スケジューラー）

### 週次催促メール
- **実行日時**: 毎週月曜9:00
- **実行内容**: worker の未回答予定確認にリマインドメール送信
- **対象**: `assignments.worker_response_status = pending` かつ対象期間内の upcoming assignment
- **設定**: `EMAIL_DRY_RUN=false` で本番送信、`=true` でログ出力のみ
- **環境変数**: 
  - `SCHEDULER_WEEKLY_DAY=0`（0=月曜、1=火曜、...、6=日曜）
  - `SCHEDULER_WEEKLY_HOUR=9`（時刻: 9:00）
  - `SCHEDULER_WEEKLY_LOOKAHEAD_DAYS=14`（催促対象に含める先の日数）
  - `ASSIGNMENT_RESPONSE_ESCALATION_DAYS_BEFORE_WORK=2`（dashboard で要エスカレーションに切り替える稼働日接近の閾値）
  - `ASSIGNMENT_RESPONSE_ESCALATION_HOURS_SINCE_REQUEST=72`（dashboard で要エスカレーションに切り替える依頼経過時間の閾値）
  - `ASSIGNMENT_RESPONSE_ESCALATION_EMAILS=ops@example.com,admin@example.com`（管理者通知先を固定したい場合の上書き。未設定時は admin / ops / accounting の active user を使用）
- **メールテンプレート**: `EmailTemplateService.assignment_response_reminder()`

### Dry run 手順
1. `EMAIL_DRY_RUN=true` を設定する
2. 必要なら `EMAIL_PROVIDER` と `SCHEDULER_WEEKLY_LOOKAHEAD_DAYS` を本番相当に合わせる
3. `c:/VANZAI_project/.venv/Scripts/python.exe scripts/scheduler_runner.py --run-once weekly_reminder` を実行する
4. ログで対象件数、送信件数、失敗件数、missing email の件数を確認する

## 手動確認（Ops）

### 毎週金曜
- 翌週の未確定シフト枠を確認
- 未確定が残る案件を抽出
- Site Managerへ催促送信（自動送信ログを確認）
- 未応答が続く案件はAdminへエスカレーション

### 毎週月曜
- 週次催促メールの送信ログを確認
- 未回答予定確認の件数と、メール未設定 worker の有無を確認
- admin-web ダッシュボードで「予定確認未回答」「要エスカレ」の件数と条件列を確認
- admin-web の「予定確認監視」画面で「直近催促履歴」を確認し、誰にいつ再送したかを確認する
- admin-web の「予定確認監視」画面から必要な assignment を選び、手動再送を実行する
- 要エスカレーション行は row 単位または複数選択で「管理者へ通知」を実行し、通知結果の recipient 数と sent / failed 件数を確認する
- 期限超過タスクの確認
- 期限超過の担当者へリマインド
- スケジューラーの実行ログをチェック

## トラブルシューティング

### 催促メールが送信されない場合
1. EMAIL_DRY_RUN が true になっていないか確認
2. SMTP設定が正しいか確認（.env ファイル）
3. スケジューラーが起動しているか確認
4. ログを確認: `logger.info("Weekly reminder...")`

### メール送信エラーが発生する場合
1. SMTP_PASSWORD が正しいか確認
2. Gmail App Password を使用しているか確認（通常パスワードは不可）
3. EMAIL_PROVIDER が正しいか確認（gmail/sendgrid/ses）
4. ファイアウォールでSMTPポート（587）がブロックされていないか確認

