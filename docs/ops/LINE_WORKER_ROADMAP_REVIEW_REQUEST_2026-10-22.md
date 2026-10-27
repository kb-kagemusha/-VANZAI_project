# 統合計画のレビュー依頼文（他AI向け）

以下をそのままレビューAIへ渡してください。レビュー対象は計画です。コードの変更・設定変更・デプロイ・ユーザーへの通知は依頼していません。

---

VANZAI の「稼働者向け公式LINE機能 統合計画」を、批判的にレビューしてください。要望を増やすことではなく、目的に対する順番の妥当性、計画書どうしの食い違い、作り直しや不整合が起きる箇所を見つけることが目的です。

## 対象

- 主文書：`docs/ops/LINE_WORKER_ROADMAP_2026-10-22.md` v0.2
- 関連する計画書（主文書 §0 の表）：
  - `docs/ops/LINE_WORKER_A1PLUS_PLAN_2026-10-22.md` v0.3
  - `docs/ops/LINE_WORKER_WEB_PORTAL_PLAN_2026-10-22.md` v0.1
  - `docs/ops/LINE_WORKER_DAILY_OPERATIONS_DESIGN_A0_A1_2026-10-22.md` v0.5（実装済みの設計）
  - `docs/ops/LINE_WORKER_DAILY_OPERATIONS_PLAN_2026-10-21.md` v0.9（方針）
- 決定記録：`docs/decisions/DECISION_LOG.md` の DEC-032・039・042・063〜070

## 最初に読むもの

1. `AGENTS.md`（正本、非破壊、金額の再現性、バージョンの付け方、入力画面の規則）
2. 主文書（§4 の決定事項はユーザーが確定したもの。推奨・提案と区別すること）
3. 関連する計画書と決定記録

実装の照合先（読める場合）：

- `src/models/line_daily.py`、`src/models/order_request.py`、`src/models/line_order.py`
- `src/services/worker_schedule.py`、`src/services/line_daily.py`、`src/services/line_order.py`、`src/services/order_request_service.py`
- `src/domain/order_schedule.py`（勤務グループと単価。日付の重なりの検証）
- `src/api/line_registration_routes.py`（既存のLIFF・IDトークン検証）、`src/models/line_registration.py`（冪等キー・受付通知の再送）
- `scripts/line/rich_menu.py`、`scripts/line/rich_menu/a1.json`

`.env` と `.env20261006` は読まない・変更しない。ファイルを変更しない。公式ドキュメントの最新確認が必要な箇所は、その必要性と確認結果を分けて書くこと。

## 特に見てほしい点

主文書 §10 の7項目。特に次の3つ。

1. 順番（①日付指定の受諾・参加カレンダー → ②Web確認画面（見込みを含む）→ ③変更依頼 → ④起床の監視）が目的に対して妥当か。
2. ①で作る共通部分（LIFFの本人確認・公開の止め方・カレンダーの部品）で、②③④の作り直しが防げるか。
3. 日給の数え方（主文書 §4 F-01・F-02）で、報酬見込みに穴がないか。

## 回答形式

最初に「この順番で進めてよい／条件付きで進めてよい／重大な再検討が必要」の判断と理由を書く。その後、次の表で指摘する。

| 指摘ID | 重要度（高/中/低） | 文書の節・根拠ファイル | 問題と発生条件 | 推奨修正 | ユーザーの決定が必要か |
|---|---|---|---|---|---|

- 確定した不整合、未決だが管理されている事項、任意の改善案を区別すること。
- 既に未決・残る論点と書かれている事項を、見落としとして指摘しないこと。ただし決定前に実装・公開できない事項は明示すること。
- 反対案は、効果・運用の負担・既存への影響を比べて示すこと。
- 最後に「実装前に必須の決定」「追加すべき受入試験」「未確認の事実」を列挙すること。
- コードを読めない場合は、実装と照合したとは書かないこと。

保存先の案：`docs/ops/LINE_WORKER_ROADMAP_REVIEW_<AI名>_2026-10-22.md`（読み取り専用の依頼なら、保存せず回答として返す）。
