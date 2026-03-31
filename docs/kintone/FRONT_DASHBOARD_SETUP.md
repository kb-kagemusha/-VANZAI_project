# 登録ダッシュボード（ダイアログ登録）設定手順

## 目的
フロントページ（ポータル）から、以下をダイアログで登録/確認できるようにする。

- クライアント職員（クライアント先の責任者/担当者など）
- スタッフマスタ（所属=現場/VANZAI、IDは STxxx / VZxxx）
- 紹介元（下請け/紹介者）
- 現場
- 案件登録（販売:あり/なし）
- 実績登録（販売ありの案件のみ販売数入力）
- 案件確認（未入力のみ/実績未入力のみの絞り込み）
- 見積書・請求書の発行（確認セクションから遷移/出力）

## 構成
- カスタムアプリ: 登録ダッシュボード
- JSカスタマイズ: kintone_app/customizations/front_dashboard.js

## 手順

### 1. 登録ダッシュボード用アプリを作成
1. Kintoneで新規アプリを作成（空でOK）
2. アプリ名: 任意（例: front_dashboard）
3. アプリIDを控える

### 2. .env にアプリIDを設定
```env
KINTONE_APP_FRONT_DASHBOARD=<作成したアプリID>
KINTONE_APP_PROJECT_ASSIGNMENTS=307
KINTONE_APP_STAFF_MANAGERS=400
```

### 3. JSカスタマイズを適用
1. 登録ダッシュボードの「アプリの設定」→「JavaScript / CSSでカスタマイズ」
2. 追加ファイル: kintone_app/customizations/front_dashboard.js
3. 保存 → アプリを更新

### 4. 設定値の確認（JS内）
`front_dashboard.js` の `CONFIG.apps` を環境に合わせて変更:
- suppliers: 199
- sites: 166
- workers: 165
- staff_managers: 400
- project_assignments: 307
- actuals: 168
- invoices: 171
- payouts: 173

補足:
- 請求書/支払明細アプリは ID 差し替えが起きるため、`171/173` を優先し、見つからない場合は旧IDへ自動フォールバックする実装を含む
- 稼働者一覧・稼働者詳細編集は `workers=165`（稼働者マスタ）を正本参照とする
- それでも開けない場合は、実在するアプリIDへ `CONFIG.apps.invoices` / `CONFIG.apps.payouts` を更新する

### 5. フロントページの更新
```powershell
C:/VANZAI_project/.venv/Scripts/python.exe scripts/generate_kintone_front_page.py
```
生成された [docs/kintone/front_page.html](front_page.html) をポータルへ貼り付け。
あわせてポータルの「JavaScript / CSSでカスタマイズ」に以下を追加:
- [kintone_app/customizations/front_portal.js](../../kintone_app/customizations/front_portal.js)
- [kintone_app/customizations/front_portal.css](../../kintone_app/customizations/front_portal.css)

### 6. 不足フィールドの追加（推奨）
`front_dashboard.js` で追加した入力項目に合わせて、アプリ側へ不足フィールドを追加します。

```powershell
C:/VANZAI_project/.venv/Scripts/python.exe scripts/add_kintone_missing_fields.py
```

必要なAPIトークン例:
- `KINTONE_TOKEN_PROJECT_ASSIGNMENTS`
- `KINTONE_TOKEN_WORKERS`
- `KINTONE_TOKEN_SITES`
- `KINTONE_TOKEN_ACTUALS`

## 使い方
- フロントページの「登録ダッシュボード」を開く
- 画面上部のボタンから各マスタ/案件/実績を登録
- 「確認」行の「見積書・請求書の発行」から、対象・年月・帳票種別を選んで確認画面へ移動
- 登録後、自動リロードで反映

## 見積書・請求書の発行フロー（App174）

### UI配置
- 旧「請求書発行」ボタンは「登録」行から削除
- 「確認」行へ移動し、名称を「見積書・請求書の発行」に変更

### ダイアログ仕様
1. 発行対象を選択
	- 依頼者（クライアント）向け見積書・請求書
	- 下請けへの支払明細書
	- 紹介者への支払明細書
2. 年/月を選択
3. クライアント選択時は「請求書 / 見積書」を選択
4. クライアント責任者ごとに発行対象を絞り込み、件名は `◯年◯月分_` を手入力
   - 固定事務局費（手入力）を任意入力できる
   - 入力時は対象請求書の「固定事務局費」フィールドへ一括反映
5. 下請け選択時は、指定年月の実績（actuals）に出勤履歴がある稼働者のみ選択可能
	- 紹介者選択時は、上記に加えて `経由先=紹介` の稼働者のみ選択可能
6. 一括ZIP選択時は、対象月の出勤履歴がある稼働者分を個別PDFとしてZIP出力

### 稼働者詳細の入力制約
- 「経由先」は選択式（3択）: `下請け` / `紹介` / `VANZAI直接`
- 「紹介者/下請け」は `経由先=VANZAI直接` のとき自動空欄・入力不可
- `経由先` は必須。`経由先!=VANZAI直接` のとき「紹介者/下請け」は必須

### 稼働者（App165）経由先フィールド方針
- フィールドコード: `via_destination`
- 入力方式: ドロップダウン（`下請け` / `紹介` / `VANZAI直接`）
- `VANZAI直接` 選択時は「紹介者/下請け」を自動的に空欄化し、入力不可にする
- `group -> via_destination` 移行は完了済みのため、移行スクリプトは通常運用では使用しない

### 一括ZIPの前提
- payouts アプリに FILE 型のPDF添付フィールドが必要（ラベル/コードに `PDF` を含むと優先選択）
- 添付ファイルがPDFでない場合はZIP対象外

## 再発防止（重要）: Kintoneクエリの演算子とフィールド型

同一不具合の再発を防ぐため、`front_dashboard.js` でKintoneクエリを組み立てる際は以下を必須ルールとする。

### 1) 演算子ルール
- `CHECK_BOX / MULTI_SELECT / CATEGORY / USER_SELECT / ORGANIZATION_SELECT / GROUP_SELECT / STATUS_ASSIGNEE / DROP_DOWN / RADIO_BUTTON`
	- 演算子は `in` を使用する
- 上記以外（例: `SINGLE_LINE_TEXT / NUMBER / DATE` など）
	- 演算子は `=` を使用する

### 2) 実装ルール
- クエリ文字列を直接連結しない
- 必ず `buildKintoneFieldCondition(fieldCode, fieldType, value)` を通す
- `fieldType` は固定値にせず、フォームメタデータから解決した型を渡す
	- 例: `resolvePayoutFieldCodes().workerFieldType`
	- 例: `resolveActualsFieldCodes().workerType`

### 3) 特に注意する箇所
- 支払明細（App173）の `worker_id`
- 実績（App168）の `worker_id`
- 期間条件（`period_key`）

### 4) 変更時の確認手順（最短）
1. App174 稼働者詳細を開く
2. 「支払明細の作成」→「作成して開く」を実行
3. 期待結果
	 - `worker_id` の演算子エラーが出ない
	 - App173レコードが作成/取得される
	 - 支払明細PDFが自動生成される
	 - App173へ添付される（設定によりURL保存）

### 5) エラーが出たときの切り分け
- エラー文に `フィールドタイプ` と `演算子` が含まれる場合:
	- まず `workerFieldType / periodType / workerType` が未解決（空）になっていないか確認
	- 次に、該当クエリが `buildKintoneFieldCondition` を経由しているか確認
	- ハードリロード（`Ctrl + F5`）後に再確認

## 注意
- ダイアログ登録は Kintone JavaScript 実行が前提です。ポータルHTMLのみでは動作しません。
- 登録権限はKintoneのユーザー権限に依存します。

## 更新履歴

### 2026-02-16: 必要アプリの日本語ラベル統一（Task 43）
- 方針: フィールドコードは変更せず、画面ラベルのみ日本語へ統一
- 実施スクリプト: `scripts/update_kintone_field_labels_to_japanese.py`
- 反映方式: フォームプレビュー更新 → deploy
- 結果: 一括更新（成功 28 / 失敗 0）
- 補足: App173 は日本語フィールドコード運用のため、個別マッピング追加後に再実行して反映完了

### 2026-02-17: App173（支払明細）フィールド型の是正（Task 45）
- 問題: `支払明細ID / 稼働者ID / 案件ID` などがラジオボタンで、追加/入力運用が困難
- 対応: 正規フィールドを追加（`payout_id`, `worker_id`, `project_id`, `period_key`, `payment_date`, `status`, `version`, `parent_payout_id`, `total_amount`, `approved_at`, `paid_at`, `closed_at`, `notes`）
- 重要: `closed_at` は `DATE` として追加し、ラベルを「締め日」に統一
- 互換: 旧ラジオ/日時フィールドは削除せず `【旧】...` ラベル化して誤操作を抑止
- 実施スクリプト: `scripts/fix_app173_payout_schema.py`

### 2026-02-17: App171/App173 旧フィールド削除（Task 46）
- 前提: 入力済みデータはサンプルであり、legacy項目の物理削除を許容
- 対応: `【旧】` ラベル項目を App171/App173 から preview 削除 → deploy
- 結果: 両アプリとも `【旧】` 項目は 0件
- 実施スクリプト: `scripts/delete_legacy_fields_171_173.py`

### 2026-02-17: App171/App173 フォーム並び順の最適化（Task 47）
- 対応: 正規フィールドを先頭へ再配置（App171）
- App173: 既に正規順のため変更なし（順序固定のみ）
- 実施スクリプト: `scripts/reorder_layout_171_173.py`

### 2026-02-17: App171 旧由来コード項目の物理削除（Task 48）
- 対応: `数値* / 日付 / 日時* / 文字列__1行_*` を App171 から削除
- 結果: App171 は正規項目のみで運用可能な構成へ整理
- 実施スクリプト: `scripts/delete_obsolete_fields_app171.py`

### 2026-02-17: App174 稼働者一覧の絞り込み強化（Task 49）
- 対応: 稼働者一覧に `経由先` / `紹介者・下請け` の選択式フィルタを追加
- 反映: 経由先の正規化表示、`VANZAI直接` 時の紹介者空表示、絞り込み解除ボタンを実装
- 実施ファイル: `kintone_app/customizations/front_dashboard.js`

### 2026-02-17: App174 稼働者一覧の参照コード自動解決（Task 50）
- 対応: App165フィールドコード差異に備え、`経由先` / `紹介者` をラベル・候補コードから動的解決
- 反映: 一覧表示と詳細保存の双方で、解決済みコードを使用
- 実施ファイル: `kintone_app/customizations/front_dashboard.js`

### 2026-02-17: App174 稼働者一覧のソート強化（Task 52）
- 対応: `経由先` / `紹介者・下請け` のヘッダクリックソートを追加
- 追加: 氏名の次に `姓(カナ)` 列を追加し、同様にソート可能化
- 実施ファイル: `kintone_app/customizations/front_dashboard.js`

### 2026-02-17: 見積書PDFの自動生成・App171添付（Task 53）
- 対応: 「見積書・請求書の発行」で、App171レコード作成/取得後にPDFを自動生成して添付
- 反映: 遷移先を一覧からレコード詳細に変更（`/show#record=`）
- 追加: App171にFILEフィールドがない場合に `invoice_pdf` を追加するスクリプト
- 是正: `CB_JH01` 対応としてアップロード処理を `XMLHttpRequest` 化し、`X-Requested-With` ヘッダーを付与
- 追加: エラーダイアログをスクロール/コピー可能に改善（長文エラーの可読性を向上）
- 追加: `CB_CS01` / 不正リンクHTML応答は要約メッセージへ変換して表示
- 実施ファイル:
	- `kintone_app/customizations/front_dashboard.js`
	- `scripts/ensure_app171_pdf_file_field.py`

### 2026-02-17: 見積書PDFの軽量化と保存先切替（Task 53 追補）
- 対応: PDF生成を Canvas画像埋め込みから jsPDFテキスト描画へ変更
- 効果: 大容量化（約8MB）の発生を抑止し、実運用しやすいサイズへ軽量化
- 追加: 保存先を `CONFIG.invoicePdf.uploadTarget` で切替可能化
	- `download`（既定・ローカル保存）
	- `external`（`externalUploadUrl` にアップロード）
	- `kintone`（既存FILE添付）
- 補足: Kintone添付時はCSRFトークン候補を複数経路から取得し順次試行

### 2026-02-17: 外部保存URLのApp171保存対応（Task 53 追補2）
- 対応: 外部ストレージ保存時の `fileUrl` をApp171へ保存する導線を追加
- 前提: App171に LINK型フィールド `invoice_pdf_url`（ラベル例: 見積書PDF URL）が必要
- 追加スクリプト: `scripts/ensure_app171_pdf_url_field.py`

### 2026-02-17: App174 支払明細導線の再発防止ルール追記（Task 54）
- 背景: `worker_id` のフィールド型差異により、`=` 演算子が使えず再発した事象への恒久対策
- 対応: クエリ演算子とフィールド型の対応表、必須実装ルール、確認手順を本書へ明記
- 効果: App173/App168 の型差異（文字列/ドロップダウン/ラジオ）でも同一フローで運用可能

詳細記録は [docs/IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md) を参照。
