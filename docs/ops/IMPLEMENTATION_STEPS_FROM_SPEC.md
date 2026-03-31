# 設計書（DESIGN_SPEC v0.3）から読み取れる「実装までのステップ」

正本: `docs/spec/DESIGN_SPEC_v0.3.md`

この文書は、設計書 v0.3 に**明記されている内容のみ**を根拠に「実装の順序」をチェックリスト化したものです。
コマンド手順（.env 作成、alembic、起動方法など）は設計書のスコープ外のため、別紙 `DEPLOYMENT_GUIDE.md` を参照してください。

---

## 0. 実装前に確定しておくこと（正本の確認）

- 目的・優先順位を確認する（設計書 1章）
- 用語定義（planned/confirmed、Soft/Hard Close、snapshot）を実装内の命名・状態遷移に反映する（4章）
- 「壊したら事故になる不変条件」を制約/実装/テストの形で担保する（6.3）
- 未決事項を一覧化し、仕様変更は `docs/decisions/DECISION_LOG.md` に理由付きで記録する（設計書 27章、AGENTS.md）

---

## 1. データモデル（最小セット）を確定し、制約を先に入れる

設計書の「主要エンティティ」「追加フィールド」「不変条件」を元に、まずDBスキーマを確定します（6.1〜6.3）。

- マスタ（設計書 6.1）
  - worker / client / site / project_type / role
  - price_sales / price_outsource / price_rule
  - incentive_rule / equipment
- トランザクション（設計書 6.1）
  - project / shift_slot / assignment / actual
  - import_batch / expense / incentive
  - invoice / invoice_line / payout / payout_line
  - payout_delivery / bank_transfer_batch
  - equipment_loan / project_document / task
  - audit_log

### 必須の状態・スナップショット字段を実装
- assignment（6.2）: status(tentative/confirmed/canceled), cancel_reason, manager_id, locked_price_sales/outsource
- actual（6.2）: status(active/invalid/superseded), invalid_reason, applied_price_sales/outsource, calc_*（時間計算の結果一式）, import_batch_id, external_row_key
- invoice（6.2, 11章）: status(preparing/issued/closed), version, parent_invoice_id, pdf_object_key
- invoice_line（6.2, 11章）: is_correction, unit_price_snapshot, minutes_or_hours_snapshot
- import_batch（6.2, 9章）: submitted_by, submit_channel, file_name, period_key, mode, scope_key, result_counts, errors_json

### 不変条件（6.3）を制約＋実装＋テストで担保
- 集計対象の actual は status=active のみ
- assignment が canceled のまま actual=active を残さない（例外不可）
- 発行済み（invoice issued / payout approved/paid）は Hard Close 相当で unlock しない
- 請求/支払で使った単価と時間計算結果はスナップショットとして保持

---

## 2. 単価適用とスナップショット（再現性の中核）

設計書 7章の「優先順位」「適用タイミング」「再計算ガードレール」を実装します。

- 単価適用優先順位（7.2）
  - 売上単価: locked_price_sales → project固定 → price_rule → price_salesデフォルト
  - 外注単価: locked_price_outsource → worker×role個別 → price_rule → price_outsourceデフォルト
- 適用タイミング（7.3）
  - actual.status=active へ確定するタイミングで単価決定し、actual.applied_price_* に保存
  - 以後、同一actualの金額は actual.applied_price_* を正本として扱う
- 再計算ガード（7.4）
  - 対象期間/案件/actual集合を明示選択
  - 影響件数・金額差（増減）を事前表示し、実行ログを残す
  - invoice issued / payout approved/paid に紐づく actual は再計算除外

---

## 3. 時間計算（丸め・休憩・深夜）を正本化する

設計書 8章に従い、時間計算結果を actual.calc_* として保存し、以後の正本にします（8.2, 8.3）。

- Projectの時間計算設定（8.1）
  - rounding_unit_minutes, rounding_method, break_deduction_rule, time_calc_mode, night_window, night_calc_mode
- system_first の計算手順（8.2）
  - minutes_total → minutes_break（auto/manual/none）→ billable → rounding → night_minutes（必要なら保存）→ actual.calc_* に保存
  - CSVの hours がある場合は比較用として保持し、差が閾値超なら「要確認フラグ」
- csv_hours_first（8.3）
  - hours を正本として minutes_billable を採用（hours*60）

---

## 4. CSV取り込み（Upsert再設計）を実装する

設計書 9章の要件に沿って、取り込みが「やり直し可能」「二重払い防止」になるように作ります。

- 提出チャネル（9.2）
  - 原則: システムのCSV提出（Site Manager）
  - 例外: Ops が import_batch.submit_channel を指定して取り込み
- CSV列の最小要件（9.3）
  - 必須: project_id, work_date, worker_id, role_id, start_time または hours, end_time（start_timeがある場合）
  - 任意: break_minutes, hours, notes
  - 推奨: shift_label
- import_batch.mode（9.4）
  - append（原則使わない）
  - upsert_by_external_key（external_row_keyがある場合）
  - replace_scope（推奨デフォルト）: 旧データは削除せず actual.status=superseded で残す
- replace_scope のスコープ（9.5）
  - project_month（推奨）/ project_day / project_day_worker
- 二重化防止の必須挙動（9.6）
  - scope内の既存 actual(active) を一括 superseded 化
  - 新規取り込み分を active で INSERT
  - 取り込み後に差分サマリ（件数、総時間、総額）を表示
  - 行数/総時間が大きく減っている等の事故パターンは UI 警告＋要確認フラグ

---

## 5. アサイン取消・差替えのガード（ゾンビ実績対策）

設計書 10章に従って、取消が「集計に残り続ける事故」にならないよう制御します。

- 取消時の制御（10.2）
  - assignment.status=canceled への変更は、紐づく actual がある場合はブロック
  - 例外: Adminのみ
    - A: 取消＋actual invalid 化（invalid_reason必須）
    - B: 取消＋actual relink（将来拡張、v0.3ではUIなし）
- 集計条件（10.2）
  - actual.status=active のみ集計
  - assignment.status=canceled は集計対象外（ただし実績は actual.status が正本）
- 差替えフロー（10.3）
  - Soft Close 前: invalid 化＋replace_scope で取り込みし直す
  - Hard Close 後: 訂正（correction）で差分調整

---

## 6. 請求書・支払の版管理（上書き禁止）を実装

設計書 11章の原則に従い、発行後に上書きせず「訂正/再発行」で整合を取ります。

- invoice/payout は発行後に上書きしない（11.1）
- PDF は version ごとに保存し、参照キーを保持（11.1）
- 訂正と再発行の使い分け（11.2）
  - 訂正（推奨）／再発行（例外・承認＋理由）
- 税の計算方式は未決（11.3）

---

## 7. 締め（Soft/Hard）と解除（ガードレール）を実装

設計書 12章に従い、締め後に計算結果が変わらない状態を作ります。

- Soft Close（12.1）: 取込完了、差分確認、請求/支払生成完了、発行前凍結。解除はAdmin可（制約あり）
- Hard Close（12.1）: invoice issued または payout approved/paid が存在。原則解除不可。
- Soft Close解除の制約（12.2）
  - 期限（7営業日以内）、回数上限（2回）、承認（2回目は二者）、再締め期限（3営業日以内）、超過時エスカレーション
- Hard Close後の修正（12.3）
  - unlock しない。訂正/再発行で対応し、根拠と差分を audit_log に残す

---

## 8. ダッシュボード（次の一手）とアラートを実装

設計書 13章の「未処理一覧の列」を満たす形で、未処理が次のアクションに落ちるUI/集計を作ります。

- 未確定シフト / 実績未提出 / 取込残件 / 差分アラート / 締め解除履歴（13.1）

---

## 9. 運用カレンダー・催促・救済フローを実装

- 営業日基準の期限起算（14.1）
- 催促手段（通知＋メール）（14.2）
- CSV遅延救済（15章）
  - 月末+3営業日で provisional 扱い
  - 遅延分提出後は replace_scope、発行済みなら訂正/再発行

---

## 10. 監査ログ（最低要件）を実装

設計書 16章の「必須ログ」を、必ず残る形（イベントごと）で実装します。

- 単価ルール変更、実績取り込み、replace_scope、Soft/Hard Close、解除、訂正/再発行、経費承認、インセンティブ付与、送信、振込バッチ、備品貸出/返却

---

## 11. 追加機能（v0.3）を順次実装

設計書 v0.3 に追加された機能は、上記の基盤（スナップショット、取込、版管理、締め、監査）が揃った後に積み上げます。

- 経費精算（17章）: expense を invoice_line/payout_line に line_type=expense で反映
- インセンティブ管理（18章）: incentive を invoice_line/payout_line に line_type=incentive で反映
- 支払明細送信（19章）: payout_delivery を作り一括送信・再送を可能にする
- 銀行振込フォーマット（20章）: paid の payout を抽出してファイル化し、状態遷移を記録
- 貸出備品（21章）: equipment / equipment_loan と返却遅延アラート
- 案件説明資料（22章）: project_document と公開範囲
- タスク進捗（23章）: task / task_template、期限通知
- 現場管理者の可視化（24章）: shift_slot.site_manager_id 等の表示
- 売上/粗利の可視化（25章）: planned/confirmed の指標定義どおりに集計
- 実績フォーム漏れアラート（26章）: assignment確定×過去日×actual未提出を検知

---

## 12. 未決事項（実装前に決める/暫定を置く）

設計書 27章より。

- キャンセル料の暫定ルール
- 税計算方式（行ごと/合計）
- 深夜割増の保存方針（night_calc_mode 確定）
- 「アサインなし実績」の扱い
- shift_label を必須列にするか
