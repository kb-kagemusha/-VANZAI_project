# DECISION_LOG

## 使い方
- 仕様の変更、未決事項の確定、例外の扱い、ガードレールの強化など
  「後から説明が必要になる判断」はすべてここに残す
- 1件=1エントリ
- 影響範囲（どのテーブル/画面/運用が変わるか）を書く

---

## Template
- Date: YYYY-MM-DD
- Decision: 
- Context:
- Options:
  - A:
  - B:
  - C:
- Chosen:
- Why:
- Impact:
  - Data model:
  - UI/UX:
  - Ops/Runbook:
  - Migration:
- Follow-ups:

---

## Entries

### DEC-001: import_batch 重複検知キーの定義
- Date: 2026-01-26
- Status: Proposal
- Decision: import_batch の重複検知キーを `(file_hash, project_id, period_key)` とする
- Context:
  - 同一ファイルの二重取り込みを防止する必要がある（仕様9.4）
  - ファイル名だけでは偶然の重複を検知できない
  - 同一内容でも異なるproject/periodなら別取込として許可すべき
- Options:
  - A: `(file_name, submitted_at)` — 時刻依存で脆弱
  - B: `(file_hash)` のみ — 異なる案件への同一ファイル使用を排除してしまう
  - C: `(file_hash, project_id, period_key)` — 案件×期間で一意化
- Chosen: C
- Why: 案件・期間単位の洗い替え運用（replace_scope=project_month）と整合し、誤操作防止と運用柔軟性を両立
- Impact:
  - Data model: import_batch に file_hash, project_id, period_key を追加、Unique制約
  - UI/UX: 重複検知時に警告表示
  - Ops/Runbook: 同一ファイル再提出時の警告対応手順
  - Migration: 初期マイグレーションで対応
- Follow-ups: なし
- Spec Reference: 9.4, 9.5

---

### DEC-002: period_key 形式の確定
- Date: 2026-01-26
- Status: Proposal
- Decision: period_key は `YYYYMM` 形式の文字列6桁とする
- Context:
  - replace_scope=project_month で使用する期間キー（仕様9.5）
  - 月次運用が基本のため月単位で十分
- Options:
  - A: `YYYYMM` (文字列6桁) — シンプル、ソート可能
  - B: `YYYY-MM` (文字列7桁) — 可読性向上
  - C: DATE型（月初日） — 型安全だが過剰
- Chosen: A
- Why: 最もシンプルで、インデックス効率・比較・パーティション切り分けが容易
- Impact:
  - Data model: actual.period_key, import_batch.period_key を CHAR(6) で定義
  - UI/UX: 入力時はYYYY/MMでも受付、内部変換
  - Ops/Runbook: CSV命名規則と整合確認
  - Migration: 初期マイグレーションで対応
- Follow-ups: なし
- Spec Reference: 9.5

---

### DEC-003: アサインなし実績（assignment_id = NULL）の扱い
- Date: 2026-01-26
- Status: Proposal
- Decision: v0.3（Sprint1）では assignment_id = NULL の実績はエラー扱いとし、取り込みを拒否する
- Context:
  - 仕様17章で「アサインなし実績」の扱いが未決
  - 自動アサイン作成は複雑度が高く、事故リスクがある
- Options:
  - A: エラー扱い（取り込み拒否） — 安全だが運用負荷
  - B: 自動アサイン作成 — 便利だがゾンビ発生リスク
  - C: 警告付きで取り込み、後で手動アサイン紐付け — 中間案
- Chosen: A
- Why: MVPでは安全優先。自動アサインはv1.0以降で検討
- Impact:
  - Data model: actual.assignment_id は NOT NULL 制約を付けない（将来拡張のため）が、アプリ層でバリデーション
  - UI/UX: エラー行として明示、修正CSV再提出を促す
  - Ops/Runbook: 「アサインなし実績」エラー時の対応手順を追記
  - Migration: なし
- Follow-ups: v1.0で再検討
- Spec Reference: 17章

---

### DEC-004: クライアント追加要件の反映（2026-01-27）
- Date: 2026-01-27
- Status: Confirmed
- Decision: クライアントからの追加・確認要件を設計書（DESIGN_SPEC_v0.3.md）およびKintoneアプリリストに反映する
- Context:
  - クライアントより以下の要件が追加・確認された
  - これらをv0.3スコープに含めるため設計書を更新
- 追加要件一覧:
  1. 経費実費精算を請求書と支払明細へ盛り込む
  2. インセンティブを盛り込む（ある案件/ない案件有）
  3. 支払い明細を各稼働者にメール送信
  4. 銀行専用フォーマット出力（全銀フォーマット等）で一括振込対応
  5. シフト管理：各現場管理者のマーク付け、誰が誰を管理してるのか見える化
  6. タスク進捗管理：タスクアラート通知機能
  7. 案件の説明資料の見える化
  8. 外注費用管理見える化：インセンティブも含めて一覧表示
  9. 売上/粗利見える化：確定シフト数×単価=売上が即見える
  10. 実績フォーム漏れアラート
  11. 貸出備品管理
- Impact:
  - Data model: 以下のエンティティを追加
    - expense（経費精算）
    - incentive_rule / incentive（インセンティブ）
    - payout_delivery（支払明細送信記録）
    - bank_transfer_batch（銀行振込バッチ）
    - equipment / equipment_loan（備品管理）
    - project_document（案件説明資料）
    - task / task_template（タスク進捗）
    - worker に銀行口座情報、is_site_manager を追加
    - project に primary_manager_id, secondary_manager_id, has_incentive を追加
    - shift_slot に site_manager_id を追加
  - UI/UX: ダッシュボードに売上/粗利/外注費/インセンティブ表示を追加
  - Ops/Runbook: 支払明細送信、銀行振込出力、備品管理、タスクアラートの運用手順を追加
  - Migration: 追加エンティティのマイグレーション作成が必要
- Follow-ups:
  - 銀行フォーマット詳細（全銀FB/CSV仕様）の確認
  - 備品種類の具体的な一覧（クライアントから要ヒアリング）
  - インセンティブ条件の具体例（皆勤、紹介等）の詳細確認
- Spec Reference: DESIGN_SPEC_v0.3.md セクション 17-27（新規追加）

---

### DEC-005: アサイン選択セットの共有範囲
- Date: 2026-03-31
- Status: Confirmed
- Decision: アサイン一覧の保存済み選択セットはサーバー保存を正本とし、個人セットは ASSIGNMENT_READ 権限者、共有セットは ASSIGNMENT_WRITE 権限者のみ作成可能とする
- Context:
  - 一括状態更新で月次の対象集合を再利用したい
  - ローカル保存のみでは端末依存になり、引き継ぎや複数端末運用に弱い
  - site_manager / accounting まで無制限に共有作成を許可すると、運用セットが増え過ぎる懸念がある
- Options:
  - A: すべてローカル保存のままにする
  - B: 全 ASSIGNMENT_READ 権限者が共有セットを作成できる
  - C: 個人セットは広く許可し、共有セットは ASSIGNMENT_WRITE 権限者に限定する
- Chosen: C
- Why: 端末依存を解消しつつ、共有セットの増殖は運用担当に寄せて抑制できるため
- Impact:
  - Data model: assignment_selection_sets を追加し、period_key / created_by_user_id / is_shared / assignment_ids を保持
  - UI/UX: アサイン一覧から保存済み選択セットの読み込み・削除ができ、共有チェックは admin / ops のみ有効
  - Ops/Runbook: 月次確定候補の引き継ぎをブラウザローカルではなく API 保存に統一
  - Migration: assignment_selection_sets テーブル追加が必要
- Follow-ups:
  - 共有セットの名称ルールと棚卸し手順を運用メモへ追記
  - 将来は project 単位の命名規約やアーカイブ基準を検討

---

### DEC-005: 税計算方式の確定
- Date: 2026-01-28
- Status: Confirmed
- Decision: 税計算は「合計計算（請求書ヘッダ側）」を採用
- Context:
  - 仕様11.3の未決事項
  - 行ごと計算は端数処理が複雑化する
- Options:
  - A: 行ごと計算（invoice_line.tax_amount保持）
  - B: 合計計算（invoice.headerで保持）
- Chosen: B
- Why: 端数処理の一貫性と運用負荷の低減
- Impact:
  - Data model: invoice.tax_amount を正本とする
  - UI/UX: 明細行に税額は表示しない（必要なら表示用に算出）
  - Ops/Runbook: 税率変更時はヘッダ計算のみ更新
  - Migration: なし
- Follow-ups: 税率の既定値と変更履歴の記録方法を決める
- Spec Reference: 11.3

---

### DEC-006: 深夜割増の保存方針
- Date: 2026-01-28
- Status: Confirmed
- Decision: night_calc_mode は store_minutes（calc_minutes_night を保存）を採用
- Context:
  - 仕様8.1/17の未決事項
  - 締め後の再現性を担保する必要がある
- Options:
  - A: store_minutes（保存）
  - B: dynamic（都度計算）
- Chosen: A
- Why: 再現性と監査性が高い
- Impact:
  - Data model: actual.calc_minutes_night を必須化（NULL禁止は後続で検討）
  - UI/UX: 実績詳細に夜間分を表示
  - Ops/Runbook: 夜間帯設定変更は次回以降適用
  - Migration: なし
- Follow-ups: 既存データの埋め方（再計算で埋めるか）を決める
- Spec Reference: 8.1, 8.2, 17

---

### DEC-007: shift_label の必須性
- Date: 2026-01-28
- Status: Confirmed
- Decision: shift_label は任意（必須化しない）
- Context:
  - 仕様9.3/17の未決事項
  - 現場運用負荷とのトレードオフ
- Options:
  - A: 必須
  - B: 任意
- Chosen: B
- Why: 既存運用の入力負荷を優先
- Impact:
  - Data model: NULL許容
  - UI/UX: 入力補助（推奨）として扱う
  - Ops/Runbook: 未入力時の差分検知ロジックは project_day_worker を推奨
  - Migration: なし
- Follow-ups: 将来の必須化判断は運用実績を見て再検討
- Spec Reference: 9.3, 17

---

### DEC-008: キャンセル料ルールの確定
- Date: 2026-01-28
- Status: Confirmed
- Decision: キャンセル料は 3日前10%、前日20%、当日50% を採用（明日から適用）
- Context:
  - 仕様17章の未決事項
  - 詳細ルールは確認中
- Options:
  - A: 3日前10%、前日20%、当日50%
  - B: 前日30%、当日50%
  - C: 当日のみ50%
- Chosen: A
- Why: 段階的な抑止効果と運用説明のしやすさ
- Impact:
  - Data model: price_rule / incentive_rule で条件表現
  - UI/UX: キャンセル理由と判定結果を表示
  - Ops/Runbook: ルール確定後に置換・再計算が必要
  - Migration: なし
- Follow-ups: 適用開始日以降の運用告知をRUNBOOKに反映
- Spec Reference: 17

---

### DEC-009: drv案件の「人工」「日額単価」「下請け支払」表現
- Date: 2026-01-28
- Status: Confirmed (2026-01-30)
- Decision: drv案件で必要な稼働実績ビュー（紹介者/管理報酬/支払サイトを含む）を再現可能に生成するための前提定義を確定する
- Context:
  - 外注（紹介者）単価は日額（例: 16,000円/日、例外 16,500円/日）が基本
  - 現場管理報酬は「配下の人工×1,000円」、統括報酬は「売上8%」といった別建て報酬がある
  - 現行実装は「単価×時間（hours）」前提の箇所があり、日額単価の扱いを決めないと金額が破綻する
  - 支払先が「稼働者」だけでなく「下請け（紹介者）」になり得る
  - Wヘッダー（同一日2案件）は組合せが複数あり、バンドル額は固定ではない
  - 下請け稼働者の支払は「粗利30%以上」を基本とし、売上日額→支払日額の段階テーブル（固定が基本）で運用されるが、現場難易度等で裁量調整が入りうる
  - 概ね「売上日額×0.70→1,000円単位へ丸め」がイメージに近い（丸め方式は未確定）
  - Wヘッダーのバンドル額は毎年変動し得るため、実運用としては都度入力（例外として月次で調整）を想定
- Options:
  - A: 1人工 = (worker_id, work_date) のユニーク数（同日複数シフトでも1）
  - B: 1人工 = actual行数（同日複数シフトなら複数）
  - C: 1人工 = shift_slot を正本にして1枠=1人工

  - D: 日額単価を時給換算して actual.applied_price_* は時給で保存（標準1日=何分かを決める）
  - E: payout_line の unit_type=days, quantity=人工 を採用し、支払生成を日単位対応

  - F: 下請け（紹介者）を workers として扱い introducer_worker_id で紐付け（最小追加）
  - G: 下請け（紹介者）マスタ（suppliers）を追加し introducer_supplier_id で紐付け（正攻法）
- Chosen:
  - **1人工**: (worker_id, work_date, project_id) のユニーク数（Wヘッダー対応）
  - **日額単価**: payout_line の unit_type=days, quantity=人工 を採用（E）
  - **下請けマスタ**: suppliers テーブルを追加（G）
  - **Wヘッダーのバンドル価格**: 都度手入力（例外として月次で調整）
  - **統括8%**: 税抜売上（invoice.amount_before_tax）を対象
  - **現場管理報酬**: 配下人工×1,000円（固定）
- Why:
  - 1人工: Wヘッダー時は案件ごとに人工が立つのが実態に即している
  - 日額単価: unit_type で日単位/時間単位を明示的に区別できる
  - 下請けマスタ: 稼働者と紹介者は役割が異なるため、別テーブルで管理する方が整合性が高い
  - バンドル価格: 組合せが多く、年ごとに変動するため、自動判定ではなく都度手入力が現実的
  - 統括8%: 税抜売上を対象にするのが会計上妥当
  - 現場管理報酬: 配下人工×1,000円で固定（将来的な移行は incentive_rules で対応）
- Impact:
  - Data model:
    - suppliers テーブル追加（supplier_id, name, contact_email, payout_terms_days, is_active, notes）
    - workers.introducer_supplier_id 追加
    - payout_line.unit_type 追加（"hours" | "days"）
  - UI/UX:
    - バンドル価格の手入力UI（請求書発行前に調整）
    - 紹介者マスタの登録UI
  - Ops/Runbook: drv案件の運用ルールをRUNBOOKへ反映
  - Migration:
    - suppliers テーブル追加マイグレーション
    - workers.introducer_worker_id → workers.introducer_supplier_id データ移行
- Follow-ups:
  - suppliers マスタ実装（src/models/master.py）: 完了
  - マイグレーション作成（alembic/versions/xxx_add_suppliers.py）: 完了
  - データ移行スクリプト作成（scripts/migrate_introducers_to_suppliers.py）: 完了
  - Kintoneアプリ追加（紹介者マスタ）: 外部作業
  - 支払生成ロジック更新（supplier_id ベースに変更）: 完了
  - バンドル価格の手入力運用フローを確立: 決定待ち（運用）
- Spec Reference: DESIGN_SPEC_v0.3 6.3, 7.3, DRV_PAYOUT_RULES.md

---

### DEC-010: Vリスト（紹介者/請求支払）の暫定取り込み方針
- Date: 2026-02-02
- Status: Proposal
- Decision: 紹介者/下請けは suppliers へ暫定反映し、請求/支払対応表は参照ドキュメントとして保管する
- Context:
  - V：紹介者などリスト.csv に supplier_id や連絡先が存在しない
  - V：請求、支払いリスト.csv は既存Kintone単価マスタのスキーマと一致しない
- Options:
  - A: suppliers には名称のみを登録し、単価は未設定
  - B: 専用アプリ（price_matrix）を新規作成してから取り込む
  - C: suppliers に日額単価を暫定反映し、請求/支払表は参照ドキュメントとして保管
- Chosen:
  - C
- Why:
  - まず紹介者/下請けの登録を進められ、運用側の入力負荷を下げられる
  - 請求/支払表はスキーマ未整備のため、誤った形での強制取り込みを避ける
- Impact:
  - Data model: 変更なし
  - UI/UX: suppliers はCSVで追加可能、請求/支払は参照表
  - Ops/Runbook: 参照表の扱い（運用判断）を明記
  - Migration: なし
- Follow-ups:
  - 請求/支払対応表をKintoneに反映するアプリ/フィールド設計の決定
  - 該当稼働者の実データ（worker_id）確定後に introducer_supplier_id を紐付け

---

### DEC-015: 請求書・支払明細 PDF の暫定保存先
- Date: 2026-03-31
- Status: Confirmed
- Decision: 請求書と支払明細の PDF は、Cloudflare R2 切替までの暫定運用として storage/pdfs 配下へ保存し、DB には相対 object key を保持する
- Context:
  - React 管理画面から PDF 保存先キーを参照できる状態を先に揃えたい
  - 既存コードには object key を保持する項目が一部あるが、保存処理は統一されていない
  - R2 連携を待つ間も、版付き PDF の再取得先を安定させる必要がある
- Options:
  - A: R2 実装まで都度生成のみで運用する
  - B: 絶対ファイルパスを DB に保存する
  - C: ローカル storage/pdfs に保存し、DB には相対 object key を保持する
- Chosen: C
- Why: 将来の R2 切替時に DB の参照形式を変えずに済み、管理画面上も保存先キーを先に可視化できるため
- Impact:
  - Data model: payouts.pdf_object_key を追加し、invoice/payout の両方で相対 object key を保持
  - UI/UX: 請求一覧・支払一覧で保存済み PDF の storage key を表示
  - Ops/Runbook: ローカル開発では storage/pdfs を生成物置き場として扱い、Git 管理から除外
  - Migration: payouts に pdf_object_key 追加が必要
- Follow-ups:
  - Cloudflare R2 / バックアップ先への切替実装
  - 再発行・訂正版の保管ポリシーと cleanup ルール整理

---

### DEC-016: 支払明細送信の記録単位
- Date: 2026-03-31
- Status: Confirmed
- Decision: 支払明細メール送信は payout 単位で送信試行ごとの履歴を payout_deliveries に追記し、支払一覧には最新1件のみを反映する
- Context:
  - 稼働者や下請けへの支払明細送付は再送が発生しうる
  - 送信可否の監査と運用確認は必要だが、一覧画面に全履歴を直接展開すると月次運用の視認性が落ちる
  - 既存の監査ログだけでは送信先メールアドレスや添付PDFキーの参照に手数がかかる
- Options:
  - A: 監査ログのみで送信履歴を管理する
  - B: payout に送信状態を上書き保存して最後の結果だけ持つ
  - C: payout_deliveries に試行履歴を保存し、一覧では最新1件だけを表示する
- Chosen: C
- Why: 再送履歴を失わずに運用一覧の可読性も維持でき、将来の専用履歴 UI や配信分析へ拡張しやすいため
- Impact:
  - Data model: payout_deliveries を追加し、recipient_email、status、provider、pdf_object_key_snapshot、sent_at を保持
  - UI/UX: 支払一覧は最新送信結果のみ表示し、再送操作は一覧から実行する
  - Ops/Runbook: 送信失敗時も履歴と監査ログを確認しながら再送判断できる
  - Migration: payout_deliveries テーブル追加が必要
- Follow-ups:
  - 宛先上書き送信時の運用ルールを RUNBOOK に明記

---

### DEC-011: site_manager の担当案件紐付け正本
- Date: 2026-03-31
- Status: Proposal
- Decision: Phase 1 時点の site_manager の担当案件判定は `project.primary_manager_id` と `project.secondary_manager_id` を正本にする
- Context:
  - React 管理画面 Phase 1 では site_manager に担当案件のみを見せる設計を採る
  - 既存コードでは `ShiftSlot.site_manager_id` を参照しているが、実モデルと不整合がある
  - Sprint 1 の一覧 API と権限制御に先立ち、どのモデルを担当案件の正本とするか決める必要がある
- Options:
  - A: `project.primary_manager_id` と `project.secondary_manager_id` を正本にする
  - B: `shift_slot.site_manager_id` を追加してシフト単位で管理する
  - C: 中間テーブルを追加して user と project を多対多管理する
- Chosen: A
- Why:
  - 既存の Project モデルに近く、Sprint 1 の修正範囲を最小化できる
  - 案件単位の閲覧制御と相性がよく、一覧 API の絞り込み実装が単純になる
  - 運用要件が将来拡張された場合のみ C を検討すればよい
- Impact:
  - Data model: 既存 Project の manager 系カラムを正本として扱う
  - UI/UX: site_manager は担当案件に紐づく Dashboard / Actuals / Assignments / Projects / Shift Slots のみ閲覧可能
  - Ops/Runbook: 案件担当者の設定漏れ時に閲覧漏れが起こるため、案件登録運用へ確認手順を追加
  - Migration: 既存コードの参照先修正が主。新規テーブル追加は不要
- Follow-ups:
  - `src/services/auth.py` の参照修正
  - 担当案件の設定手順を運用文書へ追記
  - 中間テーブルが必要な運用要件の有無を確認

---

### DEC-012: 管理画面の認証・セッション方式
- Date: 2026-03-31
- Status: Proposal
- Decision: Phase 1 の管理画面は Bearer token 方式を採用し、トークン期限切れ時は再ログインへ戻す
- Context:
  - React 管理画面の認証方式とトークン期限切れ時の挙動を先に決めないと、フロントと API の実装がぶれる
  - Phase 1 は参照系中心であり、複雑なセッション維持より実装単純性とトラブル時の明確さを優先したい
- Options:
  - A: Bearer token + 期限切れ時は再ログイン
  - B: Bearer token + silent refresh
  - C: Cookie セッション + CSRF 対策
- Chosen: A
- Why:
  - Sprint 1 の実装とデバッグが最も単純で、画面遷移や 401 処理を明確にできる
  - Cookie セッションより構成が軽く、同一オリジンの Nginx リバースプロキシとも整合しやすい
  - silent refresh は将来導入余地を残しつつ、Phase 1 では必須にしない方が手戻りが少ない
- Impact:
  - Data model: 変更なし
  - UI/UX: セッション切れ時は /login へ戻す。Phase 1 ではサイレント復帰しない
  - Ops/Runbook: 再ログイン手順とトークン期限切れ時の想定挙動を明記
  - Migration: なし
- Follow-ups:
  - トークン有効期限の既定値確認
  - 将来 silent refresh を導入するか Phase 2 以降で再評価

---

### DEC-013: Phase 1 一覧 API の共通制約
- Date: 2026-03-31
- Status: Proposal
- Decision: Phase 1 の一覧 API は共通エラーレスポンス、sort_by 許可リスト、limit 上限、search 対象明記を必須とする
- Context:
  - 一覧 API を複数本追加するため、初期の共通ルール不足がそのまま UI の分岐増加と API のばらつきにつながる
  - 外部レビューでも、エラーレスポンス、sort_by、limit、search の不足が主要指摘となった
- Options:
  - A: 最低限のページングのみ定義し、詳細は API ごとに任せる
  - B: Phase 1 時点で共通制約を固定する
- Chosen: B
- Why:
  - Sprint 1 から Sprint 3 の API 実装が増えるため、初手で揃えた方が後からの修正コストが低い
  - フロント側の DataTable とエラーハンドリングを共通化しやすい
- Impact:
  - Data model: 変更なし
  - UI/UX: エラー表示と一覧操作の挙動が画面間で統一される
  - Ops/Runbook: 画面ごとの例外的な挙動が減り、運用説明が容易になる
  - Migration: なし
- Follow-ups:
  - 標準エラーレスポンスを `error_code`, `message`, `detail` で統一
  - `limit` のデフォルト値と上限値を決める
  - API ごとの `sort_by` 許可カラム一覧を定義する
  - API ごとの `search` 対象カラムを定義する

---

### DEC-014: Phase 1 の受入比較ルール
- Date: 2026-03-31
- Status: Proposal
- Decision: Phase 1 の参照一致確認は原則完全一致とし、Sprint ごとに件数比較、代表データ比較、権限確認を実施する
- Context:
  - 受入基準に「主要件数一致」はあるが、判定方法が曖昧なままだと Sprint 3 まで問題が先送りされる
  - 外部レビューでも、Sprint 単位の受入手順と数値化が必要と指摘された
- Options:
  - A: Phase 1 終了時にまとめて比較する
  - B: Sprint ごとに比較し、件数は原則完全一致とする
- Chosen: B
- Why:
  - 問題の検出を前倒しでき、Sprint 1 の不整合を Sprint 3 まで持ち越さずに済む
  - 管理画面の信頼性を段階的に高められる
- Impact:
  - Data model: 変更なし
  - UI/UX: 一覧画面の表示項目が比較しやすい粒度で固定される
  - Ops/Runbook: Sprint ごとの比較チェックリストを整備する必要がある
  - Migration: なし
- Follow-ups:
  - Sprint 1, 2, 3 ごとの比較対象画面を確定
  - 完全一致が前提で困る例外ケースの有無を確認
  - 性能目標値と対応ブラウザを別途確定

---

### DEC-017: 2026-04-07 追加要件のデータモデル確定
- Date: 2026-04-07
- Status: Confirmed
- Decision: 追加要件のデータモデル方針として、Supplier 区分を追加し、Worker の銀行口座管理を Phase 1 で履歴モデルとして導入し、Project に `vanzai_manager_id` を追加して VANZAI 職員を参照する
- Context:
  - Kintone で先行運用している追加機能を Web 側へ移行するにあたり、Supplier 区分、Worker 振込情報、Project と VANZAI 職員の関係が未確定だった
  - notes への埋め込みや暫定流用のまま進めると、公開登録フォーム、支払処理、権限制御、管理画面表示で手戻りが大きい
- Options:
  - A: Supplier 区分を持たず notes で吸収し、Worker 銀行口座情報は後回し、Project 管理者も既存 workers 参照のままにする
  - B: Supplier 区分をカラム追加し、Worker 銀行口座管理を Phase 1 で追加し、Project に `vanzai_manager_id` を持たせる
  - C: VANZAI 職員を workers に統合して、Project 管理者も workers のみで扱う
- Chosen: B
- Why:
  - Supplier の「紹介者 / 下請け」と「個人 / 法人」は登録フォーム分岐、支払明細、集計の正本情報になるため、notes では不十分
  - Worker の銀行口座管理は既存の支払処理と今回の公開登録フォームの両方で必須であり、後回しにすると移行順が破綻する
  - VANZAI 職員は workers と別概念であり、Project 側から独立 FK で参照した方が責務分離と将来の権限制御が明確になる
- Impact:
  - Data model:
    - `suppliers.supplier_type` を追加
    - `suppliers.entity_type` を追加
    - Worker の銀行口座管理モデルを Phase 1 で追加
    - `projects.vanzai_manager_id` を追加して `vanzai_staff.id` を参照
  - UI/UX:
    - 公開登録フォームで契約経路に応じた分岐が可能になる
    - 管理画面で Supplier 区分、Worker 振込情報、案件担当 VANZAI 職員を明示表示できる
  - Ops/Runbook:
    - 採用フロー、支払前確認、案件担当確認の運用を新構成に合わせて更新する必要がある
  - Migration:
    - `suppliers`, `workers`, `projects` の追加マイグレーションが必要
- Follow-ups:
  - Worker の振込情報のマスキング表示ルールを確定する
  - `vanzai_manager_id` と既存 `primary_manager_id` / `secondary_manager_id` の役割分担を API / UI で明文化する
  - Supplier 区分ごとのフォーム分岐と帳票分岐を受入条件に落とし込む
  - `supplier_type` を supplier 自体の属性で固定できるか、案件関係属性へ切り出す必要があるかを Phase 0 で検証する
  - supplier への継続支払がある場合の口座管理モデルを Phase 0 で確定する
  - payout の recipient 移行戦略と受取人スナップショットの保持方法を Phase 0 で確定する

---

### DEC-018: Phase 0 初期回答の確定（2026-04-07）
- Date: 2026-04-07
- Status: Confirmed
- Decision: Phase 0 のうち supplier role、dedupe キー、承認競合時の挙動、旧 request の扱い、DB 制約の強度について初期回答を確定する
- Context:
  - 追加要件計画の Phase 0 を進めるため、最初に運用前提を確定する必要があった
  - 特に supplier role の所属先、重複候補判定、申請承認の二重実行時挙動、DB 制約の強度は migration 前に固める必要がある
- Options:
  - A: これらを未決事項のまま Phase 0 に残す
  - B: 現時点の実運用前提で一次確定し、残差は Phase 0 の残タスクとして扱う
- Chosen: B
- Why:
  - supplier role と dedupe 方針を早めに固定しないと request / master 設計が進まない
  - approve の競合挙動を決めないと承認トランザクション設計が止まる
  - DB 制約の強度を先に決めた方が migration 設計がぶれない
- Impact:
  - Data model:
    - `supplier_type` は Phase 1 では supplier 自体の単一属性として扱う
    - worker dedupe 候補キーは `電話番号`, `氏名 + ふりがな`
    - supplier dedupe 候補キーは `法人名 / 屋号`, `電話番号`
    - superseded / rejected request は再承認不可とする
  - UI/UX:
    - 同一 request を別管理者が先に承認済みなら「別の管理者が承認済み」と表示する
    - 重複候補は差分確認 UI へ送る
  - Ops/Runbook:
    - 管理者は worker / supplier 重複候補を指定キーで確認する
    - 旧 request の再利用運用は行わない
  - Migration:
    - DB 制約は厳しめに入れる前提で設計する
- Follow-ups:
  - supplier role を将来関係モデルへ拡張する条件を文書化する
  - `source_type` / `sales_reports` / payout recipient / auth 紐付けの追加確定事項は DEC-019 を参照する

---

### DEC-019: Phase 0 設計凍結 追加確定（2026-04-07）
- Date: 2026-04-07
- Status: Confirmed
- Decision: `vanzai_staff` と `users` の紐付け方針、payout recipient 抽象化、`source_type`、`sales_reports` の現行正本判定を確定する
- Context:
  - 既存実装は `users.worker_id` と `payouts.worker_id` / `supplier_id` を前提にしている
  - 追加要件では VANZAI 職員ログイン、支払先の汎化、公開受付の起点区分、販売報告の immutable 訂正運用を設計段階で固める必要があった
- Options:
  - A: Phase 1 実装時まで保留し、その場で migration を決める
  - B: 既存モデル方針に寄せて今ここで確定する
- Chosen: B
- Why:
  - auth 主体の参照方向を users 側へ統一した方が既存 `users.worker_id` と整合する
  - payout recipient の正本を先に決めないと API / 帳票 / migration がすべてぶれる
  - `source_type` と sales report の現行判定を先に固定しないと承認フローと集計条件が不安定になる
- Impact:
  - Data model:
    - `users.vanzai_staff_id` を追加し、`vanzai_staff` 側には auth FK を持たない
    - payout は `recipient_type` / `recipient_id` を正本とし、既存 `worker_id` / `supplier_id` から backfill する
    - `registration_requests.source_type` は `public_form`, `admin_proxy`, `api_import`, `internal_create` に固定する
    - `sales_reports` に `replaces_report_id` を持たせ、現行正本は `superseded_by_id IS NULL AND status='approved'` とする
  - UI/UX:
    - VANZAI 職員ログイン時の担当案件判定は `current_user.vanzai_staff_id` を使う
    - payout 一覧 / 帳票は recipient ベースで統一する
    - 訂正申請中でも旧 approved 販売報告を画面上の現行値として維持する
  - Ops/Runbook:
    - 管理者は request の作成起点を `source_type` で判別する
    - 販売報告の訂正は再提出後、承認時点でのみ現行値が切り替わる
  - Migration:
    - `users.vanzai_staff_id` の追加と排他制約が必要
    - payout backfill と移行期間中の legacy 列互換が必要
    - sales report の partial unique と supersede 更新 transaction が必要
- Follow-ups:
  - `users.worker_id` と `users.vanzai_staff_id` の排他制約の実装方式を migration レベルで確定する
  - payout legacy 列の廃止タイミングを Phase 7 完了条件に組み込む
  - sales report 訂正の pending 件数制御を API 仕様へ落とす

---

### DEC-020: Phase 0 分析・公開リンク・受付詳細の確定（2026-04-08）
- Date: 2026-04-08
- Status: Confirmed
- Decision: 簡易 PL の確定値 / 予測値、個人成績の遅刻閾値、公開リンク運用、身分証保持、request detail の原文保存方針、`registration_request_files.document_type` を確定する
- Context:
  - Phase 0 の残論点のうち、分析定義と公開受付まわりを先に固めないと migration の列定義と API 仕様が止まる
  - 既存 aggregation は Assignment / Actual ベースで動いているが、月次 PL の確定値は帳票との整合が必要だった
  - 身分証アップロードは retention と document type を決めないと file lifecycle が定義できない
- Options:
  - A: 実装時まで保留し、画面や API を作りながら調整する
  - B: 先に運用ルールまで確定し、計画書へ落とす
- Chosen: B
- Why:
  - PL の確定値と予測値を分けることで、月次帳票整合と進行中の見込み管理を両立できる
  - 遅刻閾値、リンク有効期限、ロック回数、保持期間は DB / API / UI の共通前提になる
  - request detail を原文保存に寄せた方が Google Form 由来の入力差異や監査に強い
- Impact:
  - Data model:
    - 簡易 PL は確定値と予測値を分けて返す
    - 個人成績の遅刻は 15 分超過を基準に集計する
    - 公開リンクは 7 日有効、PIN は 5 回失敗でロックする
    - 身分証ファイルは承認 / 却下後 180 日保持し、accounting を削除責任者とする
    - request detail は原文保存を優先し、`registration_request_files.document_type` は `driver_license`, `my_number_card`, `residence_card`, `passport`, `other` を使う
    - 同一書類の表裏を区別するため `document_part` を持つ
  - UI/UX:
    - PL 画面は確定値と予測値を併記する
    - 公開フォームはリンク期限と PIN ロック状態を利用者に明示できる
    - 管理画面では request 詳細で原文入力と正規化結果を比較できる
  - Ops/Runbook:
    - accounting が身分証ファイルの削除責任を持つ
    - 管理者は same URL の reset と新 URL 再発行を使い分ける
  - Migration:
    - request detail 列と `document_part` を含む file テーブル定義が必要
    - 分析 API は確定値 / 予測値の両系統を返せる設計にする
- Follow-ups:
  - `document_part` を partial unique や必須条件でどう拘束するかを migration レベルで確定する
  - retained file の自動削除ジョブと監査ログ粒度を RUNBOOK へ落とす
  - PL 画面で確定値 / 予測値をどう並べるかを UI 要件へ落とす

---

### DEC-021: Phase 0 残論点の確定（2026-04-08）
- Date: 2026-04-08
- Status: Confirmed
- Decision: supplier 口座管理、project_type 3 階層移行、admin-notices の未処理キュー範囲を確定する
- Context:
  - payout recipient は汎化方針が決まったが、supplier 口座をどのモデルで持つかは未確定だった
  - project_type は既存実装がフラット前提で、3 階層化時の移行方針を先に決める必要があった
  - admin-notices も staff_notices とは別概念として、どこまで未処理キュー化するかを固める必要があった
- Options:
  - A: 3 点とも Phase 1 実装時に都度決める
  - B: Phase 0 で運用前提まで確定する
- Chosen: B
- Why:
  - supplier 口座は過去支払の再現性要件があるため、履歴管理前提を先に固定すべき
  - project_type の付与階層を決めないと migration と UI が確定しない
  - admin-notices の対象範囲を決めないと API / dashboard / 運用責任が曖昧になる
- Impact:
  - Data model:
    - supplier 口座は Phase 1 で `supplier_bank_accounts` を追加し、履歴管理する
    - project_type は leaf（minor）のみ案件へ付与する
    - 既存 flat project_type は migration で major 化し、各 major 直下に minor を新設して既存 project を backfill する
    - admin-notices は `target_url`, `is_read`, `is_resolved` を持つ未処理キューとして扱う
  - UI/UX:
    - project 作成 / 編集画面は leaf のみ選択可能にする
    - dashboard の admin-notices は request 未審査、身分証未確認、sales_reports 未承認、期限超過 project_tasks、payout エラーを入口にする
  - Ops/Runbook:
    - supplier 口座変更後も過去支払の再現性を維持する
    - project_type 移行時は既存 project の再分類を migration で吸収する
    - admin-notices は summary ではなく処理完了まで追える運用にする
  - Migration:
    - `supplier_bank_accounts` 追加が必要
    - project_type major / minor の再編と project の backfill が必要
    - admin-notices 用テーブルまたは同等の永続状態管理が必要
- Follow-ups:
  - admin-notices の永続化方式を既存 dashboard summary 拡張と別テーブルのどちらにするか、実装時に具体化する

---

### DEC-022: project_type 自動生成 minor 命名規則の確定（2026-04-08）
- Date: 2026-04-08
- Status: Confirmed
- Decision: 既存 flat project_type を major 化する migration で自動生成する minor の表示名と code 規則を確定する
- Context:
  - DEC-021 で project_type は leaf（minor）のみ案件へ付与し、既存 flat 種別は major 化して直下に minor を新設する方針を確定した
  - その時点では自動生成 minor の命名規則だけが未決だった
- Options:
  - A: `major名 + （標準）`, `major_code + -DEFAULT`
  - B: major と同名、code のみ差別化
  - C: `major名 + （既存）` など移行由来を前面に出す
- Chosen: A
- Why:
  - UI 上で既定の選択肢だと直感的に分かる
  - code も機械的に生成しやすく、migration の backfill が単純になる
  - 既存 major と minor を同名にしないため、管理画面で混乱しにくい
- Impact:
  - Data model:
    - 自動生成 minor の表示名は `major名 + （標準）`
    - 自動生成 minor の code は `既存 major code + -DEFAULT`
  - UI/UX:
    - project_type ツリー上で既定の末端種別が識別しやすい
  - Ops/Runbook:
    - 移行後に人手で名称調整が必要な場合でも、初期配置ルールが統一される
  - Migration:
    - project_type backfill 時の生成ロジックを一意に書ける
- Follow-ups:
  - major_code が NULL の既存 project_type に対する code 生成 fallback を migration 設計で決める

---

### DEC-023: VANZAI担当者支払の初回実装範囲と本人稼働分の正本（2026-04-08）
- Date: 2026-04-08
- Status: Confirmed
- Decision: VANZAI担当者支払の初回実装は 全体統括責任者 と 事務 を対象にし、全体統括責任者の本人稼働分は `vanzai_staff.linked_worker_id` で worker 実績へ明示的に紐付けて VANZAI担当者支払へ集約する
- Context:
  - Kintone 運用では 全体責任者は drv社売上の8% に加えて自身の稼働分も支払対象だった
  - 一方、現行 DB では `vanzai_staff` と `workers` が直接つながっておらず、本人稼働分を自動判定すると誤計上リスクがある
  - 事務は 固定 43,200円 + 月内暦日 × 2,160円 の共通ルールで運用している
  - プレイングマネージャーは 人工 × 1,000円 と固定10万円の個別差があり、初回実装では未確定
- Options:
  - A: VANZAI担当者支払は role ごとの確定分だけ先行し、本人稼働分は `linked_worker_id` で明示紐付けする
  - B: 氏名一致で worker を自動判定する
  - C: 本人稼働分は一旦除外し、8% のみ実装する
- Chosen: A
- Why:
  - 氏名一致は誤紐付けの事故リスクが高く、推測実装になる
  - `linked_worker_id` を持たせれば本人稼働分の由来が監査可能になる
  - 初回対象を 全体統括責任者 と 事務 に絞ることで、未確定のプレイングマネージャー報酬を混ぜずに導入できる
- Impact:
  - Data model:
    - `vanzai_staff.linked_worker_id` を追加し、必要時のみ worker を明示紐付けする
  - UI/UX:
    - VANZAI担当者マスタで役職と対応 worker を設定できるようにする
    - 支払生成 UI で `recipient_type=vanzai_staff` を生成可能にする
  - Ops/Runbook:
    - 全体統括責任者の linked worker には通常の worker 支払を出さず、VANZAI担当者支払へ集約する
    - drv案件の 8% 集計対象は `client.name = 'drv社'` の請求書とする
    - 事務は role=事務 の全員へ 共通式を適用する
  - Migration:
    - `vanzai_staff.linked_worker_id` の追加が必要
- Follow-ups:
  - プレイングマネージャーの 個別固定 / 人工連動 の切替方式を別 decision として確定する
  - VANZAI担当者の振込口座マスタ化を後続フェーズで追加する

---

### DEC-024: プレイングマネージャー支払の計算方式と運営協力費の扱い（2026-04-08）
- Date: 2026-04-08
- Status: Confirmed
- Decision: プレイングマネージャー支払は基本を `配下人工 × 1,000円` としつつ、個人別に `固定額` へ切り替え可能にする。運営協力費は月ごとの手入力額を別行で加算する
- Context:
  - Kintone 参考実装では プレイングマネージャーに area 単位の管理費と 運営協力費 を別行で計上していた
  - 一方で現運用には 個人別に月額固定で扱っている担当者も存在し、人工連動か固定かを一律には決められない
- Options:
  - A: 全員を 配下人工 × 1,000円 に統一する
  - B: 全員を 固定額に統一する
  - C: 個人ごとに `配下人工 × 1,000円` と `固定額` を切り替えられるようにし、運営協力費は月次手入力の別加算にする
- Chosen: C
- Why:
  - 現運用に固定額の例外が存在するため、単一ルールへ即時統一すると運用差分を吸収できない
  - 配下人工 × 1,000円 は既存 decision と整合し、固定額は個別設定で安全に扱える
  - 運営協力費は対象月ごとの変動入力が必要であり、マスタ固定ではなく生成時入力の方が実態に合う
- Impact:
  - Data model:
    - `vanzai_staff.playing_manager_fee_type` を追加
    - `vanzai_staff.playing_manager_fixed_fee` を追加
  - UI/UX:
    - VANZAI担当者マスタでプレイングマネージャーの計算方式と固定額を設定できるようにする
    - 支払生成画面でプレイングマネージャー選択時のみ運営協力費を入力できるようにする
  - Ops/Runbook:
    - 配下人工は managed project の valid actual を `(worker_id, work_date, project_id)` で数える
    - 固定額方式の担当者は、固定額未設定なら支払生成をエラーにする
    - 運営協力費は対象月ごとに手入力し、支払明細へ別行で残す
  - Migration:
    - `vanzai_staff` への追加カラム migration が必要
- Follow-ups:
  - プレイングマネージャー本人の稼働分を管理報酬に含めるかは、運用ルールとして別途確定する
  - VANZAI担当者向け振込口座マスタ化の後続設計を行う

---

### DEC-025: プレイングマネージャー本人の稼働分を管理報酬の人工に含める（2026-04-08）
- Date: 2026-04-08
- Status: Confirmed
- Decision: プレイングマネージャー本人が自分の管理案件で稼働した valid actual も、現場管理報酬の配下人工に含める
- Context:
  - DEC-024 では計算方式の切替と運営協力費の扱いを確定したが、本人稼働の扱いだけ未決だった
  - Kintone 参考実装では、管理者ごとの集計時に本人稼働を除外する分岐がなく、管理案件の実績をそのまま束ねていた
  - 現行実装の `_count_vanzai_manager_man_days` も `Project.vanzai_manager_id = 対象担当者` の valid actual を `(worker_id, work_date, project_id)` 単位で数えており、本人稼働を別扱いにしていない
- Options:
  - A: 本人稼働も配下人工に含める
  - B: 本人稼働は配下人工から除外する
  - C: 担当者ごとに含む/含まないを切り替えられるようにする
- Chosen: A
- Why:
  - 旧運用と現行実装が同じ挙動でそろっており、ここで除外へ変える根拠がない
  - 除外ルールを後付けすると、過去資料との突合が崩れやすく、再現性が落ちる
  - 個別切替を入れるほどの運用根拠は現時点で確認できていない
- Impact:
  - Data model:
    - 追加なし
  - UI/UX:
    - プレイングマネージャー本人稼働を除外する設定 UI は設けない
  - Ops/Runbook:
    - 管理案件での本人稼働日は、他の配下メンバーと同様に現場管理報酬の人工へ算入する
    - 本人の実作業分を支払明細へ載せるかどうかは `linked_worker_id` による worker 紐付けで別管理する
  - Migration:
    - 追加なし
- Follow-ups:
  - プレイングマネージャー候補の `linked_worker_id` 整備を進め、本人作業分の明細化可否を運用で確定する
  - 将来、本人稼働の除外要件が出た場合は別 decision として toggle 追加要否を再検討する

---

### DEC-026: PAYGATE精算レシート OCR・在庫照合機能の確定事項（2026-07-02）
- Date: 2026-07-02
- Status: Confirmed（一部 Follow-up あり）
- Decision: `PAYGATE精算レシート OCR・在庫照合 計画書（改訂版 v4）`のレビュー③④で提起された論点のうち、`reconciliation_eligible` の既定値、在庫調整の自己申告制、`branch_id` の必須化タイミング、`credit_sales`/`pos_sales` の移行方針、同一端末・同日複数精算の扱いを実装方針として確定する
- Context:
  - 精算レシートOCRの在庫照合機能を実装するにあたり、複数回のレビュー（合計4件）で指摘された設計上の分岐点を実装前に確定する必要があった
  - 未確定のまま実装すると、DB制約・API・UIのいずれかで手戻りが発生するリスクが高い
- Options（主要論点ごと）:
  - `reconciliation_eligible` 既定値: A. `false`（opt-in） / B. `true`（opt-out）
  - 在庫調整の承認: A. 第三者承認フロー実装 / B. 自己申告制＋月次レビュー（システム改修なし）
  - `branch_id`: A. Phase 0結果待ちで追加 / B. 最初から照合キーに含める
  - `credit_sales`/`pos_sales`移行: A. 過去データ移行しない / B. マイグレーションで一括移行 / C. API吸収
  - 同一端末・同日複数精算: A. 発生しない前提でキー一意制約のみ / B. 発生しうる前提でOCR行は複数許容、在庫照合対象のみ一意制約
- Chosen:
  - `reconciliation_eligible` 既定値: **B（true, opt-out方式）**
  - 在庫調整: **B（自己申告制。`confirmed_by`は`entered_by`と同一人物で可。月次で事務局責任者が目視レビュー）**
  - `branch_id`: **B（最初から照合キー`(branch_id, terminal_short_id, work_date)`に含める）**
  - `credit_sales`/`pos_sales`移行: **A（過去データの遡及移行は行わない。新規解析分のみ`pos_sales`使用）**
  - 同一端末・同日複数精算: **B（OCR確定行は複数許容。`reconciliation_eligible=true`の行のみ部分ユニーク制約で1件に制限）**
- Why:
  - opt-out方式は「大半の確定行はそのまま在庫照合に使う」という実態の運用負荷に合致するため。ただし複数行が誤って同時に対象化される事故を防ぐため、部分ユニーク制約をPhase 2の必須要件とした
  - 在庫調整の第三者承認は事務局体制上のコストが高く、月次の事後レビューで不正・隠蔽リスクを許容水準まで軽減できると判断
  - `branch_id`はレシートの端末識別番号が支社横断で一意である保証がなく、早期に含めるほうが安全
  - `credit_sales`/`pos_sales`は過去データに新ラベル（PAYGATE POS）自体が抽出されていないため、遡及移行は事実上不可能
  - 同一端末・同日複数精算は「発生しない」と断定する根拠がなく、現場運用（途中精算・レシート再発行等）を考慮すると発生しうる前提で安全側に倒すべき
- Impact:
  - Data model:
    - `ocr_extracted_rows` に `terminal_short_id`, `pos_sales`, `other_payment`, `cash_unit_count`, `pos_unit_count`, `work_date`, `unit_breakdown_status`, `unit_breakdown_json`, `amount_ones_digit_ok`, `blocking_errors`, `warnings`, `duplicate_receipt_candidate`, `reconciliation_eligible`(DEFAULT true), `excluded_reason`, `voided_at`, `voided_by`, `void_reason`, `branch_id`, `staff_id` を追加
    - `uq_ocr_settlement_reconciliation_target` 部分ユニークインデックスを追加（`branch_id, terminal_short_id, work_date` × `reconciliation_eligible=true` × `status=confirmed` × `voided_at IS NULL`）
    - `inventory_snapshots` / `inventory_reconciliation_batches` / `inventory_reconciliation_results` を新規追加
  - UI/UX: `ReceiptOcrPage.tsx` に精算レシート専用列・編集モーダル・無効化／照合対象除外操作・実在庫入力セクション・在庫照合実行セクションを追加
  - Ops/Runbook: `docs/ops/OCR_INVENTORY_RUNBOOK.md`（旧`OCR_RECEIPT_RUNBOOK.md`）に月次`adjustment_reason`レビュー手順、実在庫入力手順、確定条件を追記。正式ルールは `docs/spec/OCR_INVENTORY_RECONCILIATION_SPEC.md` に記載
  - Migration: `alembic/versions/20260702a001_add_inventory_reconciliation.py`
- Follow-ups:
  - **JTとの契約上、決済・在庫関連データをVANZAI（社外DB）に保存してよいか**は未検討。契約内容の確認は本システム設計とは別タスクとして管理する（設計のブロッカーとしない）
  - パイロット運用（`docs/ops/OCR_INVENTORY_PILOT_TEMPLATE.md`）の結果、「通常取引数＝販売台数」の前提が成立しないケースが多数見つかった場合は、在庫照合の主指標の見直しを別 decision として記録する
  - `branch_id`の運用上の未入力が継続する場合、NOT NULL制約化を再検討する
- Spec Reference: `PAYGATE精算レシート OCR・在庫照合 計画書（改訂版 v4）`、`docs/spec/OCR_INVENTORY_RECONCILIATION_SPEC.md`

