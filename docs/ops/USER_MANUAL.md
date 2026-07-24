# ユーザー向け運用マニュアル（VANZAI）

## 目的
日次〜月次の実務担当者が、**管理画面（admin-web）** と本システム API を使って迷わず運用できる最短手順をまとめる。

## 対象ロール
- Ops（運用担当）
- Accounting（経理担当）
- Admin（管理者）

## 利用画面
- **管理画面**: https://vanzai-portal.com （マスタ・案件・請求・支払・CSV取込）
- **スタッフ向け**: https://staff.vanzai-portal.com

## 1. 月次運用の全体フロー
1. 実績CSVの提出状況確認
2. CSV取り込み（洗い替え）— 管理画面の「CSV取込」
3. 差分アラート確認
4. 請求書生成・レビュー・発行
5. 支払明細生成・承認・送信
6. 締め処理（Soft/Hard）

詳細は [RUNBOOK_MONTHLY.md](../../RUNBOOK_MONTHLY.md) を参照。

## 2. 日次/週次の基本操作
### 日次
- 管理画面で案件・稼働者・実績の登録/修正
- エラー差戻しの対応（CSV不備、紐付け不備）

### 週次
- 未提出CSVの催促（スケジューラー通知の確認）
- 未処理一覧（ダッシュボード）を消し込む

## 3. 見積書・請求書の発行（管理画面）
### 3.1 画面遷移
- 管理画面 → 「請求」メニュー → 請求一覧
- 「請求生成」から対象月・案件を選択して生成

### 3.2 クライアント向け発行
- 帳票種別: 見積書 / 請求書
- 件名・固定事務局費は生成フォームで入力
- 発行後、PDF をダウンロードまたはメール送信

### 3.3 下請け/紹介者向け支払明細
- 「支払」メニューから支払明細を生成・確定
- 紹介者向けは `via_destination=紹介` の稼働者が対象
- 送信履歴・再送は支払一覧の履歴パネルから操作

## 4. 稼働者マスタ入力ルール
- `via_destination` は必須（`下請け` / `紹介` / `VANZAI直接`）
- `VANZAI直接` の場合、紹介者/下請けは空欄
- `VANZAI直接` 以外は紹介者/下請け必須

## 5. よくある作業ミスと回避
- 締め後データを直接更新しない
- 再取り込みは洗い替えモードを使い二重化を防ぐ
- 送信先メール未設定の支払は、支払一覧のフィルタで先に洗い出す

## 6. 参照ドキュメント
- [RUNBOOK_MONTHLY.md](../../RUNBOOK_MONTHLY.md)
- [RUNBOOK_WEEKLY.md](../../RUNBOOK_WEEKLY.md)
- [PUSH_NOTIFICATION_RUNBOOK.md](./PUSH_NOTIFICATION_RUNBOOK.md)
- [docs/ops/REACT_MIGRATION_PLAN_2026-03-31.md](./REACT_MIGRATION_PLAN_2026-03-31.md)
- [docs/IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md)

## 更新履歴
- 2026-07-24: Kintone 運用記述を廃止し、admin-web 前提に更新
- 2026-02-16: 初版作成（ドキュメント残タスク対応）
