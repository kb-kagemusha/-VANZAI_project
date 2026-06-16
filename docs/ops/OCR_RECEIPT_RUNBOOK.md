# OCR・レシート解析 運用 Runbook

## 概要

admin-web の **OCR・レシート解析**（`/operations/ocr-receipt`）で、Paygate 取引履歴スクショと精算レシート写真を解析し、年月別に保存・CSV 出力します。

## 前提

- API に PaddleOCR 依存をインストール済みであること
  ```bash
  pip install -e ".[ocr]"
  ```
- VPS メモリ 4 GB 以上推奨（本番 VPS は 6 GB — 問題なし）
- 環境変数（任意）
  - `OCR_STORAGE_ROOT=storage/ocr`
  - `OCR_ENGINE_DISABLED=1` … OCR エンジン無効（テスト用）

## 月次手順

1. admin-web にログイン（`admin` / `ops` / `accounting`）
2. 左メニュー **OCR・レシート解析** を開く
3. **Paygateスクリーンショット** または **精算レシート** の枠に画像を D&D
4. **画像をアップロード** → **解析**
5. 結果テーブルで黄色相当（検証エラー）の行を確認・修正
6. 問題なければ行を選択して **選択行を確定**
7. **月次CSV** または **全件CSV** をダウンロード

## 撮影ガイド（精算レシート）

- レシート全体が画面に入るよう真上から撮影
- 明るい場所で、指で文字を隠さない
- ブレ・ピンボケ時は撮り直し

## 本部 CSV 突合

1. 突合セクションに本部 CSV をアップロード
2. 列名（取引番号・レシート番号・日付・金額）をサンプルに合わせて調整
3. **突合実行** で一致 / OCRのみ / 本部のみ / 金額差異を確認

## nginx

API の `proxy_read_timeout` は OCR 用に **300s** を推奨（`tools/nginx_vanzai_new.conf` 参照）。

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| 503 PaddleOCR not installed | `pip install -e ".[ocr]"` を実行し API 再起動 |
| libGL.so.1 エラー | `pip uninstall opencv-contrib-python opencv-python` 後 `pip install opencv-python-headless` |
| 解析が遅い | 同時実行を避ける（モデルはシングルトン＋ロック） |
| 取引が重複 | 同一取引番号・レシート番号は解析時に自動統合。既に登録済みの行はスキップ（未確定行はより完全なキャプチャで上書き更新） |
| 行が空 | 撮影品質を見直し、手入力で PATCH 修正 |
