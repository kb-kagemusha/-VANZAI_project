# A01 郵便番号自動入力ガイド

**最終更新**: 2026-02-06

## 目的
A01 受入企業マスターで郵便番号から都道府県・市区町村を自動入力し、存在しない郵便番号は警告で判別できるようにする。

## 対象
- アプリ: A01 受入企業マスター（ID: 276）
- カスタマイズJS: kintone-customize/phase1/a01_postal_auto_fill.js
- 使用API: zipcloud https://zipcloud.ibsnet.co.jp/api/search

## 使用フィールド
- postal_code: 郵便番号
- address_pref: 都道府県（SINGLE_LINE_TEXT）
- address_city: 市区町村（SINGLE_LINE_TEXT）
- address_text: 番地・建物（手入力）

## 仕様
1. 郵便番号が7桁になった時点で検索する（input/change/blur）。
2. 成功時は address_pref / address_city に自動入力し、画面にも即時反映する。
3. 失敗時はカスタムダイアログを表示し、保存時はエラー表示を行う。
4. 画面状態によっては保存を完全に止められないため、誤入力の警告表示を優先する。

## エラーメッセージ
- 7桁未満/超過: 「郵便番号は7桁で入力してください。」
- 存在しない郵便番号: 「存在しない郵便番号です。郵便番号（7桁）を確認してください。」
- API失敗: 「住所の取得に失敗しました: ...」

## 実装ポイント
- searchAddress: zipcloud検索（kintone.proxy）
- bindPostalInputAutoFill: 郵便番号の入力イベントを監視
- applyAddressToCurrentRecord: record反映 + DOM反映
- submit/submit.validate: エラー表示（保存ブロックは画面状態に依存）
- カスタムダイアログ: ensureDialogElements / showPostalDialog

## デプロイ手順
1. kintone-customize/phase1/a01_postal_auto_fill.js を更新
2. tools/cleanup_a01_customizations.py を実行（A01のJS/CSSを再適用）
3. Kintoneでデプロイ完了を確認
4. ブラウザを強制再読み込み（Ctrl+F5）

### 実行コマンド
```powershell
cd C:\Kuroko_Log_project\tools
C:\Kuroko_Log_project\.venv\Scripts\python.exe cleanup_a01_customizations.py
```

## 動作確認
- 正常: 1300011 -> 東京都墨田区石原
- 異常: 0000000 -> カスタムダイアログが表示される

## トラブルシュート
- 旧来のブラウザalertが出る場合: 旧JSが読まれている。デプロイと強制再読み込みを再実施。
- 住所が反映されない場合: コンソールに [A01 postal] bound postal input events が出るか確認。
- 保存が止まらない場合: 画面状態によって submit.validate が効かないことがある。警告表示で運用する。
