# VANZAI OCR スタック レビュー依頼文

更新日: 2026-06-16  
対象バージョン: admin-web / staff-mobile **Ver.0.9.15**（本番 VPS 反映済み）

---

## 1. 他 AI への依頼文（このままコピー可）

以下は、VANZAI 案件管理システムに追加した **OCR・レシート解析機能** の技術スタックについてのレビュー依頼です。

**目的**: Paygate 決済の取引履歴スクリーンショットと精算レシート写真から、取引番号・レシート番号・日時・金額などを自動抽出し、月次 CSV 出力・本部 CSV 突合に使う。

**現状の不満**: 同じ形式の画像でも解析成功率が不安定。特に Paygate スクリーンショットで、青文字の金額 `￥980` が読めない、日時が壊れて全行スキップされる、レシート番号が `-` になる、などの問題が繰り返し発生している。パーサー改善を重ねているが、根本的に **OCR エンジン（PaddleOCR）の選択が誤り** ではないか疑問がある。

**レビューしてほしいこと**:

1. 現行構成（PaddleOCR 2.x + ドメイン特化パーサー + 複数前処理パス）で **実運用に耐えるか**
2. **別の OCR エンジン／アーキテクチャに切り替えるべきか**（切り替えるなら候補と理由）
3. 現行スタックを維持する場合の **残存リスク** と **優先すべき改善**
4. **980 円固定フォールバック** などビジネス仮定に依存した実装の妥当性
5. 会計・監査観点で **人手確認フロー** として足りているか

可能なら次の形式で返答してください。

1. **重大な懸念点**（運用停止・誤請求リスクにつながるもの）
2. **OCR エンジン継続 vs 変更** の推奨（理由付き）
3. **変更する場合** の推奨案（コスト・工数・精度のトレードオフ表）
4. **継続する場合** の優先改善 TOP5
5. **このまま進めてよい点**
6. **追加で確認すべき未決事項**

---

## 2. ビジネスコンテキスト

| 項目 | 内容 |
|------|------|
| 利用者 | 本部オペレーション（`admin` / `ops` / `accounting` ロール） |
| 画面 | admin-web `/operations/ocr-receipt`（OCR・レシート解析） |
| 月次運用 | 画像アップロード → 解析 → 行の確認・修正 → 確定 → CSV ダウンロード |
| 突合 | 本部から送られる CSV と OCR 結果を突合（取引番号・レシート番号・日付・金額） |
| データ正本 | PostgreSQL `ocr_extracted_rows`（確定前は `pending_review`、確定後 `confirmed`） |
| 監査 | `audit_log` にアップロード・解析・確定を記録 |

**重要**: 金額は請求・支払の前段データとして使われる可能性がある。OCR 誤読がそのまま確定されると会計リスクになる。

---

## 3. 現行アーキテクチャ概要

```
[admin-web ReceiptOcrPage]
        │ multipart upload / POST parse
        ▼
[FastAPI /api/ocr/*]  ──►  [OcrService]
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
            [ObjectStorage] [PaddleOCR] [Parser Registry]
            storage/ocr/    paddle_engine   paygate_screenshot
                                              paygate_settlement
                    │
                    ▼
            [PostgreSQL ocr_* tables]
```

### 3.1 レイヤー分担

| レイヤー | 責務 | 実装 |
|---------|------|------|
| OCR エンジン | 画像 → テキスト行（座標・信頼度付き） | PaddleOCR 2.x（日本語） |
| 前処理 | リサイズ・青チャンネル分離・アップスケール | Pillow（`image_preprocess.py`） |
| パーサー | OCR テキスト → 構造化行 | 正規表現 + ヒューリスティクス |
| 検証 | 必須項目・桁数チェック | `validation.py` |
| 重複排除 | スクロール重なり・半端キャプチャ | `dedupe.py` |
| 突合 | 本部 CSV vs OCR 行 | `reconciliation.py` |

**設計思想**: 汎用 OCR はエンジンに任せ、**ドメイン知識はパーサーに集約**。PaddleOCR は「テキスト抽出器」、ビジネスロジックは自前。

---

## 4. OCR エンジン詳細

### 4.1 採用エンジン

| 項目 | 値 |
|------|-----|
| エンジン | **PaddleOCR**（Baidu PaddlePaddle 系） |
| バージョン制約 | `paddleocr>=2.7.0,<3.0.0`（3.x は paddlex 依存で本番失敗したため固定） |
| 言語 | `lang="japan"` |
| GPU | 不使用（`use_gpu=False`） |
| インストール | `pip install -e ".[ocr]"`（optional dependency） |
| 依存 | `paddlepaddle`, `opencv-python-headless`, `pillow` |

### 4.2 エンジン実装の特徴

- **遅延ロード + スレッドロック**: プロセス内シングルトン、`_parse_lock` で同時解析を直列化
- **API 互換**: PaddleOCR 2.x の `.ocr()` と 3.x の `.predict()` を分岐（実運用は 2.x 固定）
- **テスト時**: `OCR_ENGINE_DISABLED=1` で無効化、パーサーは `run_ocr_from_text()` でモック

### 4.3 本番インフラ制約

| 項目 | 値 |
|------|-----|
| VPS | 6 GB RAM（Xserver VPS） |
| API 起動 | **uvicorn `--workers 1` 必須**（workers 2 だと PaddleOCR 読み込みで OOM・子プロセス死亡） |
| メモリ | PaddleOCR 1 プロセスあたり **1 GB 超** |
| nginx | `proxy_read_timeout 300s` 推奨（解析に数十秒かかる） |
| OpenCV | `opencv-python-headless` 必須（`libGL.so.1` エラー回避） |

---

## 5. 対象ドキュメント種別（source_type）

### 5.1 `paygate_screenshot`（Paygate 取引履歴スクリーンショット）

**入力**: スマホで Paygate アプリ／Web の取引一覧を撮影した JPEG/PNG。1 枚に複数取引行。

**抽出フィールド**:

| フィールド | 説明 |
|-----------|------|
| `transaction_no` | 取引番号（6〜8 桁） |
| `receipt_no` | レシート番号（13 桁、`781` 始まりが多い） |
| `record_date` / `record_time` | 取引日時 |
| `amount` | 金額（現状ほぼ **980 円固定** の運用） |
| `payment_method` | 決済方法（例: クレジット） |

**UI ラベル**: 「Paygate」

### 5.2 `paygate_settlement`（精算レシート写真）

**入力**: たばこ店等の精算レシート全体写真。1 枚 1 行。

**抽出フィールド**: 精算日時、合計、現金売上、クレジット売上、取引数、端末番号、店舗名 など

**UI ラベル**: 「レシート」

**パーサー**: 厳密な日時正規表現 `\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}` に依存（スクリーンショットほど曖昧パースは未実装）

---

## 6. 処理パイプライン（Paygate スクリーンショット）

```
画像バイト
  │
  ├─► preprocess_for_ocr()          … グレースケール強化 + 青文字コントラスト
  │       └─► run_ocr()  ──┐
  │                        ├─► merge_ocr_results()
  ├─► preprocess_blue_amount_channel()  … 青チャンネル分離（黒文字化）
  │       └─► run_ocr()  ──┘
  │
  ├─► [0 行の場合] preprocess_upscaled_for_ocr() → run_ocr() → merge
  │
  ▼
PaygateScreenshotParser.parse()
  ├─ normalize_paygate_ocr_text()     … `2026,06/10` → `2026/06/10` 等
  ├─ _iter_paygate_blocks()           … 日付 or 取引番号でブロック分割
  ├─ extract_fuzzy_datetime()         … `20:521`→`20:52:1`, `2034:01`→`20:34:01`
  ├─ extract_paygate_receipt_no()     … `レツート番号` 等の誤認識対応
  ├─ extract_paygate_amount()         … ￥誤読補正 + 980 円フォールバック
  └─ dedupe_paygate_screenshot_rows()
```

---

## 7. ビジネス仮定・ヒューリスティクス（要レビュー）

以下は **仕様書に明文化されておらず**、実装時の暫定判断として入っている。レビュー対象。

| 仮定 | 実装 | リスク |
|------|------|--------|
| Paygate 取引金額は **常に 980 円** | OCR が金額を読めない場合 `_PAYGATE_DEFAULT_AMOUNT = 980` を推定 | 他金額取引が出たら **サイレント誤り** |
| `￥` は数字 `2`/`7` と誤認される | `2980`/`7980` → `980` に補正 | 実際に 2980 円の取引があると誤補正 |
| レシート番号は `781` で始まる 13 桁が多い | `781` 始まりを優先採用 | フォーマット変更で破綻 |
| 日時が壊れていても取引番号があれば行を生成 | `datetime_inferred: fuzzy_or_missing` を raw_payload に記録 | 日時 NULL の行が CSV に出る |
| 青文字金額は PaddleOCR が苦手 | 3 パス OCR + 空間座標ベースの右列読み取り | 根本解決になっていない |

---

## 8. 既知の問題（実例・本番調査ベース）

### 8.1 同形式画像で成功／失敗が分かれる

| 画像 | ファイル名 | 結果（0.9.14 以前） | 原因 |
|------|-----------|-------------------|------|
| 失敗例 | `244635_0_0.jpg` | `No structured rows extracted` | OCR 日時が `20:521`, `2034:01`, `2026,06/10` 等に壊れ、厳密正規表現で全行スキップ |
| 成功例 | `244636_0_0.jpg` | 完了 | 日時の一部が偶然マッチ。金額行は依然 OCR 不可なことが多い |

**0.9.15 対応後**: 失敗例を再解析 → **4 行抽出・完了**（ただし日時・レシート番号にノイズ残存の可能性）

### 8.2 PaddleOCR の構造的弱点（本番 OCR 生テキストより）

| 症状 | 頻度感 | 例 |
|------|--------|-----|
| 青文字 `￥980` が読めない | **高（〜40% 失敗感）** | 金額行が `980` のみ、または `UBO!` / `086台` 等のゴミ |
| `￥` を先頭数字と誤認 | 中 | `2980`, `7980` |
| 日時のコロン・桁ずれ | 高 | `20:521`, `2034:01`, `2033:0.` |
| レシート番号ラベル誤認 | 中 | `レツート番号`、数字中に `日` 混入 `78101日10557310` |
| 画面撮影のモアレ・反射 | 高 | 同一端末・同一画面でも撮影条件で品質が大きく変動 |

### 8.3 インフラ・運用で起きた問題（CHANGELOG より）

| 問題 | 対処 |
|------|------|
| PaddleOCR 3.7 + paddlex 不足で全件失敗 | `paddleocr<3` にピン留め |
| `libGL.so.1` なしで OpenCV クラッシュ | `opencv-python-headless` |
| `--workers 2` で Child process died | `--workers 1` 強制 |
| nginx 120s タイムアウト | 300s 推奨（root 権限で手動反映が必要な場合あり） |

### 8.4 パーサー／アーキテクチャ上の残課題

- **精算レシート** (`paygate_settlement`) は曖昧日時パース未対応
- **実画像 E2E テストなし**（PaddleOCR はすべてモック。本番品質は手動確認のみ）
- **信頼度スコア** を UI で十分に活用していない（低信頼行の強調表示は限定的）
- **金額フォールバック** が「推定」と分かる UI 表示が弱い
- パーサー改善のたびに **正規表現・特例が増加** しており、保守コストが上昇中

---

## 9. テストカバレッジ

| テストファイル | 内容 | PaddleOCR 実機 |
|---------------|------|----------------|
| `tests/test_ocr_parsers.py` | パーサー基本・重複排除 | モックテキスト |
| `tests/test_ocr_paygate_amount.py` | 金額補正・980 フォールバック | モック |
| `tests/test_ocr_paygate_receipt.py` | レシート番号抽出 | モック |
| `tests/test_ocr_paygate_datetime.py` | 曖昧日時（失敗画像テキスト fixture） | モック |
| `tests/test_ocr_api.py` | API・CSV・突合（OCR はモック） | モック |

**ギャップ**: 実画像 golden test、OCR エンジン精度ベンチマーク、回帰用の画像セットがない。

---

## 10. 代替案候補（レビュー時の比較軸）

レビュー AI は以下を比較検討してください。

| 案 | 概要 | 想定メリット | 想定デメリット |
|----|------|-------------|---------------|
| **A. 現状維持** | PaddleOCR 2.x + パーサー強化継続 | 追加コストゼロ、オンプレ完結、個人情報が外部に出ない | 青文字・画面撮影に弱い。特例コード増加 |
| **B. クラウド汎用 OCR** | Google Cloud Vision / AWS Textract / Azure DI | 精度・安定性向上 | 従量課金、API キー管理、画像がクラウド送信、レイテンシ |
| **C. 別 OSS エンジン** | Tesseract 5 + 日本語学習、EasyOCR、docTR 等 | Paddle より良いケースあり | 評価工数、日本語 UI スクショ向けか未検証 |
| **D. ハイブリッド** | Paddle で粗抽出 → 金額・日時だけクラウド or 専用モデル | コスト抑制しつつ弱点補完 | 複雑化、2 系統の運用 |
| **E. 入力品質改善** | アプリ内スクリーンショット共有、解像度ガイド | OCR 以前の問題解消 | 運用変更が必要、撮影習慣の変更 |
| **F. 半自動化** | OCR は候補提示のみ、金額・日時は人手必須 | 会計リスク最小 | 事務コスト削減効果が薄い |

---

## 11. レビュー観点チェックリスト

### 11.1 技術選定

- [ ] PaddleOCR は「日本語のスマホ UI スクリーンショット」に適しているか
- [ ] パーサーにドメイン知識を載せる設計は、長期的に保守可能か
- [ ] 複数 OCR パス + merge はコスト（時間・メモリ）に見合うか
- [ ] `--workers 1` 制約下で大量画像の一括解析は現実的か

### 11.2 会計・運用

- [ ] 980 円フォールバックを「確定可能な値」として扱ってよいか
- [ ] `pending_review` → 人手修正 → `confirmed` のフローは十分か
- [ ] 突合（本部 CSV）だけでは防げない誤りは何か
- [ ] 監査ログで「推定値だった」ことを後から追えるか（現状: `raw_payload.amount_inferred` 等）

### 11.3 品質保証

- [ ] 実画像ベースの回帰テストは必須か
- [ ] 成功率の KPI（例: 95% 自動抽出）を定義すべきか
- [ ] 低信頼行を自動で「要確認」に落とすべきか

### 11.4 セキュリティ・コンプライアンス

- [ ] レシート画像に個人情報・決済情報が含まれる。クラウド OCR 送信は許容されるか
- [ ] 画像保管期間・削除ポリシーは十分か（現状: soft delete のみ）

---

## 12. 関連ファイル一覧

```
# API・サービス
src/api/ocr_routes.py
src/services/ocr_service.py
src/models/ocr.py

# OCR コア
src/services/ocr/paddle_engine.py
src/services/ocr/image_preprocess.py
src/services/ocr/merge_results.py
src/services/ocr/validation.py
src/services/ocr/dedupe.py
src/services/ocr/reconciliation.py
src/services/ocr/export.py

# パーサー
src/services/ocr/parsers/registry.py
src/services/ocr/parsers/paygate_screenshot.py
src/services/ocr/parsers/paygate_settlement.py
src/services/ocr/parsers/paygate_amount.py
src/services/ocr/parsers/paygate_receipt.py
src/services/ocr/parsers/paygate_datetime.py

# フロント
apps/admin-web/src/pages/ReceiptOcrPage.tsx

# 運用・依存
docs/ops/OCR_RECEIPT_RUNBOOK.md
pyproject.toml  # [project.optional-dependencies] ocr
CHANGELOG.md    # 0.9.0〜0.9.15 の OCR 変更履歴
```

---

## 13. 付録 A: 失敗画像の OCR 生テキスト例（抜粋）

`244635_0_0.jpg`（image_id: `01KV7FHT6F2BXFNJ4GVCRDGQJE`）から得られたテキストの典型:

```
取引番号
1230567
レシート番号
7810946337325
2026/06/10
20:521
取引番号
1230557
レシート番号
7810923797325
2026/06/10
2034:01
```

→ 取引番号・レシート番号は読めるが、**日時フォーマットが壊れている** のが失敗の主因だった（0.9.15 で曖昧パース対応）。

---

## 14. 付録 B: 金額行の OCR 生テキスト例

成功・失敗に関わらず、金額行はしばしば次のようになる:

```
2026/05/10 20:52:59 980        ← ￥ が消えるが数字は残る（理想に近い）
2026/05/10 20:52:59 UBO!       ← 完全に読めない
2026/05/10 20:52:59 2980       ← ￥ を 2 と誤認（補正で 980 に）
（金額行自体が存在しない）      ← フォールバック 980 が発動
```

---

## 15. 付録 C: 本番検証結果（0.9.15 デプロイ後）

失敗画像 `244635_0_0.jpg` の再解析結果:

```
status: completed（以前は failed / No structured rows extracted）
抽出: 4 行
  1230567  2026-06-10  20:52:1   980
  1230543  2026-06-10  20:34:01  980
  1230542  (日時なし)              980
  1230501  2025-06-10  19:02:00  980
```

→ **構造化行の抽出は改善** したが、金額はほぼ推定 980、日時にもノイズが残る。

---

## 16. 未決事項（プロダクトオーナー判断待ち）

1. Paygate 取引金額は将来も **980 円のみ** か
2. OCR 自動抽出の **許容成功率**（何 % 未満ならエンジン変更するか）
3. クラウド OCR への画像送信は **社内ポリシー上許容されるか**
4. 低信頼・推定値の行を **確定不可** にするルールを入れるか
5. 精算レシートも同レベルの曖昧パース投資をするか

---

*この文書は他 AI へのレビュー依頼用です。コード変更の正本ではありません。*
