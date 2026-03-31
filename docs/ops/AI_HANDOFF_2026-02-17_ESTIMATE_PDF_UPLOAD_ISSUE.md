# AI相談用ハンドオフ（見積書PDFアップロード不具合）

## 1. 相談したい問題（現状ブロッカー）
- App174の「見積書・請求書の発行」から見積書を作成すると、
  - App171レコード作成（または表示）はできる
  - ただしPDF添付処理で失敗する
- 現在のエラー:
  - 「PDFアップロードに失敗しました: セッションの有効期限切れです。ページを再読み込みしてから再実行してください。」
- 追加で確認された問題:
  - ダイアログの「再読み込み」ボタンを押しても画面上で何も起こらない

## 2. 期待挙動
- App174で見積書発行を実行すると、
  1) App171に対象レコードが作成される（または既存取得）
  2) 見積書PDFを生成
  3) App171のFILEフィールドへPDF添付
  4) 対象レコード詳細を表示

## 3. 実際挙動
- 1) は動く（レコード詳細は表示される）
- 2) までは進んでいるが、3) のアップロードで失敗
- `CB_CS01`（ページ有効期限切れ）系で停止

## 4. 再現手順
1. App174を開く
2. 「見積書・請求書の発行」をクリック
3. 発行対象: 依頼者（クライアント）向け見積書・請求書
4. 年月: 2026年2月
5. クライアント責任者: 山田太郎
6. 帳票種別: 見積書
7. 実行
8. レコード表示後、PDF添付処理で上記エラー

## 5. ここまでに実施した修正（時系列）

### 5.1 UI/導線
- 稼働者詳細の右上ボタン追加（支払明細の作成/参照）
- 参照モーダルに年月絞り込み追加
- エラーダイアログをネイティブalertからカスタムに変更
  - 長文スクロール対応
  - コピー機能追加
  - 再読み込みボタン追加（ただしユーザー環境で動作していない報告）

### 5.2 見積書発行ロジック
- `document_type` 演算子エラー対策（条件組み立ての見直し）
- 未作成時はApp171へ自動作成
- 作成後は一覧ではなくレコード詳細へ遷移

### 5.3 PDF生成/添付
- jsPDFで見積書PDFをブラウザ生成
- `file.json` へアップロードして fileKey を取得
- App171レコードのFILEフィールドへ紐付け

### 5.4 App171側準備
- App171にFILEフィールドが無かったため追加
  - フィールドコード: `invoice_pdf`
  - ラベル: 見積書PDF
- 反映確認済み（APIで `invoice_pdf` 存在確認）

### 5.5 認証エラー対応履歴
- `CB_JH01`（X-Requested-With不足）
  - 対策: X-Requested-With付与
- その後 `CB_CS01`（ページ有効期限切れ）が継続
  - 対策: 表示メッセージを要約化、再読み込み案内
  - ただし根本解消には未達

## 6. 現在の主要エラー履歴

### 6.1 過去
- CB_JH01
  - メッセージ: セッション認証には X-Requested-With が必要

### 6.2 現在
- CB_CS01
  - メッセージ: ページの有効期限が切れています。ページを再読み込みしてください。

### 6.3 付随
- HTMLエラーページ（「このリンクは不正です。」）の本文がレスポンスに混入するケースあり

## 7. 変更済みファイル
- [kintone_app/customizations/front_dashboard.js](../../kintone_app/customizations/front_dashboard.js)
- [scripts/ensure_app171_pdf_file_field.py](../../scripts/ensure_app171_pdf_file_field.py)
- [docs/IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md)
- [docs/FILE_INDEX.md](../FILE_INDEX.md)
- [docs/kintone/FRONT_DASHBOARD_SETUP.md](../kintone/FRONT_DASHBOARD_SETUP.md)

## 8. App171の確認結果
- `invoice_pdf` フィールドは存在
- 種別: FILE
- ラベル: 見積書PDF

## 9. 他AIに相談したいポイント（依頼内容）
1. Kintoneゲストスペース上のフロントJSから `file.json` へ安全にアップロードする正攻法
   - セッション認証の前提（token/ヘッダ/送信方式）
   - `CB_CS01` を回避するための実装パターン
2. App174（ゲスト3）→ App171（同ゲスト）でのCSRF/セッション整合の注意点
3. 現在の `front_dashboard.js` のアップロード部に対する最小修正案
4. 可能なら「PDF生成→一旦ブラウザDL→ユーザー手動添付」ではなく、自動添付を維持した解決策

## 10. 補足（ユーザー要望）
- 実装が完了したら、ドキュメント・INDEX・ログを必ず残す方針
- エラー表示はCybozu標準ダイアログではなく、カスタムで見やすくしたい

---

## 11. 直近ステータス（簡潔）
- レコード作成/表示: OK
- PDF生成: おそらくOK
- PDFアップロード（file.json）: NG（CB_CS01）
- 根本課題: セッション/CSRF整合

## 12. 追加ログ（2026-02-17 追記）

ユーザー提供のブラウザコンソールログ:

```text
download.do?app=174&…c83ec997330380:2158
 POST https://xtf5wpxp3gk2.cybozu.com/k/guest/3/v1/file.json 400 (Bad Request)
（匿名） @ download.do?app=174&…c83ec997330380:2158
uploadOnce @ download.do?app=174&…c83ec997330380:2131
uploadFileBlobToKintone @ download.do?app=174&…c83ec997330380:2162
generateAndAttachInvoicePdf @ download.do?app=174&…c83ec997330380:2205
await in generateAndAttachInvoicePdf
（匿名） @ download.do?app=174&…c83ec997330380:2445
await in （匿名）
（匿名） @ download.do?app=174&…4c83ec997330380:609
```

補足:
- エンドポイントはゲストスペース配下の `/k/guest/3/v1/file.json`
- HTTPステータスは 400
- 呼び出し元は `uploadFileBlobToKintone` → `generateAndAttachInvoicePdf` で一致
