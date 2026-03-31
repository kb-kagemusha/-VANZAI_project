# RUNBOOK_WEEKLY

## 目的
- 未確定シフトと期限超過タスクを早めに潰し、月末の爆発を防ぐ

## 自動実行（スケジューラー）

### 週次催促メール
- **実行日時**: 毎週月曜9:00
- **実行内容**: CSV未提出者にリマインドメール送信
- **対象**: DashboardServiceで取得した csv_missing 項目
- **設定**: `EMAIL_DRY_RUN=false` で本番送信、`=true` でログ出力のみ
- **環境変数**: 
  - `SCHEDULER_WEEKLY_DAY=0`（0=月曜、1=火曜、...、6=日曜）
  - `SCHEDULER_WEEKLY_HOUR=9`（時刻: 9:00）
- **メールテンプレート**: EmailTemplateService.csv_unsubmitted_reminder()

## 手動確認（Ops）

### 毎週金曜
- 翌週の未確定シフト枠を確認
- 未確定が残る案件を抽出
- Site Managerへ催促送信（自動送信ログを確認）
- 未応答が続く案件はAdminへエスカレーション

### 毎週月曜
- 週次催促メールの送信ログを確認
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

