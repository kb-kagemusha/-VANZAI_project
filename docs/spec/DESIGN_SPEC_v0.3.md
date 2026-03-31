# DESIGN_SPEC — 案件・シフト・実績・請求・支払の一元管理（属人化防止）v0.3

## 1. 目的
本プロジェクトは、スプレッドシート運用で発生している属人化と事務コストを解消し、誰でも簡単に案件管理から経理処理までを実行できる状態を作ることを目的とする

優先順位
1 各案件の単価管理
2 請求書および内訳の自動作成（経費実費精算、インセンティブ含む）
3 稼働者への支払明細の自動作成（経費実費精算、インセンティブ含む）
4 支払明細の各稼働者への送信
5 銀行専用フォーマット出力による一括振込

最終イメージ
- ダッシュボード1発で「案件状況」「売上」「外注費」「粗利」「進捗」「未処理」を俯瞰できる
- 確定シフト数×単価＝売上が即見える状況
- 外注費（種類ごと）とインセンティブが一覧で見える
- 実績CSV取り込み後に、請求書と支払明細が自動生成される
- 支払明細は稼働者ごとにメール送信可能
- 銀行専用フォーマット（全銀フォーマット等）を出力し一括振込対応
- 仕様とデータの正本が一本化され、版ズレと押し付け合いが起きない

## 2. 背景と課題
現状
- スプレッドシートで案件ごとに分割管理
- 案件数増加によりシートが増殖し視認性が低下
- 計算や転記の手作業が多く人的ソースを消耗
- 運用知識が担当者の頭に閉じて属人化

主要課題
- 正本がない
- 計算ルールが散在し再現性がない
- 実績取り込みから請求・支払までが手作業で連鎖する
- 誰が誰を管理しているか可視化できない（現場管理者の担当範囲が不明確）
- 外注費が稼働者によって異なり、シフトとの連動が手作業
- 貸出備品の管理が属人化している

## 3. スコープ
### 3.1 対象範囲
- 案件管理（案件情報、期間、場所、管理者、ステータス）
- シフト管理（枠の作成、必要人数、役割、確定状況、現場管理者のマーク付け）
- アサイン管理（誰がどの枠に入るか、誰が誰を管理しているか見える化）
- タスク進捗（案件種別テンプレから自動生成、タスクアラート通知）
- 単価管理（売上単価、外注単価、単価ルール、例外）
- 経費精算（経費実費を請求書・支払明細に盛り込み）
- インセンティブ管理（案件ごとに有無を設定、請求書・支払明細に反映）
- 実績管理（CSV取り込み、突合、確定値更新、実績フォーム漏れアラート）
- 請求書および内訳の生成（案件×期間、経費・インセンティブ含む）
- 支払明細の生成（稼働者×期間、経費・インセンティブ含む）
- 支払明細の送信（各稼働者へメール送信）
- 銀行振込フォーマット出力（全銀フォーマット等で一括振込対応）
- ダッシュボード（予定/確定、未処理一覧、売上/粗利、外注費、インセンティブ）
- 案件説明資料の管理（案件ごとの資料を見える化）
- 貸出備品管理（備品種類、貸出状況、返却状況）
- 運用カレンダー、催促、差戻し、救済フロー

### 3.2 対象外（v0.3）
- 会計ソフトへの自動仕訳連携（エクスポートは検討可）
- 勤怠打刻の収集（外部システムがある場合はCSV/APIで受ける）

## 4. 用語定義
- 予定（Planned）: 確定アサインを基に算出した見込み値
- 確定（Confirmed）: 実績取り込み後の確定値
- 締め（Close）: 請求/支払を固定する状態
- 内部締め（Soft Close）: 発行前の最終凍結、原則ここまで解除可能
- 発行後締め（Hard Close）: 発行済みを含む確定、原則解除不可、訂正で対応
- 訂正（Correction）: 差分を別レコードで残して整合を取る処理
- スナップショット（Snapshot）: 計算に使った単価や時間計算結果を値として保存し再現性を担保すること

## 5. ロールと権限
### 5.1 ロール
- Admin: マスタ編集、単価ルール変更、締め、内部締め解除
- Ops: 案件/シフト/アサイン作成、実績取り込み、請求/支払の生成
- Accounting: 請求発行、支払承認、締め（Hard Close）承認
- Site Manager: 担当案件の参照、CSV提出、提出後のエラー修正再提出、担当範囲の進捗確認
- Worker: 参照のみ（必要なら）

### 5.2 Site Managerの操作範囲（具体）
許可
- 担当案件のシフト枠一覧の閲覧
- 担当案件のアサイン一覧の閲覧
- 実績CSVのアップロード（提出）
- 取り込み結果（成功/エラー/差戻し）閲覧
- エラー差戻しに対する修正CSVの再提出
- タスク（担当分）の進捗更新（完了チェック）

不許可
- 単価マスタや単価ルールの編集
- 請求/支払の生成、発行、締め
- アサインの確定/取消（運用上必要なら「変更依頼」だけ許可）

## 6. データモデル（要点）
### 6.1 主要エンティティ
マスタ
- worker
- client
- site
- project_type
- role
- price_sales
- price_outsource
- price_rule
- incentive_rule（インセンティブルール）
- equipment（備品種別）

トランザクション
- project
- shift_slot
- assignment
- actual
- import_batch
- expense（経費精算）
- incentive（インセンティブ支給）
- equipment_loan（貸出備品記録）
- project_document（案件説明資料）
- task（タスク進捗）
- invoice / invoice_line
- payout / payout_line
- payout_delivery（支払明細送信記録）
- bank_transfer_batch（銀行振込バッチ）
- audit_log

### 6.2 追加フィールド（v0.3で確定）
assignment
- status（tentative/confirmed/canceled）
- cancel_reason
- manager_id（必要ならshift_slot側で上書き）
- locked_price_sales（任意）
- locked_price_outsource（任意）

actual
- status（active/invalid/superseded）
- invalid_reason
- applied_price_sales（必須）
- applied_price_outsource（必須）
- calc_minutes_total（必須）
- calc_minutes_billable（必須）
- calc_minutes_break（必須）
- calc_minutes_night（任意）
- calc_rounding_unit（保存）
- calc_rounding_method（保存）
- calc_break_rule（保存）
- calc_tax_mode（保存する場合はinvoice_line側でも可）
- import_batch_id（必須）
- external_row_key（任意、取り込み側で生成）

invoice
- status（preparing/issued/closed）
- version
- parent_invoice_id（訂正や再発行の親）
- pdf_object_key（保存先参照）

invoice_line
- is_correction
- unit_price_snapshot
- minutes_or_hours_snapshot
- tax_amount（方針により保持）

import_batch
- submitted_by（Site Manager等）
- submit_channel（system_upload/email等）
- file_name
- period_key（YYYYMMなど）
- mode（append/upsert/replace_scope）
- scope_key（置換対象の範囲キー）
- result_counts（success/error/skip）
- errors_json

### 6.3 不変条件（壊したら事故になる）
- actual は必ず status を持ち、集計対象は status=active のみ
- assignment が canceled のまま actual=active を残さない（例外は不可）
- 発行済み（invoice issued または payout approved/paid）の期間は Hard Close とみなし、原則 unlock しない
- 計算再現性のため、請求/支払に使った単価と時間計算結果は必ずスナップショットとして保持する

## 7. 単価設計（時間軸とスナップショット）
### 7.1 単価の種類
- 売上単価（請求用）
- 外注単価（支払用）

### 7.2 単価適用の優先順位（例）
売上単価
1 assignment に個別上書き（locked_price_sales）がある
2 project に案件固定単価がある
3 price_rule に一致する単価がある
4 price_sales のデフォルト単価

外注単価
1 assignment に個別上書き（locked_price_outsource）がある
2 worker×role の個別単価がある
3 price_rule に一致する単価がある
4 price_outsource のデフォルト単価

### 7.3 適用タイミング（時間軸の定義）
- 実績確定（actual.status=active へ確定）時に単価を決定し、actual.applied_price_* に保存する
- 以後、同じactualの金額は actual.applied_price_* を正本として扱う
- マスタ単価変更は「次回の実績確定」から影響する
- 再計算は Soft Close まで許可するが、対象範囲を必ず指定する

### 7.4 再計算のガードレール
- 再計算は「対象期間」「対象案件」「対象のactual集合」を明示選択させる
- 影響件数と金額差（増減）を事前に表示し、実行ログを残す
- 既に invoice issued または payout approved/paid に紐づく actual は再計算対象から除外する

## 8. 時間計算（丸め・休憩・深夜）
### 8.1 Projectの時間計算設定（v0.3で確定）
project
- rounding_unit_minutes（例 1/15/30）
- rounding_method（floor/ceil/nearest）
- break_deduction_rule（auto/manual/none）
- time_calc_mode（system_first/csv_hours_first）
- night_window（例 22:00-05:00）
- night_calc_mode（store_minutes/dynamic）

推奨デフォルト（暫定）
- rounding_unit_minutes=15
- rounding_method=ceil
- break_deduction_rule=auto
- time_calc_mode=system_first
- night_calc_mode=store_minutes

### 8.2 計算手順（system_firstの場合）
入力
- start_time, end_time, break_minutes（任意）, hours（任意）

手順
1 minutes_total = end-start
2 minutes_break
   - break_deduction_rule=auto の場合
     - break_minutes があるなら採用
     - break_minutes が空なら 0 とし、警告（warn）を出す
   - manual の場合
     - break_minutes が空ならエラー（取り込み拒否）
   - none の場合
     - break_minutes を 0 扱い
3 minutes_billable = max(minutes_total - minutes_break, 0)
4 rounding を適用
   - rounding_unit_minutes と rounding_method に従い minutes_billable を丸め
5 night_minutes（night_calc_mode=store_minutes の場合）
   - start/end を夜間帯で交差計算し minutes_night を算出し actual.calc_minutes_night に保存
6 計算結果を actual.calc_* に保存し、以後の正本とする
7 hours が提供されている場合
   - system_first では hours は比較用として保持し、差が閾値超なら要確認フラグ

### 8.3 計算手順（csv_hours_firstの場合）
- minutes_billable は hours を正本として採用（hours*60）
- start/end は参照用、矛盾が大きい場合は要確認フラグ

## 9. CSV取り込み仕様（Upsertの再設計）
### 9.1 目的
- 現場の修正（遅刻、早退、入力ミス）で二重登録や二重払いが発生しないこと
- 取り込みのやり直しが運用として成立すること

### 9.2 提出チャネル（Opus指摘への対応）
- 原則: システムの「CSV提出」画面からアップロード（Site Manager権限）
- 例外: メール等の場合は Ops が import_batch.submit_channel を指定して取り込み

### 9.3 CSV列（最小）
必須
- project_id
- work_date
- worker_id
- role_id
- start_time または hours
- end_time（start_timeがある場合）

任意
- break_minutes
- hours
- notes

推奨（導入できるなら）
- shift_label（例 早番/日勤/夜勤/1枠目/2枠目）

### 9.4 import_batch.mode（v0.3で確定）
mode は取り込みUIで明示選択し、import_batch に保存する

- append
  - 常に新規追加
  - 原則使わない（検証用途）

- upsert_by_external_key
  - CSVに external_row_key がある場合のみ使用
  - external_row_key で上書き

- replace_scope（推奨デフォルト）
  - 指定した範囲を「洗い替え」する
  - 旧データは削除しないで actual.status=superseded として残す
  - superseded は集計対象から除外

### 9.5 replace_scope のスコープ定義（v0.3で確定）
scope_key の候補を用意し、運用に合わせて選ぶ

- scope=project_month（推奨）
  - 対象: project_id + period_key（YYYYMM）
  - その案件・その月の実績を丸ごと置換する
  - 遅刻修正などの再提出でも二重化しない

- scope=project_day（軽量）
  - 対象: project_id + work_date
  - その案件・その日の実績を置換する

- scope=project_day_worker（安全寄り）
  - 対象: project_id + work_date + worker_id
  - その案件・その日・その稼働者の実績を置換する

推奨運用
- Site Manager提出は project_month を基本とし、月次で1ファイルを正本にする
- 修正が出たら同じ project_month を再提出し、replace_scope で洗い替えする

### 9.6 二重化防止の必須挙動
replace_scope 実行時
- 置換対象 scope 内の既存 actual（status=active）を一括で status=superseded に更新する
- 新規取り込み分を status=active で INSERT する
- 取り込み後に差分サマリ（件数、総時間、総額）を表示する

注意
- 「部分ファイル」で project_month を洗い替える事故を防ぐため、UIで警告を出す
  - 例 前回提出より行数が大きく減っている、総時間が大きく減っている
  - 要確認フラグを立て、Ops/Accountingの承認が必要にする

## 10. アサイン取消と差替え（ゾンビ実績対策）
### 10.1 原則
- actual が存在する assignment の取消は、勝手に実績が集計され続ける事故の温床になる
- 取消時の actual の扱いを必ず定義する

### 10.2 取消時の制御（v0.3で確定）
- assignment.status を canceled に変更する操作は、紐づく actual が存在する場合はブロックする
- 例外として Admin のみ、以下のいずれかを選んで実行できる
  A 取消＋actual invalid 化
    - 紐づく actual.status を invalid に更新
    - invalid_reason を必須
  B 取消＋actual relink（将来拡張）
    - 紐づく actual を別 assignment に付け替える
    - v0.3では UI は用意せず、運用上は「訂正」で対応

集計条件（必須）
- actual.status=active のみ集計
- assignment.status=canceled は集計対象外（ただし実績は actual.status が正本）

### 10.3 差替えフロー（v0.3暫定）
- 原則: 旧assignmentを canceled にし、新assignmentを作成する
- 旧assignmentに actual がある場合
  - Soft Close 前: actual を invalid 化して取り込みし直す（replace_scope を使う）
  - Hard Close 後: 訂正（correction）で差分調整する

## 11. 請求書・支払の版管理（訂正と再発行）
### 11.1 基本
- invoice / payout は発行後に上書きしない
- PDF は version ごとに保存し、参照（pdf_object_key）を保持する

### 11.2 訂正と再発行の使い分け（v0.3暫定）
- 訂正（推奨）
  - 金額差分が小さい
  - クライアント側の運用が差分請求を許容する
  - 監査性を優先したい

- 再発行（例外）
  - クライアントが差分請求を受け付けない
  - 明細構造自体が誤っている
  - Accounting承認＋理由必須

運用ルール
- 再発行は invoice.version を +1 し、parent_invoice_id で親子関係を持つ
- 旧版PDFは残す

### 11.3 税の計算タイミング（未決→v0.3で論点化）
- 行ごと計算（invoice_line tax_amount 保持）
- 合計計算（invoice header 側で保持）
どちらを採るかはインボイス要件で決める

## 12. 締め（Soft Close / Hard Close）と解除
### 12.1 状態定義
- Soft Close
  - 実績取り込み完了、差分確認完了、請求/支払の生成完了
  - 発行前の最終凍結
  - Admin による解除を許可（制約あり）

- Hard Close
  - invoice issued または payout approved/paid が存在する状態
  - 原則解除不可
  - 修正は訂正または再発行で対応

### 12.2 Soft Close解除の制約（乱用防止の骨子）
- 解除可能期間: Soft Close から 7営業日以内
- 解除回数上限: 同一期間につき 2回まで
- 承認
  - 1回目: Admin 単独可（理由20文字以上）
  - 2回目: Admin + Accounting の二者承認
- 再締め期限: 解除から 3営業日以内
- 期限超過時: 自動アラート → Admin → 管理責任者へエスカレーション

### 12.3 Hard Close後の修正
- unlock はしない
- 訂正または再発行で整合を取る
- 訂正の根拠と差分計算を audit_log に残す

## 13. ダッシュボード（次の一手を固定）
### 13.1 未処理一覧（必須列）
未確定シフト
- 案件名
- 現場管理者
- 未確定枠数
- 最も近い稼働日
- 締切までの日数（営業日）
- 次アクション（催促/確定依頼）

実績未提出
- 案件名
- 現場管理者
- 対象期間
- 提出締切
- 状態（提出待ち/エラー差戻し/期限超過）
- 次アクション（催促/差戻し/救済）

取込残件
- import_batch_id
- ファイル名
- 成功/エラー/スキップ
- エラー詳細リンク
- 差戻し状態
- 修正期限

差分アラート
- 案件名
- 稼働者
- 日付
- 予定時間
- 確定時間
- 差分（時間）
- 差分（金額）
- 確認状態（未確認/確認済/問題なし）
- 担当（Ops/Accounting）

締め解除履歴
- 対象期間
- 解除者
- 解除日時
- 解除理由
- 解除回数（累計）
- 再締め期限
- 再締め日時

## 14. 運用カレンダーと催促（手段を確定）
### 14.1 締切の起算（v0.3暫定）
- 期限は原則「営業日」基準
- 営業日カレンダーはシステム側で保持（祝日対応は別途）

### 14.2 催促手段（v0.3暫定）
- デフォルト: システム通知 + メール
- 代替: Slack等（導入済みなら）

### 14.3 催促テンプレ（付録参照）
- シフト未確定
- CSV未提出
- CSVエラー差戻し
- 再締め期限超過

## 15. CSV遅延の救済フロー（Opus指摘への対応）
### 15.1 目的
- 一部現場の遅延で全体の請求/支払が止まるのを防ぐ

### 15.2 救済案（v0.3暫定）
- 月末+3営業日までにCSV未提出が残る場合
  - 当該案件は「暫定状態（provisional）」として扱う
  - 請求/支払は他案件を先行して進める
- 遅延CSVが提出されたら
  - replace_scope（project_month）で取り込み
  - 既に発行済みなら訂正または再発行で対応
  - 発行前なら生成をやり直す

## 16. 監査ログ（最低要件）
必須ログ
- 単価ルール変更（前/後、理由）
- 実績取り込み（import_batch、件数、差分サマリ）
- replace_scope 実行（scope、superseded件数）
- Soft Close / Hard Close
- Soft Close解除（理由、回数、再締め期限、二者承認の有無）
- 訂正/再発行（理由、差分）
- 経費精算の承認/却下（理由）
- インセンティブ付与（対象者、金額、理由）
- 支払明細送信（送信先、送信日時、結果）
- 銀行振込バッチ生成（件数、総額）
- 備品貸出/返却（備品ID、稼働者、日付）

## 17. 経費精算（v0.3追加）
### 17.1 目的
- 案件に紐づく経費実費（交通費、材料費等）を請求書・支払明細に反映する

### 17.2 expenseエンティティ
- expense_id（一意識別子）
- project_id（案件）
- worker_id（申請者、任意）
- expense_date（発生日）
- category（交通費/材料費/その他）
- amount（金額）
- description（内容）
- receipt_file_key（領収書ファイル参照）
- status（pending/approved/rejected）
- approved_by（承認者）
- approved_at（承認日時）
- target_invoice（請求書に計上する場合）
- target_payout（支払明細に計上する場合）

### 17.3 計上ルール
- 請求書への計上: expense.target_invoice が設定されたものを invoice_line に追加
- 支払明細への計上: expense.target_payout が設定されたものを payout_line に追加
- 経費は単価とは別枠で明細に表示する（line_type=expense）

## 18. インセンティブ管理（v0.3追加）
### 18.1 目的
- 案件ごとにインセンティブの有無を設定し、条件を満たした場合に請求書・支払明細へ反映する

### 18.2 incentive_ruleエンティティ（マスタ）
- rule_id（一意識別子）
- name（ルール名: 皆勤手当、紹介手当等）
- project_id（案件、NULLなら全案件共通）
- condition_type（皆勤/紹介/売上達成等）
- condition_json（条件詳細をJSONで保持）
- incentive_amount（支給額）
- is_for_invoice（請求書に計上するか）
- is_for_payout（支払明細に計上するか）
- valid_from / valid_until
- is_active

### 18.3 incentiveエンティティ（トランザクション）
- incentive_id（一意識別子）
- incentive_rule_id（適用ルール）
- worker_id（対象稼働者）
- project_id（対象案件）
- period_key（対象期間 YYYYMM）
- amount（支給額）
- reason（支給理由）
- status（pending/approved/paid）
- approved_by / approved_at
- target_invoice_id（請求書明細に紐付け）
- target_payout_id（支払明細に紐付け）

### 18.4 反映ルール
- インセンティブは invoice_line / payout_line に line_type=incentive として追加
- 案件にインセンティブ有無を project.has_incentive で管理

## 19. 支払明細送信（v0.3追加）
### 19.1 目的
- 生成した支払明細を各稼働者にメール送信する

### 19.2 payout_deliveryエンティティ
- delivery_id（一意識別子）
- payout_id（対象支払明細）
- worker_id（送信先稼働者）
- delivery_method（email/system_notification）
- recipient_email（送信先メールアドレス）
- sent_at（送信日時）
- status（pending/sent/failed/bounced）
- error_message（エラー時の詳細）

### 19.3 送信フロー
1. 支払明細が confirmed になったら送信対象リストを生成
2. Ops/Accounting が送信対象を確認し「一括送信」を実行
3. 各稼働者にPDF添付またはリンク付きメールを送信
4. 送信結果を payout_delivery に記録
5. 失敗分は再送信可能

## 20. 銀行振込フォーマット出力（v0.3追加）
### 20.1 目的
- 支払明細から銀行専用フォーマット（全銀フォーマット等）を出力し、一括振込に対応する

### 20.2 bank_transfer_batchエンティティ
- batch_id（一意識別子）
- period_key（対象期間 YYYYMM）
- format_type（zengin_fb/zengin_csv等）
- total_count（振込件数）
- total_amount（振込総額）
- file_name（出力ファイル名）
- file_object_key（保存先参照）
- status（preparing/exported/uploaded/completed）
- created_by / created_at
- uploaded_at（銀行アップロード日時）
- completed_at（振込完了確認日時）

### 20.3 workerエンティティへの追加フィールド
- bank_code（金融機関コード）
- branch_code（支店コード）
- account_type（普通/当座）
- account_number（口座番号）
- account_holder_kana（口座名義カナ）

### 20.4 出力フロー
1. 対象期間の payout が paid ステータスになったものを抽出
2. 銀行フォーマット選択（全銀FB、全銀CSV等）
3. ファイル生成＆ダウンロード
4. 銀行システムへアップロード（手動）
5. アップロード完了を記録
6. 振込完了確認を記録

## 21. 貸出備品管理（v0.3追加）
### 21.1 目的
- 稼働者への備品貸出状況を管理し、返却漏れを防ぐ

### 21.2 equipmentエンティティ（マスタ）
- equipment_id（一意識別子）
- name（備品名: ユニフォーム、無線機、ヘルメット等）
- category（分類）
- description（説明）
- total_stock（総在庫数）
- available_stock（貸出可能数）

### 21.3 equipment_loanエンティティ（トランザクション）
- loan_id（一意識別子）
- equipment_id（備品）
- worker_id（貸出先稼働者）
- project_id（関連案件、任意）
- loan_date（貸出日）
- expected_return_date（返却予定日）
- actual_return_date（実返却日）
- quantity（貸出数）
- status（loaned/returned/overdue/lost）
- notes（備考）

### 21.4 アラート
- 返却予定日を過ぎた備品は「返却遅延アラート」を表示
- ダッシュボードに「未返却備品一覧」を追加

## 22. 案件説明資料管理（v0.3追加）
### 22.1 目的
- 案件ごとの説明資料（マニュアル、注意事項等）を一元管理し、関係者が参照できるようにする

### 22.2 project_documentエンティティ
- document_id（一意識別子）
- project_id（案件）
- title（資料タイトル）
- document_type（manual/notice/map/other）
- file_object_key（ファイル保存先参照）
- uploaded_by / uploaded_at
- is_public（稼働者に公開するか）
- notes（備考）

### 22.3 表示
- 案件詳細画面に「説明資料」タブを追加
- Site Manager/Worker は公開資料のみ参照可能
- Ops/Admin は全資料を管理可能

## 23. タスク進捗とアラート（v0.3追加）
### 23.1 目的
- 案件ごとに「いつまでに何をすればいいか」を見える化し、期限前にアラート通知する

### 23.2 taskエンティティ
- task_id（一意識別子）
- project_id（案件）
- task_template_id（テンプレートから生成した場合）
- title（タスク名）
- description（詳細）
- assignee_id（担当者、任意）
- due_date（期限日）
- status（not_started/in_progress/completed/overdue）
- priority（high/medium/low）
- completed_at
- completed_by
- notes

### 23.3 task_templateエンティティ（マスタ）
- template_id（一意識別子）
- project_type_id（案件種別）
- title（タスク名）
- description（詳細）
- relative_due_days（案件開始日からの相対日数）
- priority
- is_active

### 23.4 アラート通知
- 期限3営業日前: 「期限間近」通知
- 期限1営業日前: 「明日期限」通知
- 期限超過: 「期限超過」アラート（ダッシュボードに赤表示）

### 23.5 ダッシュボード表示
- 未完了タスク一覧（期限順）
- 期限超過タスク（警告表示）
- タスク完了率（案件ごと）

## 24. 現場管理者の可視化（v0.3追加）
### 24.1 目的
- 「誰が誰を管理しているか」を見える化し、シフト管理の責任範囲を明確にする

### 24.2 shift_slotへの追加フィールド
- site_manager_id（現場管理者のworker_id）

### 24.3 projectへの追加フィールド
- primary_manager_id（主担当現場管理者）
- secondary_manager_id（副担当現場管理者）

### 24.4 表示
- シフト一覧に「現場管理者」列を追加
- ダッシュボードに「管理者別シフト一覧」ビューを追加
- 管理者ごとの担当案件・担当稼働者を一覧表示

## 25. 売上・粗利・外注費の可視化（v0.3追加）
### 25.1 目的
- 確定シフト数×単価=売上を即見える状況にする
- 外注費とインセンティブを一覧で見える化する

### 25.2 ダッシュボード指標
予定（Planned）
- 確定アサイン数 × 売上単価 = 予定売上
- 確定アサイン数 × 外注単価 = 予定外注費
- 予定売上 - 予定外注費 = 予定粗利

確定（Confirmed）
- 実績時間 × 売上単価 = 確定売上
- 実績時間 × 外注単価 = 確定外注費
- インセンティブ合計
- 経費合計
- 確定売上 - 確定外注費 - インセンティブ - 経費 = 確定粗利

### 25.3 表示切り替え
- 案件別/期間別/管理者別で集計表示を切り替え可能
- リアルタイム更新（実績取り込み後に自動反映）

## 26. 実績フォーム漏れアラート（v0.3追加）
### 26.1 目的
- 稼働予定があるのに実績が未提出の場合にアラートを出す

### 26.2 検知ロジック
- 対象: assignment.status=confirmed かつ work_date が過去
- 条件: 紐づく actual が存在しない、または actual.status!=active
- 期限: 稼働日の翌営業日までに実績がなければアラート

### 26.3 アラート通知
- Site Manager: 担当案件の未提出一覧をメール通知
- Ops: 全案件の未提出一覧をダッシュボードに表示
- 通知タイミング: 稼働日翌日の午前中

## 27. 未決事項（次の意思決定対象）
- キャンセル料の暫定ルール（前日/当日/無断など）
- 税計算方式（行ごと/合計）
- 深夜割増の保存方針（night_calc_mode を確定）
- 「アサインなし実績」の扱い（エラーにするか自動アサインするか）
- shift_label を必須列にするか（現場CSVの運用負荷とトレードオフ）

## 付録A 催促テンプレ（暫定）
### A-1 シフト未確定 催促
件名例
- 【要対応】未確定シフトあり {project_name} 期限{due_date}

本文例（要素）
- 対象案件
- 未確定枠数
- 最も近い稼働日
- 期限（営業日）
- 対応方法（確定 or 変更依頼）
- 返信先（Ops）

### A-2 CSV未提出 催促
件名例
- 【要提出】実績CSV 未提出 {project_name} 対象{period}

本文要素
- 提出先（CSV提出画面）
- 命名規則
- 期限
- 遅延時の扱い（暫定処理と訂正の可能性）

### A-3 CSVエラー差戻し
件名例
- 【修正依頼】実績CSV エラー {project_name} 行{n} 期限{due_date}

本文要素
- import_batch_id
- エラー行と理由
- 修正期限（1営業日）
- 再提出手順

### A-4 再締め期限超過
件名例
- 【至急】締め解除の再締め期限超過 {period}

本文要素
- 解除日時
- 再締め期限
- 影響（請求/支払の確定遅延）
