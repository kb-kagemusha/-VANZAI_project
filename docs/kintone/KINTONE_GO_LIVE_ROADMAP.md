# Kintone稼働開始ロードマップ（v0.3）

## 目的
Kintoneを正本とした実運用、または実運用前の稼働テスト開始までの最短ステップと合否基準を固定する。

## 対象範囲
- 仕様正本: DESIGN_SPEC_v0.3
- Kintone構成: KINTONE_APPS_LIST / REQUIRED_APPS_FIELDS
- 進捗: KINTONE_PROGRESS_REPORT
- 運用: RUNBOOK_MONTHLY

## 現状まとめ（2026-01-28）
- 実装・テスト: 126 tests passed
- Kintone: フィールドコード英語化完了
- Kintone側アプリ: invoices/payouts は既に作成済み
- 同期スクリプト: DB→Kintone は作成済み、Kintone→DB取込はスクリプト存在

## ロードマップ

### Phase 0: 未決事項の確定（設計の詰め）
**目的**: 実運用時の計算・発行ルールを固定
- 税計算（行ごと/合計）
- 深夜割増の保存方針（store_minutes/dynamic）
- shift_label必須化の可否
- キャンセル料ルール

**完了基準**
- DECISION_LOGに確定事項を記録
- 仕様/運用/モデルへの影響を明示

---

### Phase 1: Kintoneアプリ構成の確定
**目的**: 実運用で必要なアプリとフィールドを矛盾なく確定
- invoices / payouts アプリの有無を確定
- REQUIRED_APPS_FIELDSに合わせてフィールドを一致
- .envのAPIトークン/アプリIDの整合

**完了基準**
- 20アプリすべての作成・トークン・フィールドコードが一致
- invoices/payoutsの作成有無が文書で一致

---

### Phase 2: マスタ投入（DB/Kintoneの正本化）
**目的**: 最小運用に必要なマスタが揃っている状態にする
- workers / clients / sites / roles / project_types
- price_sales / price_outsource / price_rules
- incentive_rules / task_templates

**完了基準**
- DBとKintoneの件数が一致
- 代表レコードのキーと必須項目が一致

---

### Phase 3: トランザクション投入（稼働テスト前提）
**目的**: 1案件×1期間の稼働テストを可能にする
- projects / shift_slots / assignments / actuals
- expenses / incentives
- bank_transfer_batches（生成テスト用）

**完了基準**
- 月次一連（取込→請求→支払→締め）が再現可能
- 監査ログが出力される

---

### Phase 4: Kintone連携フローの動作確認
**目的**: 双方向同期の最小フローを固定
- Kintone→DB: 実績取り込み（CSV or API）
- DB→Kintone: マスタ同期と結果書き戻し
- エラー差戻しと再取り込み

**完了基準**
- 代表アプリでKintone↔DBの往復が成功
- エラー時の差戻しが再現できる

---

### Phase 5: 月次ドライラン（実運用前の稼働テスト）
**目的**: 運用の再現性を確認
- CSV取込→差分→Soft Close→請求生成→支払生成→Hard Close
- PDF生成/メール送信/振込ファイル生成（必要なら疑似実行）

**対象案件数**: 3案件

**完了基準**
- RUNBOOK_MONTHLYの手順で再現できる
- 主要指標（売上/外注費/粗利）が算出される

---

### Phase 6: 本番稼働準備
**目的**: 権限・監査・運用体制の固定
- ロール権限、監査ログ、リリース手順
- バックアップ/復旧、運用カレンダー

**完了基準**
- 運用開始日と担当の確定
- 監視/ログの参照手順がRUNBOOKに記載

## 受入テスト（Go/No-Go）
- Kintoneアプリ構成とDBが一致
- 3案件×1期間のエンドツーエンドが再現
- 監査ログが必要箇所で記録される
- 月次RUNBOOKで迷わず手順が進む

## 既存ドキュメントの参照先
- DESIGN_SPEC_v0.3
- REVIEW_MERGE_v0.3
- KINTONE_APPS_LIST
- REQUIRED_APPS_FIELDS
- KINTONE_PROGRESS_REPORT
- RUNBOOK_MONTHLY
- DECISION_LOG
