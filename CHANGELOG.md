# CHANGELOG

バージョン管理ルール（AGENTS.md セクション9 参照）
- **正本**: `apps/admin-web/package.json` と `apps/staff-mobile/package.json` の `version` フィールド
- **CHANGELOG の `## [X.Y.Z]` 見出し**は、上記 `package.json` を実際に更新した版のみ付与する（開発メモを版番号として記載しない）
- **X（左）**: 大きな機能追加（新ドメイン追加、画面体系の大幅変更など）
- **Y（中）**: 細かな機能追加（既存画面への機能追加、新APIエンドポイント、新ページなど）
- **Z（右）**: バグ修正・軽微な変更（修正、リファクタリング、表示調整など）

## [0.10.51] - 2026-07-05

### Added
- **OCR・保存データ**: 画像ファイル名クリックで左に画像・右に読取データを並べた確認パネル。画像を見ながら編集・保存・「問題なしで確定」が可能

### Fixed
- **OCR・保存データ**: 表示件数（10/20/50）を `localStorage` に確実に保持。アップロード画像一覧の表示件数も同様に永続化。絞り込み・ページ番号はタブごとに `sessionStorage` で保持

## [0.10.68] - 2026-07-06

### Fixed
- **ビルド**: OCR UI 変更時の import 欠落を修正（admin-web TypeScript ビルドエラー）

## [0.10.67] - 2026-07-06

### Fixed
- **OCR・確認パネル**: リネーム前は元の画像ファイル名を表示（推奨名は別行で表示）
- **OCR・Paygate SS**: 決済方法を現金 / QRコード / クレジット のみ表示し、未読取・不正値は「ー」
- **OCR・精算レシート**: 精算日の表示を `YYYY/MM/DD` に統一。日付 OCR 前処理でハイフン区切りもスラッシュに正規化
- **OCR・精算レシート**: 端末識別番号・端末番号・精算日時の誤読を改善（`9810`/`9sf0` 系の OCR 劣化、金額 `7840` の誤採用、日時形式）

### Changed
- **開発運用**: 修正完了後のバージョン・CHANGELOG・コミット・デプロイ手順をワークスペースルールに明文化

## [0.10.65] - 2026-07-06

### Fixed
- **OCR**: 精算レシート読込時などの英語エラー（`could not execute a primitive` 等）を日本語表示に統一

## [0.10.64] - 2026-07-06

### Fixed
- **OCR・Paygate SS・確認パネル**: レシート番号のフォントサイズを他項目と統一
- **OCR・Paygate SS**: 画像ファイル名を `Paygate精算画面_日付_最小取引番号～` 形式で提案し、1枚の画像に紐づく全行で連動してリネーム

## [0.10.63] - 2026-07-06

### Added
- **OCR**: アップロード済み画像ごとに「再解析」を追加。1枚から複数行を読み込む Paygate SS などで、画像全体を再OCRして保存データを作り直せる（確定済み行がある場合は不可）

## [0.10.62] - 2026-07-06

### Fixed
- **OCR・Paygate SS・保存データ**: 不要列（通常取引数・稼働日・現金/POS台数・在庫照合対象）を非表示にし、日付と時刻を分離。金額は 980 / 1480 / 1980 の整数表示に統一

## [0.10.61] - 2026-07-06

### Fixed
- **OCR・Paygate SS**: レシート番号が `782` 始まりの取引一覧スクショを「有効なデータなし」と誤判定していた問題を修正（日付・時刻・取引番号・レシート番号・金額の抽出ルール自体は変更なし）

## [0.10.60] - 2026-07-06

### Added
- **OCR**: 「Paygateスクリーンショット」と「精算レシート」を別ページに分割
- **OCR・確認パネル**: 画像ファイル名の編集と、確定時の `精算レシート_（端末識別番号）_（精算日）` 形式への自動リネーム
- **OCR**: 画像・保存データ削除の確認をオリジナルポップアップに変更

### Fixed
- **OCR・端末番号**: 部分抽出（`-7f8d-4b74-aa67-` + 12桁など）からの復元ロジックを強化
- **OCR・確認パネル**: 部分抽出時に端末番号分割入力へ既知セグメントを事前表示
- **OCR**: `pending_review` ステータスを「未確定」と日本語表示
- **OCR**: 確定済み行の検証欄に「確定」ラベルを表示
- **OCR・Paygate SS**: 解析対象をページ種別ごとに分離（精算レシートと混在しないよう修正）
- **OCR**: 解析中の進捗（件数・バッチ・成功/失敗）をボタン横とホバーで分かりやすく表示

## [0.10.59] - 2026-07-06

### Added
- **OCR・確認パネル**: 端末番号の編集を 8-4-4-4-12 の分割入力欄に対応

### Fixed
- **OCR・確認パネル**: 97%表示なのに青くなる信憑性色分けの不一致を修正（表示％の丸め基準に統一）
- **OCR・確認パネル**: 検証メッセージで縦に伸びて操作ボタンが押せなくなるレイアウトを修正（ヘッダー/本文スクロール/フッター固定）
- **OCR・精算レシート**: 1行UUIDや断片トークンから端末番号を復元する抽出ロジックを改善（`e9c0` 系レシートの部分抽出を解消）

## [0.10.58] - 2026-07-06

### Fixed
- **OCR・端末番号表示**: フォントサイズを他項目と揃え、1行目を `8-4-4-`・2行目を `4-12` の2行固定表示に修正（折り返し・末尾ハイフン欠落を解消）

## [0.10.57] - 2026-07-06

### Changed
- **OCR・読取信憑性**: 色分けしきい値を 97%以上（黒）/ 85–96%（青）/ 85%未満（オレンジ）に変更

## [0.10.56] - 2026-07-06

### Added
- **OCR・Paygate SS**: 精算レシートと同様の「再解析」APIに対応。保存データ一覧・確認パネルから再解析可能

### Changed
- **OCR・信憑性表示**: 確認パネルでは％付き、一覧では色分けのみ（凡例は一覧上部に常時表示）
- **OCR・確認パネル**: 端末番号のフォントサイズを他項目と揃えた

## [0.10.55] - 2026-07-05

### Changed
- **OCR・確認パネル**: 端末番号を `8-4-4` / `4-12` の2行表示に変更。部分抽出時は読めた断片を表示し「部分抽出のみ」バッジを付与（確定不可）
- **OCR・確認パネル**: 再解析中は画像オーバーレイとボタンアニメーションで進行を表示
- **OCR・保存データ一覧**: 確定前の行は信憑性の色分けを一覧でも表示

## [0.10.54] - 2026-07-05

### Added
- **OCR・Paygate SS**: 精算レシートと同様の確認パネル（画像＋読取データ、行単位編集、信憑性％表示）を Paygate スクショ行にも適用。取引番号・レシート番号・決済方法の信憑性をバックエンドで算出

### Changed
- **OCR・保存データ**: 操作列の「編集」を「確認」に統一し、確認パネルを開く操作に揃えた

## [0.10.53] - 2026-07-05

### Changed
- **OCR・保存データ確認パネル**: 読取データをレシート印字順（上から）の1行1項目で表示。各行に編集ボタンを配置し、押下時のみその場で値を変更可能（下部の一括編集フォームを廃止）

## [0.10.52] - 2026-07-05

### Added
- **OCR・保存データ確認パネル**: 各項目の読取信憑性を参考％表示（99%以上=黒、90–98%=青、90%未満=オレンジ）。PaddleOCR行信頼度と抽出方法から算出

### Fixed
- **精算レシートOCR（98f0系）**: 端末番号が日時ノイズや誤OCR行から誤組立される問題を修正。高信頼度UUID行の優先・98f0明示パターン・端末識別番号 `981e/9810` 誤読の補正

## [0.10.51] - 2026-07-05

### Added
- **OCR・保存データ**: 画像ファイル名クリックで左に画像・右に読取データを並べた確認パネル。画像を見ながら編集・保存・「問題なしで確定」が可能

### Fixed
- **OCR・保存データ**: 表示件数（10/20/50）を `localStorage` に確実に保持。アップロード画像一覧の表示件数も同様に永続化。絞り込み・ページ番号はタブごとに `sessionStorage` で保持

## [0.10.50] - 2026-07-05

### Fixed
- **精算レシートOCR（260703_2）**: 小計 `16B60` 誤読で ¥16 になる問題を修正（非妥当金額の除外・レイアウト優先・合計との整合）。2c0e 系端末番号の組立も強化

### Added
- **OCR・保存データ**: 端末識別番号・ステータス・検証・キーワードでの絞り込み、表示件数（10/20/50・既定20）とページ送り

## [0.10.49] - 2026-07-05

### Fixed
- **精算レシートOCR（260703_15）**: 現金売上・PAYGATE POS・端末番号の本番OCR誤読補正（`現金上`/`PAY0ATE` 正規化、`17840`→7840、`1980`→980、0b21 UUID断片組立、合計からPOSを誤推論しないよう修正）

## [0.10.48] - 2026-07-05

### Fixed
- **精算レシートOCR**: `b0d6cc26.a!` 行と `af4c-ff22d625c6a7` 断片からの明示的UUID組立（`ff22` 誤分割の防止）

## [0.10.47] - 2026-07-05

### Fixed
- **精算レシートOCR**: 260703_14 の本番OCR向けに UUID 行正規化・日時ノイズ除外・先頭末尾フラグメント組立を追加（`DOd6cc?6.a!` → 正UUID、郵便番号誤ヒント防止）
- **精算レシートOCR**: UUID 中腹帯の追加OCRパス（高解像度帯）を追加

## [0.10.46] - 2026-07-05

### Fixed
- **精算レシートOCR**: 260703_14 系の端末識別番号・UUID誤読補正（`DOd6`→`b0d6`、郵便番号ノイズ除外、`ff22d625c6a7` 断片の再結合、ID帯・UUID広帯の追加OCR）
- **OCR・レシート解析**: 解析中・再解析中はボタンにホバーで進捗グラフを表示（一覧下の固定バーを廃止し、操作ボタン付近で確認可能に）

## [0.10.45] - 2026-07-05

### Fixed
- **精算レシートOCR**: 端末識別番号・端末番号の誤読補正強化（0も21→0b21、0621→0b21、750/8246ノイズ除去、UUID断片の並べ替え組立、2026/01八02 日付補正）

## [0.10.44] - 2026-07-04

### Fixed
- **精算レシートOCR**: 精算日時の読取強化（時刻→日付の逆順、全角コロン・円誤読、8桁日付、`2026/07101` 誤結合、`23:02-59` / `23-07:13` / `23:0259` 形式、日付行分割）

## [0.10.43] - 2026-07-04

### Fixed
- **OCR・レシート解析**: バッチ解析中の進捗バーにストライプ・シマーアニメーションを追加し、処理継続中であることを視覚的に表示

## [0.10.42] - 2026-07-04

### Fixed
- **精算レシートOCR**: 精算日時の読取強化（日付・時刻の行分割、`202607/02` 誤読補正、6桁時刻、識別番号直後のゾーン抽出）

## [0.10.41] - 2026-07-04

### Added
- **OCR・レシート解析**: 精算6枚・スクショ15枚のバッチ解析、進捗バー、失敗分の自動再試行（最大2回）、全体10分上限

## [0.10.40] - 2026-07-04

### Fixed
- **OCR・レシート解析**: 検証エラー・画像解析エラー・`duplicate_receipt_candidate` 等を日本語表示に統一

## [0.10.39] - 2026-07-04

### Added
- **OCR・レシート解析**: 解析失敗・タイムアウト・一部失敗時にモダンなポップアップ通知を表示

## [0.10.38] - 2026-07-04

### Added
- **管理画面サイドバー**: 縮小時にメニューアイコンへホバーすると項目名・説明をフライアウト表示

## [0.10.37] - 2026-07-04

### Fixed
- **精算レシートOCR（260703_1）**: UUID末尾 `06` 誤読を `90` に補正、誤読小計ラベル（小餅等）での端末番号セクション切り出し改善

## [0.10.36] - 2026-07-04

### Fixed
- **精算レシートOCR（260703_1）**: UUID末尾が別行 `90` に折り返された場合の端末番号修復（`...5bb5733a2490`）

## [0.10.35] - 2026-07-04

### Fixed
- **精算レシートOCR**: UUID復元時の2桁数字ノイズ（06/15等）を除外し端末番号末尾の誤結合を抑制

## [0.10.34] - 2026-07-04

### Fixed
- **精算レシートOCR（260703_1）**: レシート固定順序（精算→日時→端末番号→小計→合計→現金売上）に基づく抽出を追加
- **精算レシートOCR**: 日時の連結誤読（`2026/06/2723:04:46`）・`15.880`→`5,880` 補正・UUID末尾 `90`/`06` の優先判定

## [0.10.33] - 2026-07-04

### Fixed
- **精算レシートOCR**: 合計=現金売上のみのレシートでクレジット/POS誤読を0に正規化（内訳不一致解消）

## [0.10.32] - 2026-07-04

### Fixed
- **精算レシートOCR**: 現金売上と同一値のPOS誤読を重複として除外（取引数10誤認を防止）

## [0.10.31] - 2026-07-04

### Fixed
- **精算レシートOCR**: 無効なPOS金額を取引数推定から除外し、現金のみ時は5件等を正しく推定
- **精算レシートOCR**: 合計=現金売上時のクレジット/POS誤読（20等）を0に正規化

## [0.10.30] - 2026-07-04

### Fixed
- **精算レシートOCR**: 現金のみ売上時は通常取引数を売上金額÷980で優先推定（OCR誤読10等を上書き）
- **精算レシートOCR**: PAYGATE POS/クレジットの `20` 誤読を0扱いにし金額内訳不一致を解消

## [0.10.29] - 2026-07-04

### Fixed
- **精算レシートOCR（260703_11 本番JPG）**: LINE圧縮画像の劣化OCR向けに端末番号候補のスコアリング・ゴミ行除外を追加
- **精算レシートOCR**: ラベル文字化け（小訁E/今訁E/現金売丁等）からの金額抽出、現金売上のみ時の合計推定
- **精算レシートOCR**: クレジット誤読 `20` の除外、`4280`→`428c`・`Sbb`→`5bb` 等のUUID補正

## [0.10.28] - 2026-07-04

### Fixed
- **精算レシートOCR（260703_11）**: 本番OCRの誤ラベル（現会売上・会計・澤末番号等）と3行折返しUUIDを正規化して復元
- **精算レシートOCR**: 端末識別番号 `8402`→`84e2`（eの0誤読）、`2d32`/`3d32`→`ed32`、`じ`/`日`混入のUUID行を補正
- **精算レシートOCR**: 金額の先頭ノイズ（04900/44900等）と売上金額からの通常取引数推定を強化

## [0.10.27] - 2026-07-04

### Fixed
- **精算レシートOCR（260703_8）**: 画像上端ギリギリの端末識別番号向けにヘッダー帯域OCRを再統合
- **精算レシートOCR**: OCR誤読 `đ`（d-stroke）を `d` に正規化し、折返しUUID末尾の復元を改善
- **精算レシートOCR**: アクセント付き文字（例: `6bfá`）を除去して端末識別番号4桁を抽出

## [0.10.26] - 2026-07-04

### Fixed
- **管理画面サイドバー**: メニュー部分だけの内部スクロールバーを廃止し、サイドバー全体を1本の縦スクロールに統一

## [0.10.25] - 2026-07-04

### Changed
- **管理画面サイドバー**: ◀▶ 折りたたみボタンを常時表示せず、サイドバーにホバーしたときのみ表示。縮小時のメニューホバーツールチップも廃止

## [0.10.24] - 2026-07-04

### Fixed
- **管理画面サイドバー**: ◀▶ 折りたたみボタンをスクロールしても画面上部の同じ位置に固定表示

## [0.10.23] - 2026-07-04

### Fixed
- **管理画面サイドバー**: メニュー行が縦に伸びて大きく表示される不具合を修正（自然な高さに戻す）
- **管理画面サイドバー**: ◀▶ 折りたたみボタンをサイドバー上部へ移動

## [0.10.22] - 2026-07-04

### Changed
- **管理画面サイドバー**: ◀▶ ボタンでアイコンのみ表示（縮小）とアイコン＋文言表示（展開）を切り替え可能に。状態はブラウザに保存

## [0.10.21] - 2026-07-03

### Changed
- **端末識別番号**: 必ず4桁16進（0-9a-f）として正規化・検証。手入力/APIは厳密4桁、OCRは誤読補正後に4桁抽出。未入力・不正形式は確定ブロック

## [0.10.20] - 2026-07-03

### Fixed
- **精算レシート帯域OCR**: `Oed?rTad-ebas.` 等の本番ノイズパターンに対応（`O`/`0` 混同、ebas→eba8）

## [0.10.19] - 2026-07-03

### Fixed
- **精算レシート260703_18**: 帯域OCRのノイズ行（`Oed77Tad-eDas-` 等）からUUID断片を復元。ヘッダー帯域の誤マージを除去

## [0.10.18] - 2026-07-03

### Fixed
- **精算レシート帯域OCR**: 座標マージの誤りを修正し、帯域テキストを先頭マージする方式に変更

## [0.10.17] - 2026-07-03

### Fixed
- **精算レシートOCR（260703_18系）**: ヘッダー・端末UUID帯域の複数パスOCRを追加。折返しUUID断片の結合復元で端末識別番号 `0ed7` を取得可能に

## [0.10.16] - 2026-07-03

### Fixed
- **精算レシート端末識別番号**: 端末番号行が `-af4C` のように先頭欠落した場合に `af4c` を復元。UUID途中断片（`-babd-`）や末尾断片（`d131c08d6e76`）の誤採用を防止

## [0.10.15] - 2026-07-03

### Fixed
- **精算レシート端末識別番号**: ラベルが崩れたOCR（端未/認別/職別、`O`→`0` 等）や、端末番号UUID先頭・精算直前行からの復元に対応。登録番号やUUID途中断片は誤採用しない

## [0.10.14] - 2026-07-03

### Changed
- **精算レシート再解析**: クリックした行のみ再解析（行単位API）。一覧全体の再読み込み表示を抑制
- **画像プレビュー**: ホバーは従来どおり小さく表示、クリックで拡大モーダル表示（Esc/背景クリックで閉じる）

## [0.10.13] - 2026-07-03

### Fixed
- **PAYGATE POS売上**: ¥10 等の不正値を除外（¥980/¥1,480/¥2,980の組み合わせのみ採用）。合計−現金からPOSを推定
- **検証メッセージ**: 単価組み合わせ不正を日本語で表示

## [0.10.12] - 2026-07-03

### Fixed
- **その他支払い**: `-その他` 行の誤読（消費税534等）を除外し、内訳不一致を解消

## [0.10.11] - 2026-07-03

### Fixed
- **精算レシート金額**: ラベルと金額が行ずれしたOCR（現金売上・PAYGATE POS）を補正し、`amount_breakdown_mismatch` を解消
- **通常取引数**: 金額補正後に現金＋POSの980円単位から取引数を推定（OCRで数字欠落時）
- **検証メッセージ**: `amount_breakdown_mismatch` 等を日本語で表示

## [0.10.10] - 2026-07-03

### Fixed
- **精算レシート通常取引数**: 本番OCRで `8` が `-` と誤認されるケースを補正。返品計/取消計の `0` を誤採用しないよう通常取引数ブロックに限定
- **端末番号**: 改行折返しの短い断片（`90` 等）を結合し 32 桁 UUID を復元
- **取引数推定**: 現金売上＋PAYGATE POS の 980 円単位から合算推定

## [0.10.9] - 2026-07-03

### Fixed
- **精算レシート通常取引数**: 中盤の「精算現金」空欄行の直前の数字を優先採用（レシート右欄レイアウト準拠）

## [0.10.8] - 2026-07-03

### Fixed
- **精算レシート端末番号**: 8-4-4-4-12 形式・小文字 a～f / 数字 0～9 のみを正規化・検証。不完全な UUID 断片は採用しない

## [0.10.7] - 2026-07-03

### Fixed
- **精算レシート再解析**: 同一画像の再解析時に既存行を更新するよう修正（従来は新規行が増えるだけで表示が変わらなかった）
- **精算レシートOCR（本番OCR対応）**: ラベルと金額の別行読み取り、`15/880` スラッシュ誤認、UUID断片の結合、`端末識別番号2C0e` 形式、取引数0の現金売上からの推定（5880→6件）

### Changed
- **精算レシート一覧**: 未確定行に「再解析」ボタンを追加

## [0.10.6] - 2026-07-03

### Fixed
- **精算レシートOCR（端末・取引数）**: 端末番号(UUID)の2行折り返し読み取り、端末識別番号の登録番号断片（3000）誤検知防止、通常取引数の余白・改行対応

## [0.10.5] - 2026-07-03

### Fixed
- **精算レシートOCR（金額）**: 「￥」を先頭の「1」と誤認して `￥5,880` → `15,880` になる典型パターンを補正（カンマ区切り・連結数字の両方に対応）
- **精算レシートOCR（端末）**: 端末番号(UUID)の改行後読み取り、登録番号直後の端末識別番号（ラベル欠落時）の抽出を追加

## [0.10.4] - 2026-07-03

### Changed
- **精算レシート一覧**: 指定9項目（端末識別番号・精算日時・端末番号・小計・合計・現金売上・PAYGATE POS・通常取引数）以外の列（稼働日・現金/POS台数・在庫照合対象・状態）を非表示に整理
- **精算レシート一覧**: 画像ファイル名を最大2行＋省略表示（ホバーで全文）に変更し横スクロールを抑制

### Fixed
- **精算レシート検証**: 売上があるのに通常取引数が `0` と OCR 誤認識された場合の `unit_breakdown_invalid` 表示を解消（取引数を未確定として扱い、検証列から単価内訳警告も除外）

## [0.10.3] - 2026-07-03

### Fixed
- **OCR解析失敗（`cv2.INTER_LINEAR`）再発**: デプロイ後に OpenCV が未インストール状態（空の `cv2` モジュール）になる問題を修正。`opencv-python-headless==4.10.0.84` に固定し、デプロイ時に強制再インストール＋`INTER_LINEAR` 存在チェックを追加

## [0.10.2] - 2026-07-03

### Changed
- **精算レシートOCR**: 指定9項目（端末識別番号・精算日・精算時間・端末番号・小計・合計・現金売上・PAYGATE POS・通常取引数）の抽出を強化し、精算レシートタブの一覧・編集モーダルにすべて表示
- **精算レシートパーサー**: `精算日`/`精算時間` ラベル対応、`-PAYGATE POS` 表記の正規化、端末識別番号の改行分離読取に対応

## [0.10.1] - 2026-07-03

### Changed
- **OCR・レシート解析**: 保存データ一覧を Paygate / 精算レシートのタブで切り替え表示するよう改善（件数バッジ・種別ごとの列表示・月次サマリのタブ連動）

### Fixed
- **OCR解析失敗（`cv2.INTER_LINEAR`）**: デプロイ時に OpenCV 5.x が入り PaddleOCR 2.x と非互換になる問題を修正。`opencv-python-headless` を 4.x にピン留めし、デプロイスクリプトで全 opencv パッケージを入れ替えてから再インストールするよう変更

## [0.10.0] - 2026-07-02

### Added
- **精算レシート（PAYGATE）OCR強化・在庫照合機能を新規追加**（`PAYGATE精算レシート OCR・在庫照合 計画書 v4` に基づく実装。対象は `source_type=paygate_settlement` のみ、Paygateスクリーンショットは変更なし）
  - OCR抽出項目を拡張: 端末識別番号（`terminal_short_id`）、PAYGATE POS金額、その他支払い、稼働日（`work_date`、深夜またぎルール対応）
  - 単価構成（現金／PAYGATE POS台数）の逆算ソルバーを追加。曖昧・クレジット/その他非ゼロの場合は `unit_breakdown_status=manual` とし人手入力UIへ誘導
  - 金額整合・1の位チェックによる `blocking_errors`（確定不可）と `warnings`（確定可）の分離
  - 画像SHA一致とは別の意味的重複検知（`duplicate_receipt_candidate`）を追加
  - 精算レシートのOCR確定条件を修正（`transaction_no`/`receipt_no` 必須の既知バグを解消。Paygateスクリーンショットの確定条件は変更なし）
  - OCR行の無効化（`voided_at`等）、在庫照合対象採用フラグ（`reconciliation_eligible`、既定true・opt-out方式）を追加
  - 実在庫入力（`inventory_snapshots`）・在庫照合実行（`inventory_reconciliation_batches`/`results`）のAPI・UIを新規追加
  - 在庫照合対象は同一キー（`branch_id`+`terminal_short_id`+`work_date`）で常に1件のみに制限する部分ユニーク制約を追加
  - 精算レシート専用CSV（拡張フォーマット）のエクスポート機能を追加
  - 運用手順を `docs/ops/OCR_INVENTORY_RUNBOOK.md`（旧 `OCR_RECEIPT_RUNBOOK.md`）に集約し、月次 `adjustment_reason` レビュー手順を追記
  - 仕様書 `docs/spec/OCR_INVENTORY_RECONCILIATION_SPEC.md` を新規作成

## [0.9.29] - 2026-07-02

### Fixed
- **VZ モノグラム根本修正**: これまでの「Z」パスが実際には正しい Z の字形になっておらず、稲妻状の図形だった不具合を修正
  - 正しい Z の字形（上横棒・斜め・下横棒）に再構築し、V との重なりを最小限に調整
  - レンダリング画像で 32px・128px 双方で「VZ」と判読できることを確認したうえで反映

## [0.9.28] - 2026-07-02

### Fixed
- **サイドナビブランド**: 「管理画面」の文字が二重・スキャンライン状に見える表示を修正
  - 日本語フォント（BIZ UDPGothic 等）を明示、太字合成を無効化
- **VZ モノグラム**: Z の上横棒が V に隠れて「Vx」に見える問題を再調整（Z を右寄せ・横棒を太く）

## [0.9.27] - 2026-07-02

### Fixed
- **ブランドマーク（候補B）**: favicon・サイドナビの Z が「Vx」に見える問題を修正
  - Z をブロック字形に変更し、上横棒・下横棒を 16px でも識別可能に
  - 描画順を Z→V に変更（V を手前に重ね、重なりを維持しつつ Z を判読可能に）
- **サイドナビ**: 「フェーズ1」「管理画面」の文字化けを修正

## [0.9.26] - 2026-07-02

### Fixed
- **ログイン画面**: `LoginPage.tsx` の日本語ラベルが `?` 表示になる文字化けを修正（UTF-8 で正しい文言を復元）

## [0.9.25] - 2026-07-02

### Fixed
- **ブランドマーク**: 候補B（VZ 重なりモノグラム）を正本デザインに復元（0.9.24 の左右分離は誤り）
- **ログイン**: API 停止時に「認証サーバーに接続できません」と明示（`client.ts`, `LoginPage.tsx`）
- **API 再起動**: `restart_uvicorn.sh` に logs 作成・JWT 検証・`/api/health` 確認を追加

### Added
- **デプロイ運用**: `docs/ops/DEPLOY_TROUBLESHOOTING.md`（遅延原因と最短手順）
- **フロントのみデプロイ**: `scripts/deploy/03_frontend_only_deploy.sh`

## [0.9.24] - 2026-07-02

### Fixed
- **favicon・サイドナビブランド**（`favicon.svg`, `BrandMark.tsx`, `index.html`）
  - V/Z モノグラムを左右分離レイアウトに修正（重なりによる潰れ・文字への滲みを解消）
  - PNG フォールバック（`favicon-32.png`）追加、キャッシュバイパス `?v=2`
  - nginx: favicon の長期 immutable キャッシュを短期（1日）に変更

## [0.9.23] - 2026-07-02

### Fixed
- **円表示**: 金額から小数点以下を除去（`formatCurrency`, OCR 編集フォーム, CSV エクスポート）
  - `5880.00` → `￥5,880` / `5880` に統一

## [0.9.22] - 2026-07-02

### Changed
- **ブランドマーク統一**（favicon・サイドナビ）
  - VZ モノグラム（候補B）を管理画面・スタッフモバイルの favicon に適用
  - 管理画面サイドナビの brand-mark を同一デザインに変更

### Fixed
- **CHANGELOG 版番号の整合**（`CHANGELOG.md`）
  - 0.9.2–0.9.21 を個別デプロイ版として誤記していた記述を `[0.9.1]` へ統合（`package.json` は 0.9.1 → 0.9.22 のみが実績）

## [0.9.1] - 2026-06-11 — 2026-06-16

`package.json` は **0.9.1** のまま本番反映されていた期間の OCR 継続改善をまとめる。git 上も `6c50f6b`（0.9.1）から `45ad671`（0.9.22）まで版番号更新はなく、中間の 0.9.2–0.9.21 に相当する git tag / デプロイ版は存在しない。

### Changed — Paygate 重複除去（初回 0.9.1 反映）
- **Paygateスクリーンショット OCR**（`src/services/ocr/dedupe.py`, `src/services/ocr/parsers/paygate_screenshot.py`, `src/services/ocr_service.py`）
  - 取引番号・レシート番号が重複する行を自動で統合（スクロール重なり・半分だけ写ったキャプチャ対策）
  - 複数画像を一括解析した場合もジョブ内・既存 DB 行と突合して重複を除外
  - 重複時は項目が揃っている行（レシート番号・決済方法など）を優先して保持

### Changed — OCR 画像一覧 UI
- **OCR 画像一覧 UI**（`apps/admin-web/src/pages/ReceiptOcrPage.tsx`, `global.css`）
  - アップロード済み画像のサムネイル表示、選択削除、同一画像・同名ファイルの重複表示
  - 解析失敗時のエラーメッセージを画像カードに表示
  - カード内の文字重なりを解消する縦型レイアウトに変更
  - 解析失敗（`failed`）画像も再解析対象に含める
- **OCR 画像 API**（`src/api/ocr_routes.py`）
  - 認証付き画像ファイル取得 `GET /api/ocr/images/{id}/file` と一括削除 `DELETE /api/ocr/images` を追加

### Fixed — PaddleOCR 3.x 互換・前処理
- **PaddleOCR 3.x 互換**（`pyproject.toml`, `src/services/ocr/paddle_engine.py`）
  - 本番で `paddleocr 3.7` が paddlex 依存不足により全件解析失敗していた問題を修正（`paddleocr<3` に固定）
- **OCR 前処理・アップロード**（`src/services/ocr/image_preprocess.py`, `src/services/ocr_service.py`）
  - OpenCV 競合による `cv2.cvtColor` エラーを Pillow 前処理に切替えて解消
  - 削除済み画像と同一内容を再アップロードした際の DB 一意制約エラーを解消（復元して再利用）

### Changed — OCR 画像一覧 UI 拡張
- **OCR 画像一覧 UI**（`apps/admin-web/src/pages/ReceiptOcrPage.tsx`）
  - 表示形式の切替（サムネイル / 一覧＝ファイル名・日時のみ）
  - セクションの折りたたみ
  - 表示件数の変更（10 / 20 / 50 件）とページ送り
- **エージェントルール**（`AGENTS.md`, `.cursor/rules/version-bump.mdc`）
  - バグ修正・UI改善完了時もバージョンを上げることを明文化

### Fixed — OCR 解析の安定性
- **OCR 解析の安定性**（`restart_uvicorn.sh`, `scripts/deploy/systemd/vanzai-api.service`）
  - PaddleOCR 初回ロード時に uvicorn ワーカーが落ちて「解析に失敗しました」となる問題を修正（`--workers 1` に変更）

### Changed — OCR 画像・保存データ UI
- **OCR 画像一覧**（`apps/admin-web/src/pages/ReceiptOcrPage.tsx`）
  - 未解析状態の表示を「保留」から **「解析待ち」** に変更
- **OCR 保存データ**（`src/api/ocr_routes.py`, `ReceiptOcrPage.tsx`）
  - 解析結果行の選択削除（すべて選択含む）を追加

### Changed — OCR 表示
- **OCR 表示**（`ReceiptOcrPage.tsx`, `src/api/ocr_routes.py`）
  - 種別ラベルを「Paygate」「レシート」に短縮
  - 保存データに解析元の画像ファイル名を表示（10文字超は「・・・」で省略）
  - アップロード後の画像ファイル名を変更可能に（保存データのファイル名も連動）

### Changed — OCR 画面（選択 UI）
- **OCR 画面**（`ReceiptOcrPage.tsx`）
  - 「すべて選択」をチェックボックスからボタン表示に変更（選択解除トグル付き）

### Changed — OCR 画像プレビュー
- **OCR 画面**（`ReceiptOcrPage.tsx`）
  - サムネイル・画像ファイル名をホバー／クリックで拡大プレビュー表示
  - ファイル名の省略表示を 10 文字から 24 文字に拡張（`title` で全文表示は維持）

### Fixed — OCR 保存データ表示
- **OCR 保存データ**（`ReceiptOcrPage.tsx`）
  - 画像ファイル名の表示から拡張子（`.jpg` 等）を除外
  - テーブル内ホバープレビューが見切れる問題を修正（ポータル表示で枠外に描画）

### Fixed — Paygate スクリーンショット OCR（金額・行抽出）
- **Paygate スクリーンショット OCR**（`paygate_screenshot.py`）
  - 金額が `￥` なしの単独行（例: `980`）で読まれるケースに対応
  - 日付・時刻・ラベルが改行区切りの OCR 結果でも金額を抽出
- **OCR 画像プレビュー**（`ReceiptOcrPage.tsx`）
  - アップロード前の画像・サムネイル・保存データのファイル名でホバーが効かない／見切れる問題を修正
  - プレビューを常に画面全体へポータル表示し、トリガー付近に自動配置
- **Paygate スクリーンショット OCR 金額**（`paygate_amount.py`, `paygate_screenshot.py`）
  - ￥記号を数字（2/5/7 等）と誤認した `2980` `7980` 等を `980` に補正
  - 青文字の金額領域を強調する画像前処理を追加

### Fixed — Paygate OCR 金額
- **Paygate OCR 金額**（`paygate_amount.py`, `ocr_service.py`, `image_preprocess.py`）
  - 青文字 `￥980` 専用の OCR パスを追加し、取引行の右側読み取り・980 円フォールバックを実装
  - 2980 等の誤読補正を維持しつつ、OCR が金額行を読めないケースでも 980 円を推定
- **OCR 画面**（`ReceiptOcrPage.tsx`）
  - 金額表示を整数円表示に統一（`980.00` → `¥980`）

### Changed — OCR 解析フロー
- **OCR 画面**（`ReceiptOcrPage.tsx`）
  - 「解析」ボタンをアップロード済み画像セクションへ移動（アップロード後に解析する流れを明確化）

### Fixed — Paygate レシート番号 OCR
- **Paygate レシート番号 OCR**（`paygate_receipt.py`）
  - `レツート番号` 等のラベル誤認識、`日` 混入数字に対応しレシート番号を抽出

### Fixed — Paygate OCR パーサー
- **Paygate OCR パーサー**（`paygate_datetime.py`, `paygate_screenshot.py`, `paygate_amount.py`, `ocr_service.py`）
  - 日時の曖昧パース（`20:521`→`20:52:1`、`2034:01`→`20:34:01` 等）で厳密マッチ失敗時も行を抽出
  - 取引番号をアンカーにブロック分割し、日時が壊れていても取引行を生成
  - Paygate 向け gray + blue 2パス OCR、0行時は upscale 3パス目を追加
  - 日時未取得時の金額抽出クラッシュを修正

### Added — OCR 確定ガード・行編集
- **OCR 確定ガード**（`confirm_metadata.py`, `ocr_service.py`, `ocr_routes.py`）
  - `confirm_required=true` や検証エラー行は confirmed にできない（全体拒否）
  - DB カラム: `amount_inferred`, `amount_source`, `datetime_source`, `confirm_required`, `manually_edited`
- **OCR 行編集 UI**（`ReceiptOcrPage.tsx`）
  - 金額・日時・取引番号等の人手修正モーダル、要確認バッジ表示
- **CSV 監査列**（`export.py`）
  - 推定・要確認メタデータ列を追加
- **Vitest**（`rowDisplay.ts`）表示ラベルテスト

### Fixed — Paygate OCR メタデータ
- **Paygate OCR メタデータ**（`paygate_amount.py`, `paygate_datetime.py`, `paygate_screenshot.py`）
  - 980 円フォールバック・補正 OCR・fuzzy/missing 日時を要確認として正規化
  - `HH:MM:SS` 形式でない時刻は確定不可

### Added — OCR 保存データ削除の改善
- **OCR 保存データ削除の改善**（`ReceiptOcrPage.tsx`, `ocr_service.py`）
  - 要確認行も含めすべての保存データ行を選択・削除可能
  - 各行・各画像に「削除」ボタンを追加（確認ダイアログ付き）
  - 画像削除時に関連する解析行をカスケード soft delete

### Fixed — OCR 行削除
- 要確認行がチェックボックス選択不可のため削除できなかった問題

### Fixed — Paygate OCR 行抽出・金額解釈
- **Paygate OCR 行抽出**（`paygate_screenshot.py`, `paygate_receipt.py`）
  - 「取引番号」ラベル欠落時も取引番号・レシート番号（781…）から行を復元
  - 日時行を起点にブロック分割を強化し、8件スクショの取りこぼしを低減
- **金額解釈**（`paygate_amount.py`）
  - **1980 / 1480 を実金額として保持**（1980 を 980 に自動補正しない）
  - 2980 / 7980 等の ￥誤読のみ 980 へ補正

### Added — Paygate 保存条件
- **Paygate 保存条件**: 日付・取引番号（7桁）・レシート番号（13桁）の3つが揃った行のみ DB 保存
- レシート番号の `101…` → `781…` OCR 誤読補正
- レシート番号アンカーによるブロック分割（取りこぼし低減）
- Paygate 解析時に拡大前処理 OCR を常時マージ

### Fixed — 取引番号・レシート欠損
- 取引番号6桁（123054 等）・レシート欠損行が不完全なまま保存されていた問題
- 取引番号パターンを `1xxxxxx`（7桁）に拡張

### Added — 同一画像内の多数決補正
- **同一画像内の多数決補正**（`paygate_consensus.py`）
  - 日付: 2025/05 等の OCR 誤読を同画面の多数派日付へ補正（要確認）
  - 金額: 画面内がほぼ 980 円のとき 1980 円誤読を 980 へ補正（要確認）

### Fixed — 日付・金額誤読
- **1980 円**: ¥980 の先頭誤読として 980 へ補正（1480 円はそのまま）
- 5/6 混同による日付ズレ（2026-05-10 / 2025-06-10 等）

### Added — OCR 保存データの並び替え
- **OCR 保存データの並び替え**（`ReceiptOcrPage.tsx`, `sortRows.ts`）
  - 画像ファイル名・日付・金額・取引番号・レシート番号で昇順/降順
  - 列ヘッダークリックまたはツールバーから切替

## [0.9.0] - 2026-04-11

### Added
- **OCR・レシート解析機能**（`apps/admin-web/src/pages/ReceiptOcrPage.tsx`, `src/api/ocr_routes.py`, `src/services/ocr/`, `src/models/ocr.py`）
  - Paygate スクリーンショットと精算レシートの画像アップロード・PaddleOCR 解析
  - 年月別保存、CSV ダウンロード、確定フロー
  - 本部 CSV 突合 API/UI（列マッピング可変）
  - 自己申告（sales_reports）比較のプレースホルダ API
- **OCR 用 DB テーブル**（`alembic/versions/20260411a001_add_ocr_receipt_tables.py`）
- **運用 Runbook**（`docs/ops/OCR_RECEIPT_RUNBOOK.md`）

### Changed
- **nginx API timeout** を OCR 向けに 300s へ延長（`tools/nginx_vanzai_new.conf`）
- **pyproject.toml** に `pillow` と optional `ocr` 依存（paddlepaddle / paddleocr / opencv）を追加

## [0.8.0] - 2026-04-09

### Added
- **請求書発行の Kintone 参照 UI 拡張**（`src/api/main.py`, `src/api/schemas.py`, `src/services/invoice_service.py`, `src/services/pdf_generator.py`, `apps/admin-web/src/pages/InvoicesPage.tsx`）
  - `/api/invoices/generate` で `document_type`、`client_staff_id`、`subject`、`fixed_office_fee_amount`、`billing_date` を受け付けるようにした
  - 請求先担当者スナップショット、件名、帳票種別、固定事務局費を invoice に保持できるようにした
  - admin-web の請求生成フォームで帳票種別、担当者、件名、固定事務局費を指定できるようにした

### Changed
- **請求 PDF と請求一覧の表示を拡張**（`src/services/pdf_generator.py`, `apps/admin-web/src/types/api.ts`, `apps/admin-web/src/pages/InvoicesPage.tsx`）
  - PDF に請求先名、担当者名、住所、件名、帳票種別、請求日を表示するようにした
  - 固定事務局費を請求明細行へ追加し、請求一覧でも確認できるようにした

## [0.7.8] - 2026-04-08

### Added
- **プレイングマネージャー支払の個別設定対応**（`src/models/master.py`, `src/services/payout_service.py`, `apps/admin-web/src/pages/MasterDataPage.tsx`, `apps/admin-web/src/pages/PayoutsPage.tsx`）
  - VANZAI担当者マスタに `playing_manager_fee_type` と `playing_manager_fixed_fee` を追加
  - プレイングマネージャー支払で `配下人工×1,000円` と `固定額` を個人別に切り替え可能にした
  - 支払生成時に運営協力費を月次手入力で別行加算できるようにした

### Changed
- **VANZAI担当者支払生成ロジックを拡張**（`src/api/schemas.py`, `src/api/main.py`, `src/services/payout_service.py`）
  - `/api/payouts/generate` が `support_fee_amount` を受け付けるようにした
  - プレイングマネージャーの支払生成を backend で完結できるようにした

## [0.7.7] - 2026-04-08

### Added
- **VANZAI担当者支払の初回生成対応**（`src/services/payout_service.py`, `src/api/main.py`, `apps/admin-web/src/pages/PayoutsPage.tsx`）
  - `/api/payouts/generate` で `recipient_type=vanzai_staff` を受け付けるように変更
  - `全体統括責任者` は drv社請求税抜売上の 8% と linked worker の本人稼働分を1件に集約
  - `事務` は 固定43,200円 と 月内暦日 × 2,160円 の支払明細を自動生成

### Changed
- **VANZAI担当者マスタに linked worker 設定を追加**（`src/models/master.py`, `src/api/main.py`, `apps/admin-web/src/pages/MasterDataPage.tsx`）
  - VANZAI担当者と worker 実績主体を明示的に紐付けできるようにした
  - 全体統括責任者の linked worker は通常の worker 支払生成を抑止し、二重計上を防止

---

## [0.7.6] - 2026-04-09

### Added
- **supplier recipient の支払生成対応**（`src/api/main.py`, `apps/admin-web/src/pages/PayoutsPage.tsx`）
  - `/api/payouts/generate` で `recipient_type=supplier` を受け付けるように変更
  - PayoutsPage で取引先を選んで支払生成できるようにした
  - supplier 支払は案件指定不要であることを UI に明示

### Changed
- **DashboardPage のボタンとリンクをスタイル統一**（`apps/admin-web/src/pages/DashboardPage.tsx`）
  - 締め処理の選択ボタン群、監査ログ導線、月次一括生成などの素のボタンを `btn` 系スタイルへ統一
  - 締め候補の一括選択ボタンをチップ風デザインへ変更

---

## [0.7.5] - 2026-04-09

### Added
- **支払一覧の recipient_type UI 移行着手**（`apps/admin-web/src/pages/PayoutsPage.tsx`）
  - 一覧フィルタと種別表示を `recipient_type` 優先へ変更
  - 支払明細生成リクエストを `recipient_type` / `recipient_id` ベースへ更新
  - worker 以外の受取人生成は未対応であることを UI で明示し、誤操作を防止

### Changed
- **登録申請ページの主要アクションをスタイル統一**（`apps/admin-web/src/pages/RegistrationRequestsPage.tsx`）
  - `リンク発行`、`承認`、`却下`、`PINロック解除`、`リンク再発行` を強弱のある共通ボタンへ変更
  - 発行カードに装飾を追加し、操作部の視認性を改善

---

## [0.7.4] - 2026-04-09

### Fixed
- **公開登録リンク発行フォームのレイアウト修正**（`apps/admin-web/src/pages/RegistrationRequestsPage.tsx`）
  - 発行フォームを余白付きカードへ変更し、左端の文字が見切れる状態を解消
  - 入力欄の最小幅を上書きし、狭い幅でも崩れにくい表示へ調整

---

## [0.7.3] - 2026-04-09

### Added
- **admin-web 口座履歴 UI 改善**（`apps/admin-web`）
  - `WorkersPage` と `MasterDataPage` の振込先口座一覧で口座番号をマスキング表示に統一
  - worker / supplier 口座の新規登録・更新フォームに `有効終了日` を追加
  - 一覧テーブルに `有効終了` 列を追加し、履歴の終了日を確認可能にした
  - `有効終了日 < 有効開始日` を UI 側でバリデーション

## [0.7.2] - 2026-04-09

### Added
- **Phase 1 DBマイグレーション適用完了**（`20260408c001` ～ `20260408e001`）
  - `project_types`: `category_level`（major/middle/minor）・`parent_id` 自己参照FK 追加
  - `payout_lines`: `recipient_type`・`payee_name_snapshot`・`bank_account_snapshot_json` フィールド追加
  - `project_documents`・`project_tasks`・`sales_reports` テーブル新規追加
- **API エンドポイント追加**（`src/api/main.py`・`src/api/schemas.py`）
  - `GET/POST/PUT /api/vanzai-staff` — VANZAI担当者マスタ CRUD
  - `GET/POST/PUT /api/clients/{client_id}/staff` — クライアント担当者 CRUD
  - `GET/POST/PUT /api/workers/{worker_id}/bank-accounts` — 稼働者振込先口座 CRUD
  - `GET/POST/PUT /api/suppliers/{supplier_id}/bank-accounts` — 下請け振込先口座 CRUD
- **admin-web UI 追加**（`apps/admin-web`）
  - マスタ一覧 → 「VANZAI担当者」タブ追加（作成・編集対応）
  - マスタ一覧 → クライアント行に「担当者管理」パネル追加（担当者一覧・追加）
  - 稼働者ページ編集パネルに「振込先口座」セクション追加（口座一覧・新規登録フォーム）
- **型定義追加**（`apps/admin-web/src/types/api.ts`）
  - `VanzaiStaffItem/CreateRequest/UpdateRequest`
  - `ClientStaffItem/CreateRequest/UpdateRequest`
  - `WorkerBankAccountItem/ListResponse/CreateRequest/UpdateRequest`
  - `SupplierBankAccountItem/ListResponse/CreateRequest/UpdateRequest`

---

## [0.7.1] - 2026-04-08

### Added
- **公開登録フォーム UI** (`/public/registrations/:formType`)
  - token + PIN による本人確認パネル
  - 4フォーム種（稼働者・個人下請け/紹介者・法人下請け・紹介者身分証）に対応した動的フィールド
  - ログイン不要のアンオーセンティケートルートとして App.tsx に追加
- **身分証ファイルアップロード**（`POST /public/registrations/{form_type}/files`）
  - document_type / document_part 指定、MIME・サイズ検証、SHA256 保存
  - 同一種類/部位の旧ファイルをソフトデリート（1件1種類1部位）
  - 監査ログ: `registration_request_file_uploaded`
- **管理者ファイルダウンロード**（`GET /api/registration-requests/{request_id}/files/{file_id}`）
  - 閲覧理由（`reason`）必須クエリパラメータ
  - 監査ログ: `registration_request_file_downloaded`
  - 承認/却下後 180 日保持ポリシー適用
- **dedupe 差分比較表示**（`RegistrationRequestsPage`）
  - 申請値 vs 既存マスタ値を項目ごとに色分けハイライト（一致: 緑 / 不一致: 赤）
  - 対象フィールド: 氏名・ふりがな・電話・メール・屋号・性別・インボイス番号 など

---

## [0.6.9] - 2026-04-07

### Added
- **公開登録フォーム バックエンド**
  - `registration_requests` テーブルを正本とした受付ドメイン実装
  - token 発行・PIN 設定・PIN ロック（5回失敗）・ロック解除・再発行 API
  - 4フォーム種の submit エンドポイント（稼働者・個人・法人・紹介者身分証）
  - dedupe 候補検索（氏名+電話、メールなどで既存 workers/suppliers を照合）
- **管理画面: 登録申請管理** (`/operations/registration-requests`)
  - 申請一覧・詳細表示
  - 承認（master INSERT/UPDATE）・却下アクション
  - dedupe 候補一覧と承認対象選択 UI
  - 公開リンク発行・再発行・PIN ロック解除

---

## [0.6.8] - 2026-04-04

### Added
- **ブラウザキャッシュ対策**（`tools/vite-plugin-version-check.ts`）
  - ビルド時に `dist/version.json` を生成し `index.html` にインラインスクリプト埋め込み
  - バージョン不一致を自動検知して `location.replace` でキャッシュバイパス
  - `window.__APP_VERSION__` / `window.__APP_BUILD_ID__` を React コンポーネントに公開
- **プッシュ通知改善**（`PersonalSettingsPage`）
  - 工程別プログレス表示・タイムアウト対応
  - 通知拒否時のブラウザ別解除手順表示

---

## [0.6.7] - 2026-04-03

### Added
- **稼働可否カレンダー管理画面** (`/operations/availability-calendar`)
  - 管理者向けスタッフ横断カレンダー（月/週トグル）
  - スタッフ行にスキル資格バッジを折りたたみ表示
  - `GET /api/availability-calendar` バックエンドエンドポイント
- **Worker スキル資格フラグ** (`workers` テーブル)
  - `smoking_area_ok`, `has_p_shirt`, `has_best`, `stores_training_done`, `pioneer_training_done` 追加
  - staff-mobile 個人設定ページから更新可能
- **staff-mobile ステータスバンド** (`MobileStatusBand`)
  - 今日のアサイン・未返答・実績・稼働可否・設定を上部バンドで一覧表示

---

## [0.6.6] - 2026-04-01

### Added
- **アサイン返答モニタリング** (`/operations/assignment-responses`)
  - 返答未回収アサインの一覧・フィルタ（月・案件・スタッフ・エスカレーション）
  - 手動リマインダー再送 (`POST /api/assignments/reminders/send`)
  - リマインダー履歴・エスカレーション履歴パネル
- **週次スケジューラー**: 未返答アサインへのリマインダーメール自動送信
- **お知らせ機能** (`/operations/notices`, staff-mobile `/notices`)
  - 管理者 → スタッフへのお知らせ CRUD
  - staff-mobile 未読バッジ表示
- **支払明細 メール送付改善**
  - 送付履歴パネル（受取人候補チップ・送付先オーバーライド）
  - `GET /api/payouts` に `delivery_state=unsent|failed` フィルタ追加
  - ダッシュボードに `missing_payout_recipient` カウント追加

---

## [0.6.5] - 2026-03-31

### Added
- **案件・シフト枠 編集** (PUT /api/projects/{id}, PUT /api/shift-slots/{id})
- **アサイン 高度化**
  - 一括ステータス更新・キャンセル→再開
  - `reopen_reason` 必須（監査ログ記録）
  - 月次キャンセル履歴 (`GET /api/assignments/cancellation-history`)
  - サーバー側選択セット保存 (`GET/POST/DELETE /api/assignments/selection-sets`)
- **スタッフ稼働可否管理** (staff-mobile `/availability`, admin-web 参照)
- **worker assignment response** (staff-mobile 承認・辞退アクション + 未返答バッジ)

---

## [0.6.4] - 2026-03-30

### Added
- **staff-mobile** 初期リリース
  - `/today` 今日のアサイン・出退勤打刻
  - `/schedule` 月次スケジュール
  - `/actuals` 実績一覧
  - `/expenses` 経費申請・添付レシート
  - `/settings` 個人設定
- **経費管理** admin-web (`/billing/expenses`)
  - 承認・却下・レシートダウンロード
  - `ObjectStorage` 経由での添付ファイル保存

---

## [0.6.3] - 2026-03-28

### Added
- **マスタ管理** admin-web 拡張 (`/masters/data`, `/masters/workers`)
  - Worker・Supplier の作成・編集
  - クライアント・現場・案件種別・役割 の作成
- **単価管理** admin-web (`/masters/prices`)
  - price_rules / price_sales / price_outsource の作成・編集

---

## [0.6.2] - 2026-03-26

### Added
- **請求書・支払明細 PDF** 生成・保存・メール送信
- **支払明細 paid 更新** (`POST /api/payouts/{id}/paid`)
- **請求書・支払明細 監査ログ** 一括クイックフィルタ追加

---

## [0.6.0] - 2026-03-24

### Added
- **ダッシュボード** 月次・案件別 締め管理（ソフト/ハードクローズ・解除）
- **CSV インポート** (`/operations/csv-import`)
  - 洗い替えモード・バッチ履歴・エラープレビュー
- **監査ログ** 全文検索・クイックフィルタ・監査対象の名称解決
- **単価スナップショット** と締め後の再計算ガード

