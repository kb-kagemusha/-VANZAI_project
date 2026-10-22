# 公式LINE リッチメニューの公開（A1）

対象：運営（管理者）。DEC-064、詳細設計 `docs/ops/LINE_WORKER_DAILY_OPERATIONS_DESIGN_A0_A1_2026-10-22.md` §8・§16 I-06

## 何が決まるか

- 稼働者の公式LINEのメニュー画像と、押せる範囲。
- **Webhookで「押してよい機能」**。最後に公開した記録の `enabled_actions` だけが有効。公開記録がないうちは、①⑤⑥を押しても「この機能はまだご利用いただけません」と返る。

## A1 の内容

| パネル | 位置（2500×1686 の6分割） | A1 |
|---|---|---|
| ①起床報告 | 上段・左 | 押せる（`wk_wake`） |
| ②出勤報告 | 上段・中 | 押せない（画像に「準備中」） |
| ③退勤報告 | 上段・右 | 押せない（画像に「準備中」） |
| ④販売報告 | 下段・左 | 押せない（画像に「準備中」） |
| ⑤受託済みの発注依頼書 | 下段・中 | 押せる（`wk_orders`） |
| ⑥スケジュール確認 | 下段・右 | 押せる（`wk_schedule`） |

画像の配置が上の表と違う場合は、`scripts/line/rich_menu/a1.json` の `bounds` を直してから公開する。

## 画像

- A1 の画像は `scripts/line/rich_menu/a1.png`（2026-10-22 に公開したもの）。作り直すときは `scripts/line/rich_menu/make_a1.py` の文言・色を直して実行する。

## 画像の条件

- 2500×1686 ピクセル、PNG または JPEG、1MB 以下。
- 押せないパネルには「準備中」と分かる表示を入れる。

## 公開の手順

1. 画像をVPSへ置く（デプロイ後は `scripts/line/rich_menu/a1.png` がVPSにもある）。
2. VPSで次を実行する（`.env` の値は表示しない）。

```bash
cd /var/www/vanzai
set -a; . ./.env; set +a
.venv/bin/python scripts/line/rich_menu.py check --stage a1
.venv/bin/python scripts/line/rich_menu.py apply --stage a1 --image scripts/line/rich_menu/a1.png --by <自分の名前>
.venv/bin/python scripts/line/rich_menu.py status
```

3. 検証用のLINE（運営の本人LINE。稼働者として紐付け済み）で、①⑤⑥を押して返事を確認する。
   - テスト区分の依頼書を受諾しておくと、「【テスト】」付きの予定で確認できる（起床状況一覧には出ない）。

## 失敗したとき

- 作成・画像・既定化のどこかで止まった場合、公開記録は残らない（Webhookの有効な機能は前のまま）。もう一度 `apply` する。
- `status` で「LINE上の既定メニューと公開記録が一致しません」と出たら、もう一度 `apply` する。
- 古いメニューが残っている人から無効な機能が押されても、「まだご利用いただけません」と返るだけで記録は変わらない。

## 次の段階

②③④を公開するときは、`scripts/line/rich_menu/<段階>.json` を作り、`enabled_actions` と押せる範囲を一致させて `apply` する。
