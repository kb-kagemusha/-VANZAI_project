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

