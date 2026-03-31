# 買い周りサポート かんたんマニュアル（質問ゼロ運用版）

最終更新: 2026-03-03
対象ファイル: `mobile-report-app.html` / `flow-data.json`

---

## 1. これだけやれば使える（30秒）

1. `mobile-report-app.html` を開く
2. 上部バーで自分のチームを選ぶ
3. 「報告する」タブでフロー判定を進める
4. 下の7項目を埋める
5. 「報告文を作成＋保存」
6. 必要なら「テキストをコピー」してLINEやメールに貼り付ける

> 迷ったら: 青い「判断のヒント」を読んで、わからなければ NO を押して先へ進んでOK。

---

## 2. 起動方法（失敗しない）

### A0) 共有DB付きサーバー版（推奨）
```powershell
cd C:\MykeyC
C:/MykeyC/.venv/Scripts/python.exe app_server.py
```
- ブラウザで `http://127.0.0.1:8080/mobile-report-app.html`
- 画面上部のバッジが `サーバー共有DB: ON` なら共有DB利用中
- DBファイルは `shared_reports.db`（同フォルダ）

### A) 推奨: VS Code Live Server（ローカル保存モード）
- `mobile-report-app.html` を右クリック
- `Open with Live Server`

### B) 代替: Python簡易サーバー
```powershell
cd C:\MykeyC
python -m http.server 8080
```
- ブラウザで `http://127.0.0.1:8080/mobile-report-app.html`

### C) 直接開き（file://）
- 本アプリは**直接開きでも動く設計**（HTML内埋め込みフローデータに自動フォールバック）

---

## 3. 入力ルール（質問されないための統一ルール）

- チーム: 最初に上部バーで選択（保存先チームになる）
- 1）結果: プルダウンから選択
- 2）報告ナンバー: フロー後に自動（手入力不要）
- 3）日時: 初期値で現在時刻が入る（必要なら変更）
- 4）店舗名: 手入力 or Google Maps URL解析
- 5）住所: 手入力 or Google Maps URL解析
- 6）レシート写真: 必須（ファイル選択）
- 7）コメント: 任意（空欄可）

### チーム運用ルール（推奨）
- 1端末1担当者で利用（同時利用しない）
- 報告前にチーム名を必ず確認
- チーム追加はリーダーのみ実施

---

## 4. Google Maps URL解析の使い方

1. Google Mapsで店舗ページURLをコピー
2. 「Google Maps URL」欄に貼る
3. 「URL解析」を押す

### 注意
- `maps.app.goo.gl` の短縮URLは解析不可
- `google.* /maps/` 以外のURLは拒否
- 住所取得は OpenStreetMap Nominatim の逆ジオコーディングを利用（ネット接続が必要）

---

## 5. よくある詰まり（運用向け）

- **報告文が作れない**
  - 必須項目の未入力。警告に出た項目を埋める
- **別チームに保存してしまった**
  - 上部バーで正しいチームに切替 → 再作成
- **住所が自動入力されない**
  - URLが短縮URL or Google Maps URLではない
- **写真が送られない**
  - 仕様です。報告文作成のみ。実送信時に別途添付

---

## 5.1 リーダー向け集計手順

1. 「集計（リーダー用）」タブを開く
2. 「表示チーム」で `全チーム` または任意チームを選ぶ
3. 画面上部の件数カードで全体状況を確認
4. 下の一覧テーブルで明細を確認
5. 必要に応じて `CSV出力` / `テキスト出力`

### できること
- チーム追加・削除
- チームフィルタ集計
- 個別報告の削除
- 全データ削除
- CSVダウンロード

### 注意
- 集計データは **localStorage（同一ブラウザ・同一端末）** に保存
- 他端末とは自動共有されない

---

## 6. セキュリティチェック結果（実施済み）

## 6.1 参照基準
- Context7 で `MDN /mdn/content` を参照
- CSP（Content Security Policy）と inline script 制約のベストプラクティスを確認

## 6.2 実装済み対策
- `textContent` で表示文字列を構築（ユーザー入力のHTML実行を防止）
- 質問描画を `innerHTML` 連結から DOM API 生成へ変更
- Google Maps URL は `new URL()` で構文検証
- ドメイン制限: `google.*` + `/maps/` 以外は拒否
- CSPメタタグ追加:
  - `default-src 'self'`
  - `connect-src 'self' https://nominatim.openstreetmap.org`
  - `img-src 'self' data: blob:`
  - `base-uri 'none'`
  - `frame-ancestors 'none'`
  - `form-action 'self'`
- サーバーAPI側で入力必須項目を検証（teams / reports）

## 6.3 残留リスク（許容範囲）
- `style-src/script-src` に `unsafe-inline` を使用
  - 単一HTML運用のため。現実運用上は許容
  - さらに強化する場合は JS/CSS を外部ファイル化し、`unsafe-inline` を撤去
- 外部通信先（Nominatim）に依存
  - 障害時は住所自動入力のみ失敗（手入力で運用継続可能）

## 6.4 判定
- 現行要件（単一HTML・現場利用・多数利用）に対して**実用上問題ない安全水準**
- 高セキュリティ環境へ持ち込む場合は「外部JS/CSS化 + 厳格CSP」を追加実施推奨

---

## 7. 変更ログ（作業ログ）

### 2026-03-03 実施
- フロー判定UIを全面改善
  - ステップ表示
  - 「1つ戻る」
  - 「最初から」
  - 質問ごとの判断ヒント表示
- 入力UX改善
  - 現在日時を自動入力
  - 必須項目の明示バリデーション
  - トースト通知（コピー成功など）
- 実行互換性改善
  - `flow-data.json` 読込失敗時に埋め込みJSONへフォールバック
- セキュリティ改善
  - DOM API描画へ移行
  - Google URL検証
  - CSP導入
- データ改善
  - `flow-data.json` の全質問に `hint` を追加
  - JSONをUTF-8(BOMなし)に修正
- チーム対応を追加
  - チーム選択バー（現在チーム表示、localStorage保存）
  - 報告作成時にチームを自動付与
  - 集計タブ（リーダー用）追加
  - チーム別フィルタ / CSV出力 / テキスト出力 / 削除機能
- サーバーあり版（最小構成）を追加
  - `app_server.py`（標準ライブラリのみ）
  - SQLite共有DB（`shared_reports.db`）
  - API: `/api/health` `/api/teams` `/api/reports`
  - フロント側はサーバー自動検出（失敗時はローカル保存へフォールバック）
- 日次サマリを追加
  - API: `/api/summary/daily?date=YYYY-MM-DD&team=__ALL__|チーム名`
  - ダッシュボード上部に「今日のサマリ」を表示
- 週次サマリを追加
  - API: `/api/summary/weekly?date=YYYY-MM-DD&days=7&team=__ALL__|チーム名`
  - ダッシュボード上部に「直近7日のサマリ」を表示
- 月次サマリを追加
  - API: `/api/summary/monthly?date=YYYY-MM-DD&days=30&team=__ALL__|チーム名`
  - ダッシュボード上部に「直近30日のサマリ」を表示
- 任意期間サマリを追加
  - API: `/api/summary/range?start=YYYY-MM-DD&end=YYYY-MM-DD&team=__ALL__|チーム名`
  - ダッシュボード上部で開始日/終了日を指定して集計可能
- 削除運用を強化
  - 指定削除（チェック選択）
  - 指定削除（報告IDを直接入力）
  - 直前削除の巻き戻し（Undo）
  - 削除ログ一覧（最新10件）
  - ログ行から任意opIdの巻き戻し
- 操作担当者ログを追加
  - 画面上部の「担当者」入力をAPIヘッダに送信
  - 監査ログに `actor` を記録

---

## 9. 日次サマリ（リーダー向け）

- 対象画面: 「集計（リーダー用）」タブ
- 表示内容: 今日の合計件数 + 結果別件数
- フィルタ連動: 「表示チーム」が `全チーム` なら全体、個別チームならそのチームのみ

### API単体確認
```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8080/api/summary/daily?date=2026-03-03&team=__ALL__"
```

### 補足
- サーバーモード時のみ共有DBのサマリを表示
- ローカル保存モードでは「共有DBサマリはサーバーモード時のみ」の表示になる

---

## 10. 週次サマリ（リーダー向け）

- 対象画面: 「集計（リーダー用）」タブ
- 表示内容: 直近7日（当日含む）の合計件数 + 結果別件数
- フィルタ連動: 「表示チーム」が `全チーム` なら全体、個別チームならそのチームのみ

### API単体確認
```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8080/api/summary/weekly?date=2026-03-03&days=7&team=__ALL__"
```

---

## 11. 月次サマリ（リーダー向け）

- 対象画面: 「集計（リーダー用）」タブ
- 表示内容: 直近30日（当日含む）の合計件数 + 結果別件数
- フィルタ連動: 「表示チーム」が `全チーム` なら全体、個別チームならそのチームのみ

### API単体確認
```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8080/api/summary/monthly?date=2026-03-03&days=30&team=__ALL__"
```

---

## 12. 期間指定サマリ（range）

### 画面から実行
- 「集計（リーダー用）」タブ
- 開始日/終了日を指定
- 「期間集計」を押す

### API単体確認
```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8080/api/summary/range?start=2026-02-20&end=2026-03-03&team=__ALL__"
```

---

## 13. 削除・巻き戻し運用

### 指定削除
- 一覧のチェックボックスで対象を選択
- 「選択削除」を押す

### ID指定削除
- 「削除したい報告ID（カンマ区切り）」へ入力
- 「ID指定削除」を押す

### 全削除（リセット）
- 「全削除」を押す

### 巻き戻し
- 「直前削除を巻き戻す」ボタン
- または削除ログの「この削除を戻す」ボタン

### ログ
- 「削除ログ（最新10件）」に opId・件数・時刻を表示
- 同時に担当者（actor）を表示
- サーバー側監査ログAPI: `/api/deletions` `/api/logs`

### 監査ログフィルタ（新規）
- 期間（開始日/終了日）
- 担当者（完全一致）
- action 種別
- 「ログ絞り込み」で再取得
- 「ログCSV出力」で監査ログをダウンロード

---

## 14. 誰が操作したか（担当者ログ）

- 画面上部の「担当者」を設定してから操作
- 以下の操作は担当者名付きで監査ログへ記録
  - チーム作成
  - 報告作成
  - 指定削除 / 全削除
  - 巻き戻し（Undo）

### APIで担当者を直接指定する場合
```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/reports/delete \
  -Headers @{ 'X-Actor'='leader-tanaka' } \
  -ContentType 'application/json' \
  -Body (@{ids=@('report-id-1')} | ConvertTo-Json)
```

### 監査ログAPI（フィルタ付き）
```powershell
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8080/api/logs?start=2026-03-01&end=2026-03-03&actor=leader-tanaka&action=delete_reports&limit=100"
```

### 注意
- サーバーモード時のみ巻き戻しと共有ログが有効
- ローカルモード削除は端末内のみ・巻き戻し不可

---

## 8. 運用者向け・最短案内テンプレ

必要なら以下をそのまま共有してください。

> 上のフローでYES/NOを押して、出た番号をそのまま使ってください。  
> 上部でチームを選び、下は1〜7を埋めて「報告文を作成＋保存」です。  
> リーダーは「集計（リーダー用）」タブで全件確認できます。  
> Google MapsのURLを貼ると店名・住所は自動入力できます（短縮URLは不可）。
