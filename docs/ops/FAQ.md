# FAQ（運用・Kintone連携）

## Q1. App174で請求書を開くと「指定したアプリが見つかりません」と出る
A. 請求/支払アプリIDの差し替えが発生している可能性があります。現在は `invoices=171`, `payouts=173` を優先参照し、存在しない場合はフォールバックする実装です。必要に応じて `front_dashboard.js` の `CONFIG.apps` を確認してください。

## Q2. 固定事務局費はどこで入力する？
A. App174のクライアント向け発行ダイアログで手入力します。入力値は対象請求書レコードの固定事務局費フィールドへ反映されます。

## Q3. 紹介者向け支払明細の対象者が出ない
A. 稼働者の `via_destination` が `紹介` になっているか確認してください。`VANZAI直接` や `下請け` は対象外です。

## Q4. `group` フィールドはまだ使う？
A. 運用上は `via_destination` に移行済みです。`group` 依存ロジックは廃止し、互換対応は履歴扱いです。

## Q5. ラベルを日本語化したいが、フィールドコードは変えたくない
A. `scripts/update_kintone_field_labels_to_japanese.py` を使用してください。コードは維持し、ラベルのみ変更します。

## Q6. App171でラジオボタンが多すぎる問題は解消済み？
A. 直接型変換不可のため、実運用に必要な正規フィールドを追加して運用可能化済みです。旧ラジオ系は互換・履歴用途として残しています。

## Q7. 締め後に金額が変わってしまうのを防ぐには？
A. 単価スナップショットと締め境界を守ってください。締め後の再計算や直接更新は行わず、必要時はガードレール付きの締め解除手順を使います。

## Q8. まずどのドキュメントを見ればよい？
A. 仕様は [docs/spec/DESIGN_SPEC_v0.3.md](../spec/DESIGN_SPEC_v0.3.md)、実装履歴は [docs/IMPLEMENTATION_LOG.md](../IMPLEMENTATION_LOG.md)、画面運用は [docs/kintone/FRONT_DASHBOARD_SETUP.md](../kintone/FRONT_DASHBOARD_SETUP.md) を参照してください。

## Q9. 「worker_idフィールドのフィールドタイプには演算子=を使用できません」が再発する
A. 原因は、フィールド型に合わない演算子でKintoneクエリを組み立てていることです。`DROP_DOWN` / `RADIO_BUTTON` を含む選択系フィールドは `in` が必要で、`=` は使えません。運用時は以下を必ず確認してください。
- クエリ条件を手書きせず、`buildKintoneFieldCondition(fieldCode, fieldType, value)` を経由している
- `workerFieldType` / `periodType` / `workerType` をフォームメタデータから取得して渡している
- 画面更新後は `Ctrl + F5` でハードリロードして再実行している
- 詳細は [docs/kintone/FRONT_DASHBOARD_SETUP.md](../kintone/FRONT_DASHBOARD_SETUP.md) の「再発防止（重要）: Kintoneクエリの演算子とフィールド型」を参照

## 更新履歴
- 2026-02-16: 初版作成（ドキュメント残タスク対応）
- 2026-02-17: Q9追加（worker_id演算子エラー再発防止）
