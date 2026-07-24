# FAQ（運用）

## Q1. 請求書を生成できない / PDF が表示されない
A. 管理画面の請求一覧で対象月・案件を確認してください。生成済みで PDF がない場合は「発行」を実行し、`storage/pdfs` に保存されたか API ログを確認します。詳細は [RUNBOOK_MONTHLY.md](../../RUNBOOK_MONTHLY.md) を参照。

## Q2. 固定事務局費はどこで入力する？
A. admin-web の請求生成フォームで手入力します。入力値は請求レコードの `fixed_office_fee_amount` に保存されます。

## Q3. 紹介者向け支払明細の対象者が出ない
A. 稼働者の `via_destination` が `紹介` になっているか確認してください。`VANZAI直接` や `下請け` は対象外です。

## Q4. `group` フィールドはまだ使う？
A. 運用上は `via_destination` に移行済みです。`group` 依存ロジックは廃止し、互換対応は履歴扱いです。

## Q5. 締め後に金額が変わってしまうのを防ぐには？
A. 単価スナップショットと締め境界を守ってください。締め後の再計算や直接更新は行わず、必要時はガードレール付きの締め解除手順を使います。

## Q6. まずどのドキュメントを見ればよい？
A. 仕様は [docs/spec/DESIGN_SPEC_v0.3.md](../spec/DESIGN_SPEC_v0.3.md)、実装状況は [docs/ops/STATUS.md](./STATUS.md)、画面運用は [docs/ops/USER_MANUAL.md](./USER_MANUAL.md) を参照してください。

## Q7. 支払明細メールの送信先を変更したい
A. 支払一覧の送信履歴パネルで宛先を上書きして送信できます。既定送信先は payee に紐づくメールアドレスです。未設定の支払は一覧の「既定送信先未設定」フィルタで洗い出せます。

## Q8. Kintone はまだ使う？
A. **いいえ。** 本番運用は VPS（admin-web + staff-mobile + API）のみです。Kintone 関連スクリプトは `scripts/legacy/kintone/` にアーカイブされています。

## 更新履歴
- 2026-07-24: Kintone 連携 FAQ を廃止し、admin-web 運用前提に全面更新
- 2026-02-16: 初版作成（ドキュメント残タスク対応）
- 2026-02-17: Q9追加（worker_id演算子エラー再発防止）— 2026-07-24 に Kintone 廃止に伴い削除
