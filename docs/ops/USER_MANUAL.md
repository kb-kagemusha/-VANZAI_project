# ユーザー向け運用マニュアル（VANZAI）

## 目的
日次〜月次の実務担当者が、Kintoneと本システムを使って迷わず運用できる最短手順をまとめる。

## 対象ロール
- Ops（運用担当）
- Accounting（経理担当）
- Admin（管理者）

## 1. 月次運用の全体フロー
1. 実績CSVの提出状況確認
2. CSV取り込み（洗い替え）
3. 差分アラート確認
4. 請求書生成・レビュー・発行
5. 支払明細生成・承認
6. 締め処理（Soft/Hard）

詳細は [RUNBOOK_MONTHLY.md](../../RUNBOOK_MONTHLY.md) を参照。

## 2. 日次/週次の基本操作
### 日次
- Kintoneで案件・稼働者・実績の登録/修正
- エラー差戻しの対応（CSV不備、紐付け不備）

### 週次
- 未提出CSVの催促（スケジューラー通知の確認）
- 未処理一覧（ダッシュボード）を消し込む

## 3. App174（見積書・請求書の発行）の使い方
### 3.1 画面遷移
- ポータル → 登録ダッシュボード（App174）
- 「確認」行の「見積書・請求書の発行」を選択

### 3.2 クライアント向け発行
- 発行対象: 依頼者（クライアント）
- 帳票種別: 見積書/請求書
- 件名: `◯年◯月分_` を入力
- 固定事務局費: 必要な場合のみ手入力（0以上）

### 3.3 下請け/紹介者向け支払明細
- 発行対象: 下請け または 紹介者
- 紹介者向けは `via_destination=紹介` の稼働者のみ対象
- 一括ZIPは対象月のPDF添付がある明細のみ出力

## 4. 稼働者（App165）入力ルール
- `via_destination` は必須（`下請け` / `紹介` / `VANZAI直接`）
- `VANZAI直接` の場合、「紹介者/下請け」は空欄・入力不可
- `VANZAI直接` 以外は「紹介者/下請け」必須

## 5. よくある作業ミスと回避
- フィールドコードを変更しない（連携破損の原因）
- 締め後データを直接更新しない
- 再取り込みは `REPLACE_SCOPE` を使い二重化を防ぐ

## 6. 参照ドキュメント
- [RUNBOOK_MONTHLY.md](../../RUNBOOK_MONTHLY.md)
- [RUNBOOK_WEEKLY.md](../../RUNBOOK_WEEKLY.md)
- [PUSH_NOTIFICATION_RUNBOOK.md](./PUSH_NOTIFICATION_RUNBOOK.md)
- [docs/kintone/FRONT_DASHBOARD_SETUP.md](../kintone/FRONT_DASHBOARD_SETUP.md)
- [docs/IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md)

## 更新履歴
- 2026-02-16: 初版作成（ドキュメント残タスク対応）
