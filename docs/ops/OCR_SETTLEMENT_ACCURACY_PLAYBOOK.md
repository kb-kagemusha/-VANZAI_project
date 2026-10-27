# 精算レシート OCR 精度向上プレイブック

更新日: 2026-07-06  
対象: Paygate **精算レシート**（`paygate_settlement`）の OCR 読取・パース  
関連: `docs/ops/OCR_STACK_REVIEW_REQUEST_2026-06-16.md`（スタック全体レビュー）、`CHANGELOG.md`（版ごとの変更履歴）

---

## 1. 目的（AI・開発者向け）

本ドキュメントは、精算レシート OCR で繰り返し実施してきた**精度向上施策の設計思想と実装の所在**をまとめたものです。  
新しい誤読パターンが出たときは、まずここを読み、**テストケース追加 → 最小修正**の順で対応してください。

**正本の優先順位**

1. 本番 OCR テキスト（`ocr_source_images` / 保存済み `full_text`）
2. `tests/test_ocr_parsers.py` の `PRODUCTION_OCR_TEXT_*` フィクスチャ
3. `tests/test_settlement_layout.py` の日時・レイアウト単体テスト
4. 本ドキュメント

---

## 2. アーキテクチャ概要

```
[画像アップロード]
    → run_settlement_ocr()     … 複数帯域の前処理 + PaddleOCR マージ
    → PaygateSettlementParser  … 正規化 + フィールド抽出
    → validation / confirm_metadata … 要確認・確定可否
    → admin-web 確認パネル      … 人手修正・確定
```

| レイヤー | ファイル | 役割 |
|---------|----------|------|
| マルチパス OCR | `src/services/ocr/settlement_ocr.py` | ヘッダー・識別番号・**日時**・UUID 帯などを個別に拡大 OCR しマージ |
| エンジン | `src/services/ocr/paddle_engine.py` | PaddleOCR 2.x（日本語） |
| 前処理 | `src/services/ocr/image_preprocess.py` | リサイズ・コントラスト・アップスケール |
| 日時レイアウト | `src/services/ocr/parsers/settlement_layout.py` | 精算タイトル直下の日時、行ペアリング |
| 精算パーサー | `src/services/ocr/parsers/paygate_settlement.py` | 端末番号・金額・識別番号・全体正規化 |
| 端末番号 | `src/services/ocr/parsers/settlement_terminal_id.py` | UUID 組立・部分復元 |
| 金額 | `src/services/ocr/parsers/settlement_amount.py` | ノイズ除去・桁補正 |
| 通常取引数 | `src/services/ocr/parsers/settlement_transaction_count.py` | 精算現金直前ブロックから件数 |
| 信憑性 | `src/services/ocr/parsers/ocr_field_confidence.py` | 行信頼度 × 抽出方法 |

**設計原則**: OCR エンジンは「文字列を出す」だけ。ドメイン知識（レシート印字順・典型誤読）はパーサー側に集約する。

---

## 3. 精算レシートの印字順（パースの前提）

```
端末識別番号 (4桁 hex)
    ↓
精算（タイトル）
    ↓
YYYY/MM/DD HH:MM:SS   ← 精算日・精算時間（1行または2行）
    ↓
端末番号: UUID (8-4-4-4-12、折り返し2行あり)
    ↓
小計 → 合計 → 現金売上 → … → 通常取引数
```

日時は **スラッシュ区切り日付 + コロン時刻** が正規だが、OCR では区切りが欠落しやすい（後述）。

---

## 4. 実施してきた施策一覧

### 4.1 マルチパス OCR（帯域分割）

**問題**: 1枚全体を1回 OCR すると、感熱紙の薄い上段（識別番号・日時）や折り返し UUID が欠落する。

**対策** (`settlement_ocr.py`):

| 帯域関数 | 目的（おおよその Y 範囲） |
|----------|-------------------------|
| `preprocess_settlement_header_band` | 登録番号・会社名上段 |
| `preprocess_settlement_id_line_band` | 端末識別番号〜精算タイトル |
| `preprocess_settlement_datetime_band` | **精算日時行**（スラッシュ・コロン欠落対策） |
| `preprocess_settlement_terminal_band` | 端末番号 UUID 前半 |
| `preprocess_settlement_uuid_mid_band` | UUID 折り返し中腹 |
| `preprocess_settlement_uuid_wide_band` | UUID 広域 |
| `preprocess_for_ocr` / `preprocess_upscaled_for_ocr` | 全体フォールバック |

各パス結果は `merge_ocr_results()` で行単位マージ（高信頼度・長い行を優先）。

### 4.2 日時正規化・ペアリング

**問題例**:

| OCR 出力 | 意味 | 対策 |
|----------|------|------|
| `2026/07/04 23:04:34` | 正常 | `_DATETIME_RE` で一発抽出 |
| `2026/07104` | 月日結合 | `_DATE_MERGED_SLASH_RE`、スラッシュ補正 |
| `202607104` | 9桁・区切りなし | **`_parse_compact_date_from_digits`（1桁ノイズ除去）** |
| `2310434` | 7桁・コロンなし | `_repair_seven_digit_time` |
| `23:0434` | 分秒結合 | `(\d{2}):(\d{4})` 分割 |
| 日付行と時刻行が別行 | 分割読取 | `_pair_date_time_from_lines`（最大ギャップ 3〜4 行） |
| `清算` / `清尊` | 精算の誤読 | `_normalize_settlement_text` で `精算` に統一 |

**実装正本**: `settlement_layout.py` の `_normalize_datetime_line`, `_parse_settlement_date_from_text`, `_parse_settlement_time_from_text`, `extract_settlement_datetime`

### 4.3 端末識別番号（4桁）

**問題**: `9810` / `981e` / `9sf0` / `980` など `98f0` 系の誤読。

**対策** (`paygate_settlement.py`, `settlement_terminal_id.py`):

- 明示ラベル行 `端末識別番号:` の優先
- `98f0` ファミリへの正規化 (`normalize_settlement_terminal_short_id`)
- 端末番号 UUID 先頭 4 桁との整合スコアリング

### 4.4 端末番号（UUID 32hex）

**問題**: 2行折り返し、日時ノイズ混入、16進以外文字、部分抽出のみ。

**対策**:

- 高信頼度 OCR 行からの UUID 行検出 (`_extract_terminal_id_from_confident_ocr_lines`)
- ガベージ行除外 (`_line_looks_like_datetime_uuid_noise`)
- トークン並べ替え・部分セグメントからの復元 (`recover_terminal_id_from_partial_segments`)
- UI: 8-4-4 / 4-12 の2行表示、部分抽出時は確定不可

### 4.5 金額

**問題**: 登録番号や電話番号の数字列を小計・合計と誤認。

**対策** (`settlement_amount.py`, `settlement_amount_recovery.py`):

- レイアウト順（小計→合計→現金売上）での抽出
- 妥当な金額レンジ・桁数チェック
- 弱いヘッダ金額の上書き（subtotal / cash から total 補完）

### 4.6 通常取引数

**問題**: 金種内訳の数字と混同。

**対策**: `精算現金` 空欄行の直前ブロックのみを参照 (`settlement_transaction_count.py`)。

### 4.7 OpenCV / Paddle 互換（VPS）

**問題**: OpenCV 5.x で `cv2.INTER_LINEAR` 欠落 → OCR 全体失敗。

**対策**: デプロイ時 `opencv-python-headless==4.10.0.84` を強制（`02_app_deploy.sh`）。

### 4.8 UI・運用フロー

- 確認パネルで画像と読取データを並列表示、フィールド単位編集
- 信憑性色分け（97%以上黒 / 85–96% 青 / 85%未満オレンジ）
- `pending_review` → 人手修正 → **確定**（検証欄は「確定済」）
- 確定済み行の再解析禁止（監査・データ整合）
- 精算日画面表示: `YYYY/MM/DD`（`formatSettlementRecordDate`）

---

## 5. 典型インシデントと直し方

### 5.1 精算日時が両方 null（2026-07-06: 98f0 / 2026/07/04 23:04:34）

**症状**: 端末番号・金額は取れるが `record_date` / `record_time` が空。

**原因**: OCR が `2026/07/04 23:04:34` を **`202607104` + `2310434`** のように区切りなしで2行出力。8桁日付パーサは 9 桁を処理できなかった。

**修正**: `_parse_compact_date_from_digits` で 9 桁から 1 桁除去して `YYYYMMDD` を復元。日時専用 OCR 帯を追加。

**再発防止テスト**:

- `tests/test_settlement_layout.py::test_extract_settlement_datetime_handles_nine_digit_compact_date_and_seven_digit_time`
- `tests/test_ocr_parsers.py::test_paygate_settlement_parser_handles_production_ocr_text_260706_98f0_compact_datetime`

### 5.2 新しい誤読が出たときの手順

1. 本番またはローカルで `run_settlement_ocr` → `full_text` を取得
2. `PRODUCTION_OCR_TEXT_<日付>_<端末>` として `tests/test_ocr_parsers.py` に貼る
3. 失敗する最小断言を書く（日付・時刻・端末・金額のうち欠けているもの）
4. `settlement_layout.py` または `paygate_settlement.py` を**1パターンずつ**修正
5. `pytest tests/test_settlement_layout.py tests/test_ocr_parsers.py -k settlement` を実行

---

## 6. テストの見方

```bash
# 日時レイアウト単体
pytest tests/test_settlement_layout.py -q

# 精算パーサー統合（PRODUCTION_OCR_TEXT_* 多数）
pytest tests/test_ocr_parsers.py -k "paygate_settlement or settlement" -q

# 端末番号
pytest tests/test_ocr_settlement_terminal_id.py tests/test_ocr_settlement_short_id_98f0.py -q
```

`PRODUCTION_OCR_TEXT_*` は **実際の OCR 出力をそのまま保存したフィクスチャ**です。修正時に削除・弱めないこと。

---

## 7. あえてやっていないこと（スコープ外・リスク）

- 汎用 LLM による読取（監査・再現性の観点から未採用）
- 金額の固定フォールバック（例: 980 円固定）は Paygate SS 側の歴史的措置のみ。精算レシートには適用しない
- 確定後の OCR 上書き（データ正本保護のため禁止）

---

## 8. 関連ファイル早見表

| 変更したい内容 | まず見るファイル |
|----------------|------------------|
| 日時の読取 | `settlement_layout.py`, `settlement_ocr.py` |
| 端末識別番号 | `paygate_settlement.py`, `settlement_terminal_id.py` |
| 端末番号 UUID | `paygate_settlement.py`, `settlement_terminal_id.py` |
| 金額 | `settlement_layout.py`, `settlement_amount.py` |
| OCR  pass 追加 | `settlement_ocr.py` |
| 確定・要確認ルール | `confirm_metadata.py`, `validation.py` |
| 画面表示 | `ReceiptOcrPage.tsx`, `OcrSavedRowReviewModal.tsx` |

---

## 9. 変更履歴（抜粋）

詳細は `CHANGELOG.md` を参照。主な版:

- **0.10.67〜0.10.69**: 98f0 系端末・日時ガベージ・表示形式
- **0.10.71**: 精算日表示 `YYYY/MM/DD`
- **0.10.72**: 9桁コンパクト日付・日時 OCR 帯・確定済検証表示
