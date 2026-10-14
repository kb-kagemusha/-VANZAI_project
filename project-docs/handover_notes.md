# handover_notes.md

## 1. このプロジェクトで重要な考え方
- 金額と時間は「後で説明できること」が最優先
- 破壊的更新を避け、無効化・版管理・監査で履歴を残す
- 画面層は段階移行できるよう、API/DBの正本性を守る
- 運用上の失敗を前提に、再送・再実行・差戻しを業務として設計する

## 2. 実装時に注意すべきこと
- actual の status と assignment の status は別概念として扱う
- closing 後の変更は通常更新でなく訂正フローで扱う
- CSV取り込みは重複防止と洗い替えスコープを明示する
- 請求/支払は明細行を正本にし、合計は再計算可能に保つ

## 3. よくある失敗
- 1. 画面側の権限制御だけで満足し、API権限チェックを抜く
- 2. month/period_key 変換を画面ごとに実装し、月末バグを作る
- 3. 発行済みデータを直接更新して整合性を壊す
- 4. 送信結果を履歴化せず、再送判断ができなくなる
- 5. 監査ログに理由や差分を残さない

## 4. 変更時の注意点
- DBスキーマ変更は必ずAlembicで管理
- 監査対象操作に新機能を追加した場合は audit_log 出力点を追加
- APIレスポンス契約を変える場合、admin-web と staff-mobile の両方を確認
- period_key の意味を壊す変更（別フォーマット等）は禁止

## 5. 削除禁止箇所（実質）
- actuals の計算・単価スナップショット列
- invoices / payouts の version・親子関係
- closings の release関連列
- payout_deliveries と audit_logs
- 権限マッピング（ROLE_PERMISSIONS）

## 6. DB変更時の注意
- SQLite/PG差分を考慮する
- unique制約・FK追加のmigration戦略を環境別に確認
- 既存データを消すDDLではなく、互換移行を優先
- migration失敗時の復旧手順（stamp等）をrunbookへ残す

## 7. 将来の改善候補
- OpenAPIからAPI一覧を自動生成する仕組み
- period_key集計に対する集約ビュー整備
- 通知/送信失敗の再処理ジョブ標準化
- registration系の責務整理（運用実態に合わせた簡素化）
- ObjectStorage のR2切替運用を本番標準化

## 8. 技術的負債
- ドキュメントに旧情報と最新情報が併存している
- API経路の履歴差分（audit/closing周辺）に揺れがある
- 簡易API(main_simple.py)と本実装(main.py)の二重管理
- 一部機能でKintone依存が残り、完全独立境界が曖昧

## 9. AI Agent向け実装指針
- 仕様/決定ログを正本として先に確認する
- 推測で埋めず、未確定は「要確認」にする
- 変更提案は「整合性維持」と「運用再現性」の観点で優先順位を付ける
- PR単位は業務テーマで分割し、監査ログとテスト追加点を説明する

## 10. 初日オンボーディング手順（推奨）
1. docs/spec と docs/decisions を読み、用語定義を合わせる
2. src/models と alembic を読んで制約を把握する
3. src/services の csv_import / closing / invoice_service / payout_service / audit を確認
4. apps/admin-web と apps/staff-mobile の route guard と API client を確認
5. 監査ログ一覧画面で主要操作の証跡を辿る

## 11. コード照合で確認した実装ギャップ（2026-06-10）

詳細一覧: `project-docs/CODE_VERIFIED_GAPS.md`

### 最優先（P0）
1. **締め後も CSV 取込・請求/支払生成が可能** — `csv_import`, `invoice_service`, `payout_service` に closing 参照なし
2. **請求数量が total 時間ベース** — `calc_minutes_billable` との不一致（aggregation/recalc は billable 優先）
3. **`reissue_invoice` が明細行をコピーしない** — 版管理の穴
4. **`/api/aggregation/*` が無認証** — セキュリティリスク

### 締めガードの現状
| 操作 | Hard Close 時 |
|------|--------------|
| 再計算 | ❌ 拒否（`recalculation.py`） |
| CSV 取込 | ✅ 可能（要制限） |
| 請求/支払生成 | ✅ 可能（要制限） |

### 仕様正本
- `docs/spec/DESIGN_SPEC_v0.3.md` を復元たたき台として再配置（2026-06-10）
- 欠落期間の判断は `DECISION_LOG.md` を優先

## 12. 要確認
- 本番運用で必須とする通知チャネル（メール/Push/外部連携）の優先順位
- Kintone停止時の最終移行判定基準
- 締めガード統合の実装方針（Soft のみ制限 vs Hard も制限）
