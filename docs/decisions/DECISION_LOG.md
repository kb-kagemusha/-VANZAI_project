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

---

### DEC-027: 発注依頼書は確定版を正本にし、公式LINE送信は別単位にする（2026-10-02）
- Date: 2026-10-02
- Status: Confirmed（書式とLINEチャネルは未入手）
- Decision: 発注依頼書の初期実装は、共通の入力内容を版として確定し、版×稼働者の送付行と共有一覧までとする。確定後の本文・PDF・送付時の氏名は上書きしない。公式LINEへの push、本人紐付け、受領Webhookは、利用企業の公式アカウント権限と弁護士確認済み書式が揃ってから接続する。
- Context:
  - 計画は「発注依頼書の作成・公式LINE送付・受領履歴」。目的は、誰が誰に何を送り、誰が受領操作をしたかを担当者間で共有すること
  - リポジトリに弁護士確認済み書式は無く、LINEチャネルの秘密情報も無い
  - 受領は本人の「受け取りました」であり、PDFを開いたことや電話連絡では成立しない
- Options:
  - A: 書式とチャネルが揃うまでコードを置かない
  - B: 保存・版・送付行・一覧を先に作り、PDFは入力の保存用とし、送信は未接続のままにする
  - C: 仮の法的書式とLINE送信まで一度に作る
- Chosen: B
- Why:
  - 送付履歴が残ることが課題の中心であり、送信成功を待ってから記録する形にはしない
  - 未入手の書式を法的レイアウトとして固定せず、入手後に差し替える余地を残す
  - チャネル権限が無い状態で push を実装しても受入できない
- Impact:
  - Data model: `order_request_documents` / `order_request_versions` / `order_request_deliveries` / `order_request_notes`
  - UI/UX: 管理画面「発注依頼書」（admin / ops）。テスト区分は既定の一覧に出さない
  - Ops/Runbook: 導入手順は `docs/ops/LINE_ORDER_REQUEST_ROLLOUT_2026-10-01.md`
  - Migration: `alembic/versions/20261002a001_add_order_requests.py`
- Follow-ups:
  - 弁護士確認済み書式と受託者名の記載方法を入手し、PDFレイアウトを合わせる
  - 公式アカウントの管理権限を得てから、本人紐付け、1人ずつの送信、受領Webhookを接続する（テスト用アカウントの接続は DEC-028）
  - PDF閲覧期間、未受領の業務期限、パスワード再発行手順は試行前に運用側で決める
- Spec Reference: 発注依頼書LINE送付 初期版計画（2026-10-01）、`docs/ops/LINE_ORDER_REQUEST_ROLLOUT_2026-10-01.md`

---

### DEC-028: テスト用公式LINEではテスト区分だけを1人ずつ送る（2026-10-06）
- Date: 2026-10-06
- Status: Confirmed（書式は未入手。PDF閲覧期間とコード期限は暫定）
- Decision: テスト用公式アカウントが使える状態になったので、本人紐付け、1人ずつの push、受領Webhookを接続する。送れるのはテスト区分だけとする。正式区分は弁護士確認済み書式が適用されるまで送らない。紐付けは、管理画面が発行した一次性コードを本人のLINEから公式アカウントへ送ったときだけ成立させる。受領は「受け取りました」の postback だけを記録し、PDFを開いたことでは記録しない。解除した紐付けへの送信は止める。
- Context:
  - DEC-027 はチャネル権限が無い間、送信を未接続にしていた
  - テスト用公式アカウントの Messaging API と長期チャネルアクセストークン、友だち追加が揃った
  - 弁護士確認済み書式はまだ無い
  - PDF閲覧期間、未受領の業務期限、パスワード再発行手順は未決
- Options:
  - A: 書式が揃うまで送信コードを置かない
  - B: テスト区分だけ送り、正式区分と書式レイアウトは止めたままにする
  - C: 正式区分も同じPDFで送る
- Chosen: B
- Why:
  - 送信経路と受領記録は、書式の欄位置と独立して確認できる
  - 未確認の書式を正式な発注として送ると、テストと正式の区別が崩れる
- Impact:
  - Data model: `line_worker_links` / `line_link_codes` / `line_webhook_events` / `order_request_send_attempts` / `order_request_file_tokens`
  - UI/UX: 発注依頼書画面に紐付けと「この1人にテスト送信」
  - Ops/Runbook: チャネル値はサーバー環境変数。Webhook URL は `https://api.vanzai-portal.com/api/line/webhook`
  - Migration: `alembic/versions/20261006a001_add_line_order_links.py`
- Follow-ups:
  - PDFを開ける期間（暫定7日）と紐付けコードの期限（暫定30分）を運用側が確定する
  - 弁護士確認済み書式の適用後に、正式区分の送信可否を別決定にする
  - 未受領の業務期限とパスワード再発行手順は試行前に決める
- Spec Reference: DEC-027、`docs/ops/LINE_ORDER_REQUEST_ROLLOUT_2026-10-01.md`

---

### DEC-029: 稼働者タグは定義済みの4種だけにする（2026-10-06）
- Date: 2026-10-06
- Status: Confirmed（タグの種類は名簿と配置の呼び方から暫定。追加は定義の更新で行う）
- Decision: 稼働者に複数タグを付けられるようにする。タグは自由入力せず、定義済みの「常勤」「スポット」「リーダー可」「新人」だけを選ぶ。
- Context:
  - 稼働者を一覧と出勤カレンダーで見分けたい
  - スタッフ名簿の区分は「常勤 or スポット」で、配置の役割にはリーダーがある
  - タグの種類を画面から増やす運用は、今回の範囲に入っていない
- Options:
  - A: 任意の文字列をタグとして保存する
  - B: 定義済みコードだけを保存し、画面は選択式にする
  - C: タグ用のマスタ画面を作り、運用中に追加できるようにする
- Chosen: B
- Why:
  - 表記ゆれを防ぐ
  - タグの追加はコード上の定義を1か所変えるだけで足りる
- Impact:
  - Data model: `workers.tags`（JSON配列。コードのみ）
  - UI/UX: 稼働者登録・一覧とマスタデータでチェック選択。一覧はタグで絞り込める。出勤カレンダーの名前の下にも出す
  - Ops/Runbook: 新しいタグが必要になったら `src/domain/worker_tags.py` の定義を増やす
  - Migration: `alembic/versions/20261006d001_add_worker_tags.py`
- Follow-ups:
  - 現場で不足するタグが出たら、定義へ追加する
- Spec Reference: DESIGN_SPEC_v0.3 セクション6.1

---

### DEC-030: 稼働者タグを現場区分の7種にし、新人は3ヶ月で外す（2026-10-08）
- Date: 2026-10-08
- Status: Confirmed（DEC-029 のタグ種類を置き換える）
- Decision: 稼働者タグは「新人」「飲食D」「商業D」「渋喫D」「小型イベD」「中型イベD」「大型イベD」だけにする。新人は付けた日から3ヶ月後に外れる。以前の「常勤」「スポット」「リーダー可」は選ばない。
- Context:
  - タグは勤務形態ではなく、回れる現場の種類で見分けたい
  - 新人は期間が来たら外す運用にしたい
- Options:
  - A: 画面の説明だけ変えて、外す操作は手作業のままにする
  - B: 付けた日を起点に3ヶ月後の日付を保存し、期限が来たらタグを外す
- Chosen: B
- Why:
  - 一覧を開いたときに期限切れの新人が残らない
  - 同じ新人タグを付け直したときは、その日から改めて3ヶ月にする
- Impact:
  - Data model: `workers.tags` のコードを差し替え。`workers.newcomer_until` を追加
  - UI/UX: 稼働者登録の入力欄を同じ高さに揃える。状態は「有効 / 無効」が読めるチェックにする。各タグに説明を出す
  - Ops/Runbook: 旧タグは一覧に出ない。すでに付いている新人は、付けた日が残っていないため、この変更を入れた日から3ヶ月で外す。新人の自動解除は監査ログを残さない。手での付け外しは従来どおり残す
  - Migration: `alembic/versions/20261008b001_worker_newcomer_until.py`
- Follow-ups:
  - なし
- Spec Reference: DESIGN_SPEC_v0.3 セクション6.1、DEC-029

---

### DEC-031: イベント規模のタグは1つだけ（2026-10-08）
- Date: 2026-10-08
- Status: Confirmed
- Decision: 小型イベD・中型イベD・大型イベDはタグ欄の2行目に並べ、同時に1つだけ付ける。新しく選んだ規模が残り、それまでの規模は外れる。どれも付けないことはできる。
- Context:
  - イベントの規模は重ならない
- Options:
  - A: 3つとも同時に付けられる
  - B: 3つのうち1つだけ残す
- Chosen: B
- Why:
  - 現場の人数帯は1人の稼働者に1つで足りる
- Impact:
  - Data model: 保存時も3つのうち後から指定した1つだけを残す
  - UI/UX: 2行目の3枠
  - Ops/Runbook: なし
  - Migration: なし
- Follow-ups:
  - なし
- Spec Reference: DEC-030

---

### DEC-032: 公式LINEの稼働者登録はLIFF送信後に申請し、既存者は有効紐付けを必須にする（2026-10-11）
- Date: 2026-10-11
- Status: Confirmed（Q05の利用目的・保持期間、Q06の本番入口有効化は未決）
- Decision: 公式LINEの「登録」には全員共通のLIFFボタンだけを返す。申請は、サーバーがLINEのIDトークンを検証したあとのフォーム送信時に作る。有効なLINE紐付けは成立経路を問わず次回から再利用する。未紐付けの既存Workerへの初回反映には、一次性コードによる有効紐付けを必須にする。新規Workerを作る承認だけが、同じ取引で紐付けを作る。
- Context:
  - 本人入力と管理者承認を分け、別人への反映と二重登録を防ぎたい
  - 既存の公開登録は期限付きリンクとPINであり、`source_type` は DEC-019 の4種類に固定されている
  - DEC-028 の紐付けは、管理画面が発行した一次性コードを本人が送ったときに成立する
  - Webhookの共有セッションを途中で確定すると、同じ受信に含まれる受諾・辞退まで確定し得る
- Options:
  - A: 「登録」の受信時に個人別の受付を作り、既存の未紐付け者も管理者照合だけで更新・紐付けする
  - B: 共通LIFFボタンとし、申請は送信時に作る。有効紐付けは再利用し、未紐付けの既存者にはコードを必須にする
- Chosen: B
- Why:
  - ボタン返信の成否に申請の存在を依存させず、再送と取引境界を既存Webhookに追加しない
  - 自己申告の氏名や電話だけでは、既存稼働者へ他人の情報とLINEを結び得る
  - 新規承認で作った紐付けを、次回の補完でも有効紐付けとして再利用できる
- Impact:
  - Data model:
    - `worker_registration_request_details.birth_date` を DATE NULL で追加する。Worker の `name`（100）、`furigana`（200）、`birth_date`、`postal_code`、`address` は既存列を使う
    - `line_registration_sessions`：セッションIDハッシュは一意。検証済みLINE主体、期限、開始時の紐付けIDとWorker IDを持つ。住所と生年月日は持たない。期限は60分、延長なし
    - `line_registration_contexts`：申請IDは一意。検証済みLINE主体、送信時の紐付けIDとWorker ID、継続中フラグを持つ。継続中の主体は部分ユニークで1件。返信結果と発行時の更新日時は持たない
    - `line_registration_submit_keys`：主体と冪等キーの組は一意。申請IDと正規化内容のハッシュを持つ。1申請に複数キーを結び付けられる
    - `line_registration_review_snapshots`：申請、選択Worker、期待する紐付け、審査者、影響項目のサーバー取得値、期限を持つ。期限は60分。恒久保存しない
    - `registration_requests.source_type` は `public_form` のままにする。LIFF申請にはPINと公開tokenを発行しない
  - UI/UX:
    - 「登録」は共通LIFFボタン。フォームは送信時に確認待ちの申請になる
    - 有効紐付け済みは部分入力。未紐付けは基本項目を必須にする
    - 氏名は「姓＋半角スペース＋名」、ふりがなも同様。住所は都道府県と住所1を連結し、住所2があれば改行を挟む
  - Ops/Runbook:
    - 入口フラグの初期値は無効。本番有効化はQ05、PostgreSQL競合試験、実機確認、チャネルのPublished確認の後
    - 競合時は当該取引だけを巻き戻す。他の取引が確定した状態は戻さない
    - 成功監査は業務更新と同じ取引で確定する。失敗記録は巻き戻し後の別取引で、申請ID、実行者、理由分類だけを残す
  - Migration: 上記の表と列。ファイルの追加と適用は機能実装時に行う
- Follow-ups:
  - Q05：利用目的、取得項目、保持期間、削除または匿名化。確定前は架空情報だけ
  - Q06：本番入口の有効化。今回は公開状態も入口フラグも変えない
  - 通知（Q04）と書類アップロードは今回含めない
  - DEC-033は2026-10-11に採用済み。審査スナップショット表は作らない。このConfirmedの基本方針は置き換えない
- Spec Reference: DEC-019、DEC-020、DEC-028、`docs/ops/LINE_WORKER_REGISTRATION_PLAN_2026-10-11.md`

---

### DEC-033: LINE稼働者登録の認証・比較票・編集ガードを改める（2026-10-11）
- Date: 2026-10-11
- Status: Confirmed（2026-10-11に採用。DEC-032の基本方針は維持する）
- Decision: 登録専用認証はメモリ上のBearerにする。審査用の現在値をDBへ複製せず、サーバーが発行する期限付きの署名付き比較票を使う。通常のWorker更新にも、本機能が変える7項目の比較ガードを足す。再送キーの対応表は残し、送信内容は平文のハッシュではなく認証付きハッシュで対応づける。
- Context:
  - DEC-032は共通LIFF、送信時の申請作成、有効紐付けの再利用、未紐付け既存者への一次性コード必須を確定している
  - 画面とAPIは別オリジンで、既存APIもBearerである
  - 現行のWorker更新はプロフィールを一括保存し、古い編集画面が承認後の値を戻し得る
  - 再送キーを捨てると、承認後の遅延再送で申請が増える
- Options:
  - A: DEC-032の4表、Cookie認証、審査スナップショット表のまま実装する
  - B: セッション表、申請context、再送キー対応の3表にし、比較は署名付き票、認証はメモリBearer、通常編集にも逆方向のガードを置く
- Chosen: B
- Why:
  - 個人情報の複製と期限切れ行を減らし、承認と通常編集で同じ比較の考え方を使える
  - CookieとCSRFを新設せず、既存のBearer方式に寄せられる
  - 再送キー対応を残すと、確認中に保存しなかった別キーの遅延再送で申請を増やさない
- Impact:
  - Data model:
    - 新設は `line_registration_sessions`、`line_registration_contexts`、`line_registration_submit_keys` の3表。DEC-032の `line_registration_review_snapshots` は作らない
    - `worker_registration_request_details.birth_date` は DATE NULL のまま。新しい変換と生年月日・住所の承認反映はLINE起点だけに適用する
    - 継続中は `status=pending` かつ `deleted_at IS NULL` のLINE申請に限る
  - UI/UX:
    - 登録Bearerはメモリだけに置き、Cookie、localStorage、sessionStorage、URLへ保存しない。管理者APIへ転用しない
    - 確認中の別キーは、今回の入力を本文に保存していないことを案内する
    - Worker編集は開始時の最新値と比較票から始め、7項目の不一致は409で再読込を案内する
  - Ops/Runbook:
    - PostgreSQLの独立接続試験を、送信・審査の取引実装より前に用意する。入力変換などの準備実装はそれまで止めない
    - 期限切れセッションの削除担当、頻度、失敗時の再実行をRUNBOOKに書く
    - 入口は無効のまま。Q05確定前は架空情報だけ
  - Migration: `alembic/versions/20261011a001_line_registration_tables.py`。3表、制約、`birth_date`。本番DBへは未適用。入口は有効にしない
- Follow-ups:
  - 試験用PostgreSQLの基盤準備と、実装後のLINE承認競合試験合格は別である。後者は未実施
  - Q05に送信キー対応の保持と、再送を識別できる期間を含める
  - 試験用PostgreSQLでは本番DBとsecretsを使わない
- Spec Reference: DEC-032、`docs/ops/LINE_WORKER_REGISTRATION_PLAN_2026-10-11.md`




### 2026-10-12: DEC-032/033の検証入口設定
- 利用者の公式LINEは既存のMessaging APIチャネルを継続し、同じプロバイダーのLINEログインチャネルをLIFFに使用する。
- ユーザーは今回に限り、追加設定、起動処理の変更、再起動と作業用コピー作成を許可した。今後の変更は毎回確認する。
- 既存の秘密情報ファイルを読まず・上書きせず、git管理外の `line-registration-config.json` に登録入口の3項目だけを置き、API lifespanで読み込む。業務DBと承認ルールは変更しない。
- 検証入口のみ有効化する。LINEログインチャネルは開発中で、実機確認とQ05の確定は未完了。一般公開・実在者情報の取得の完了とは扱わない。


### DEC-034: LINE登録の入力画面と任意のアクセス項目（2026-10-12）
- Status: Confirmed（ユーザーがロゴ使用、最寄り駅・徒歩時間の追加、利用目的の明示と実装を許可）
- Decision: 既存の本人確認・再送・管理者承認方式を維持し、スマートフォン向けの入力・確認・受付画面へ改める。提供ロゴを使用する。
- Data: Workerの既存nearest_station・station_walk_minutesを使い、申請詳細に同名のNULL可2列を追加。駅100文字、徒歩時間0〜300分。任意入力・空欄保持・0分保持。通常編集とLINE審査の比較対象を7項目から9項目へ拡張。旧申請は新項目が空欄なら元の本文ハッシュを維持する。
- Purpose: 入力前に「ご入力いただいた個人情報は、当社の稼働者情報の登録・更新、お仕事のご案内および業務連絡のために利用し、これらの目的以外には利用しません。」を表示する。利用目的の具体化と取得前の明示は個人情報保護委員会の通則編を参照（https://www.ppc.go.jp/personalinfo/legal/guidelines_tsusoku/）。
- Scope: 利用目的の短文のみ今回確定。Q05の保持期間、削除・匿名化、事業者の正式なポリシーは未確定で、法令対応全体の完了とは扱わない。クライアント用公式LINEは別。検証用チャネルを公開済みにしたのはユーザー操作である。
- Tests/Audit: 申請保存、承認反映、空欄保持、0分、競合拒否、旧申請の再送と本人変更を試験する。既存の申請・承認監査に2項目を含める。ログへ認証情報を出さない。

### DEC-035: 新規LINE登録の必須項目・緊急連絡先・住所補完（2026-10-12）
- Status: Confirmed（ユーザーが実装を指示し、新規だけ必須・更新は変更項目だけ・建物名は任意、Web対象は稼働者一覧の新規登録と回答）
- Decision: DEC-034の任意入力を新規LINE登録について変更する。建物名以外の全入力を必須にする。既存LINE更新は空欄保持を継続し、緊急連絡先の電話番号・氏名・関係は1組で変更する。稼働者一覧の新規登録も緊急連絡先3項目を必須にし、従来の最小マスタ作成経路は変更しない。
- Why: 新規登録の不足情報を減らし、緊急時に連絡する相手と関係を確認できるようにする。既存更新では無関係な情報の再入力を求めない。
- Data: 既存の緊急連絡先電話列を再利用。Workerと申請詳細に緊急連絡先氏名・関係のNULL可列を追加。既存の氏名カナ列は保持し、氏名と混同しない。申請詳細にサーバーが設定するフォーム版を追加し、新規送信は2、旧申請はNULLとする。新必須条件は新規送信と版2以降の新規承認に適用し、旧申請の審査と本文ハッシュを維持する。
- Comparison: 通常編集・LINE承認の比較対象を9項目から12項目へ拡張する。APIで省略された緊急連絡先は変更しない。
- Address: 既存Web版と同じZipcloudへ郵便番号だけを送る。全角数字・ハイフンを整え、7桁で検索。複数候補は利用者が選び、手入力の競合・古い検索結果・建物名の上書きを防ぐ。10秒で検索を打ち切り手入力へ進める。番地は補完対象外。
- Purpose: 利用目的の明示に「緊急時の連絡」を追加する。保持期間・正式ポリシーなど未決の法令対応全体は今回確定しない。
- Tests/Audit: 新規必須、更新空欄保持、3項目保存・承認、旧申請再送・承認、Web新規、住所補完の競合・失敗・候補選択、PostgreSQL承認競合を確認する。既存の稼働者更新監査に緊急連絡先を含め、認証情報はログに出さない。
- Spec Reference: DESIGN_SPEC_v0.3 セクション6.1、DEC-034

### DEC-036: 登録済みLINE情報の表示と未登録項目の必須化（2026-10-12）
- Status: Confirmed（ユーザーが更新画面に保存済み情報を表示し、情報がない項目を必須入力とするよう指示）
- Decision: 本人確認済みLINEに有効な稼働者紐付けがある場合、フォーム取得APIが現在の稼働者情報を返して各欄へ初期表示する。値がある欄は「登録済み」、値がない欄は建物名を除いて「必須」と表示する。更新は変更分だけ送る。
- Names: Worker.name/furigana は全文字列保存のため、空白区切りがある値だけ姓・名へ分ける。区切りがない場合は姓欄に全文を表示し、残りは本人が確認して入力する。自動推測で文字を分割・欠落させない。
- Address: 保存済み住所から認識できる都道府県と改行後の建物名を表示する。番地等を自動推測しない。
- Security: フォーム応答にCache-Control: no-storeを設定。稼働者の12比較項目から用途付きHMAC比較票を生成し、送信時に再読込した現値と照合する。不一致時は409で受付を作らず、画面から開き直すよう案内する。同じ送信キーの保存済み再送は従来どおり照合より前に結果を返す。入力値はローカル永続ストレージへ保存しない。
- Web: 稼働者一覧の新規登録は姓・名・姓ふりがな・名ふりがな、都道府県・市区町村番地・建物名の欄に分ける。既存値は編集時に可能な範囲で分解し、元の氏名/ふりがなを保持する。
- Spec Reference: DEC-034、DEC-035

### DEC-037: 全体レビューの会計保護・二者承認・登録復帰の修正（2026-10-13）
- Status: Confirmed（ユーザーがレビュー指摘の修正とMD・CHANGELOGへの記録を指示）
- Financial: 時間単価の数量をcalc_minutes_billableへ揃え、既存の発行済み金額は変更しない。締め済みまたは確定済み明細に実績を持つ月へのCSV洗い替えと、確定済み実績の新規再計上を拒否する。CSVの稼働日と対象月を一致させる。
- Serialization: CSV・締め・金額生成・発行／承認はProjectの既存行をID順にロックする。集約生成は既存案件をまとめてロックする安全側の実装。性能最適化は負荷測定後に判断する。
- Drafts: ヘッダだけを物理削除せず、旧下書き・明細を保持して論理削除と監査を残す。再発行・訂正は明細全列と宛先／受取人スナップショットを複製する。
- Closing approval: 本締め・仮締め解除・本締め解除は申請と別の認証済み権限者の承認に分ける。両者に対象操作の現行権限を要求する。24時間期限、同一案件×月×操作の確認待ち1件、本人不可、状態・解除回数比較、再承認不可、取消／却下を採用する。
- Minimal model: closing_approval_requestsに申請者・承認者のUser FK、対象・操作・理由、申請時の状態／解除回数、期限、処理状態／承認日時を保存する。本人承認不可・承認済みの必須情報・pending部分一意をDB制約にする。既存データの書き換えはしない。DDLは20261013a001。
- LINE: 再認証後は別本人でもフォームを取得する。同じ本人・反映先は本人の編集だけを新取得値へ重ねる。別本人／反映先変更は旧入力を引き継がない。保存済み再送を先に返す規則を維持する。
- OCR: 手入力の端末番号を厳密検証し、OCR候補の文字補正は別関数にする。全文連結による日付の混入を止める。旧試験の期待を削除して合格にはせず、抽出経路と試験のエンジン呼び出しを修正する。
- Scope: 訂正／追加請求の新しい運用、営業日カレンダー、実機操作の完了はこの修正で確定しない。正本の作業先をMDに明記し、旧ワークスペースの未コミット変更は保全する。
- Audit/Tests: 下書き置換・締め申請／別本人承認／却下を記録する。再現した金額差・再計上・締め後CSV・親削除・明細欠落・本人変更を回帰試験で確認する。
- Spec Reference: DESIGN_SPEC_v0.3 セクション6.3・7・8・9・11・12、WORKSPACE_CODE_REVIEW_2026-10-13.md

### DEC-038: LINE確認待ちを稼働者一覧へ表示し、同じ画面で承認する（2026-10-13）
- Status: Confirmed（ユーザーが公式LINE登録データを稼働者一覧へ置いて反映するよう指示）
- Decision: 稼働者一覧の上部にLINE起点のpending申請を表示し、既存の専用審査パネルから管理者が反映先・差分を確認して承認する。30秒ごとの再取得と手動更新を備える。承認後に確認待ち・稼働者・LINE紐付けを再取得する。
- Why: 送信済みの申請が別の「登録申請」画面にしか出ず、登録の受付とマスタ反映の違いが一覧で分からなかった。自動承認ではなく申請と次の操作を同じ画面へ置く。
- Boundaries: DEC-032/033の本人照合・一次性コード・承認・比較票ルールと権限を維持する。adminが承認、opsは確認待ち一覧の参照のみ。登録は契約完了・稼働開始許可を意味しない。
- Minimal model/DDL: 既存5表と申請詳細を利用し、新設列・表・migrationなし。登録申請一覧のline_onlyはline_registration_contextsの存在で判定する。source_typeはpublic_formのまま。
- Audit/Tests: 既存の専用審査の成功・拒否監査を維持する。LINEと従来フォームの分離、ページング、未承認はWorkerなし、承認後の一覧反映、未認証拒否、画面の即時更新・競合拒否・運用権限・取得失敗を確認する。
- Spec Reference: DESIGN_SPEC_v0.3 §6.1、DEC-032/033、docs/ops/LINE_WORKER_INBOX_RUNBOOK.md

### DEC-039: LINE登録受付の本人通知とポップアップ審査（2026-10-13）
- Status: Confirmed（ユーザーが本人への「登録を受付けました」の送信と内容確認のポップアップ化を指示）
- Trigger: 新しいLINE申請がDBへcommitされた後、認証済みLINE主体へ受付通知を送る。マスタ反映・契約完了の通知とは区別し、管理者承認方式を維持する。今回内容が保存されていない別キー入力、保存失敗、入力エラーへは新しい受付通知を作らない。保存済み再送は既存の送信状態を使う。
- Minimal model/DDL: line_registration_receiptsを追加。申請IDをPK/FKとし、UUIDリトライキー一意、本文、pending/sent/failed、試行回数、次回試行、受理日時、HTTP状態、作成/更新日時を保存する。既存contextのLINE主体を宛先とし、個人情報を複製しない。DDLは20261013b001。既存申請へ通知行を補完しない。
- Delivery: commit後のバックグラウンド処理と60秒間隔の専用ジョブが同じキューを処理する。PostgreSQLの通知行ロックとskip_lockedで同時送信を避け、API受理後のDB保存失敗にも同じキー・宛先・本文で再試行する。最大5回、指数的待機、作成から23時間で打ち切る。2xxと受理済みID付き409だけ受理済みとし、4xxは終了、接続障害/5xxは再試行する。sentはLINEのAPI受理を表し、本人の既読やブロック解除を意味しない。
- UI: 稼働者一覧の内容確認は既存のorder-create-backdrop/worker-profile-modalと同じ枠で表示する。内部スクロール、背景スクロール抑止、Tabのフォーカス維持、Escape/閉じるで元操作へ戻る。審査の反映先・比較票・権限は維持する。
- Audit/Tests: line_registration_receipt_sent/failedに申請ID・受理状態・試行回数・HTTP状態・区分のみを記録する。本文・LINE ID・電話・住所・トークンはログへ出さない。保存後通知、再送・未保存・ロールバック、失敗再試行、24時間超過防止、受理後DB巻戻し、409判定、migration非遡及、既存発注経路、ポップアップの承認/競合/キーボード操作を試験する。
- Spec Reference: DESIGN_SPEC_v0.3 §6.1・16、DEC-032/033/038、LINE_WORKER_INBOX_RUNBOOK.md。LINE再試行の公式仕様: https://developers.line.biz/ja/docs/messaging-api/retrying-api-request/

### DEC-040: 既存LINE登録フローの修正・変更は右側の版を上げる（2026-10-13）
- Status: Confirmed（ユーザーがXは大きなアップデート、Yは機能追加、Zは修正・変更と明示し、前回はZだと指摘）
- Decision: 前回の受付通知と内容確認ポップアップは既存登録フローの修正・変更として扱い、正しい版を0.44.0から0.44.1へ更新する。誤って公開した0.45.0は0.44.1へ訂正する。0.44.0以前の版履歴は今回の訂正対象にしない。
- Why: 修正の実装に通知処理やDB表を追加したことを、利用者向けの新しい業務機能の追加と混同した。判定は利用者にとっての変更内容を基準とする。
- Impact: admin-web/staff-mobileを同一の0.44.1へ訂正し、CHANGELOGとRUNBOOKを更新する。AGENTS.md §9とrelease-workflow.mdcをX/Y/Zの定義で揃える。DB/model/DDLの追加変更なし、業務監査の追加なし。
- Verification: 両package.json・CHANGELOGの版一致、両アプリのビルド、公開version.jsonとAPI再起動後のhealthを確認する。画面の更新検知はビルドIDの不一致を使うため、今回の版番号訂正も検知する。
- Spec Reference: AGENTS.md §9、.cursor/rules/release-workflow.mdc、DEC-039

### DEC-041: LINE新規承認で表示名を保存し、未取得の既存紐付けを補完する（2026-10-13）
- Status: Confirmed（ユーザーが前回登録者の「表示名なし」を指摘し、LINEで取得できる表示名を一覧へ反映するよう要請）
- Cause: コード紐付けではMessaging APIプロフィールを取得していたが、LINE新規登録の承認ではline_display_nameを保存していなかった。未取得を「表示名なし」と表示していた。
- Decision: 新規承認時に検証済みLINE主体のプロフィール表示名を保存する。既存紐付けはadmin/opsの認証済み更新APIから補完できる。保存済みLINE主体を宛先に使い、応答のuserIdを照合する。表示名をWorker.nameや本人識別の正本にせず、クライアント申告の名前で代用しない。
- Guard: 取得失敗は既存表示名を保持し、新規登録承認そのものは止めない。未取得は「未取得」と表示する。更新は取得後に稼働者と紐付けをロック・再読込し、解除/差し替えがあれば保存を拒否する。
- Minimal model/DDL: 既存line_worker_links.line_display_nameのみを利用。DB/model/DDL追加なし。既存情報補完と表示修正なので0.44.1から0.44.2へZを上げる（DEC-040）。
- Audit/Tests: line_profile_refreshedに紐付けID、実行者、Worker ID、取得・変更フラグを保存する。LINE ID・認証情報・表示名全文は監査へ複製しない。新規保存、既存補完、失敗時の保持、解除/差し替え拒否、権限、プロフィール応答主体照合、画面の未取得/取得成功/失敗を試験する。
- Spec Reference: DESIGN_SPEC_v0.3 §6.1・16、DEC-032/033/040。プロフィール取得の公式仕様: https://developers.line.biz/ja/docs/basics/user-profile/

### DEC-042: 日付別発注条件・運営スタッフ連絡先と所在地基盤（2026-10-13）
- Status: Partial Confirmed / Pending（勤務日別・期間別の時間・単価、費用込みの初期値、更新成功通知、運営スタッフ登録・LINE紐付けはユーザー指定。起床自動化の今回範囲、5ロールの権限、Google API設定と取得住所の保存方法は回答・確認待ち）
- Decision: 発注条件は既存request_conditionsのadditional-request-v1 JSONにschedule(version=1)を追加し、勤務/単価グループの不変ID、単日/期間、開始/終了・翌日、任意集合時間、備考、単価・単位、昼食/交通費込みと備考を保存する。連動時は勤務グループIDに単価を対応付ける。日付・時刻・金額の検証をサーバー側で行い、確定時に未入力と単価カバーを拒否する。既存自由文から条件を推測しない。旧文面は切替確認後も参考データとして保存する。給与/請求単価の正本へ転記しない。
- Minimal model/DDL: 依頼書は既存版Text/JSONを利用しDDL不要。VanzaiStaffにcan_drive、smoking_area_ok、緊急連絡先3項目、management_roles、profile_revisionを追加する。別のLineStaffLink/Codeを追加し、運営1人とLINE1主体の有効紐付けを部分ユニーク索引で担保する。migration 20261013c001。既存の報酬用role・linked_worker・金額設定を上書きしない。稼働者/ログインユーザーの自動生成なし。
- LINE Guard: OPS-付き一次コードを個別トークの署名付きWebhookで照合する。期限30分、平文不保存、再発行で旧コード失効、行ロック・LINE主体のadvisory lock・ユニーク制約、使用済み/無効/削除済みを拒否する。解除履歴を残し、友だち解除を反映する。運営の紐付けと稼働者の紐付けは本人確認を別々に行う。
- Pending roles: 5名称は暫定的に担当業務ラベルとして複数記録する。実際のログイン/操作権限の変更は実施しない。特に収益管理・基礎管理の操作範囲と複数権限の方針を質問済み。管理画面/APIは既存admin限定とする。回答後に権限設計を別途確定する。
- Location: 主催者が提供した住所をsite_addressと本文/PDFへ保存する。Google PlacesのPOI取得住所を永続保存せず、検索結果は参照表示、place_idだけ保存する。会場名変更で地点紐付けを解除する。公式APIのGOOGLE_MAPS_API_KEYはサーバー環境で利用する準備のみで、既存.envの閲覧・変更なし。API利用・課金設定、公開の利用規約等と取得住所の保存方式は確認待ち。起床ボタン・経路計算・期限判定・実リマインド/エスカレーションの自動ジョブは未追加。集合基準・準備余裕・取得失敗・取消停止・通知対象を次段階で確定する。
- Audit: operator_staff_created/updated、operator_line_code_issued/linked/revoked。ID・担当ロール・状態/版と解除理由を残し、連絡先・LINE ID・平文コードを複製しない。依頼書の既存確定/改訂監査・PDFスナップショットを継続する。
- Verification: 日付重複/逆転、夜跨ぎ、単価連動とカバー、別途費用備考、確定版保護、既存自由文、運営CRUD/競合/権限、署名・期限/再使用・友だち解除、Google未設定/失敗時の秘密不表示、成功/競合/再読込失敗時のポップアップとスマートフォン表示を試験する。
- Version: 運営スタッフ専用ページと日付別勤務条件は利用者向けの機能追加のためYを上げ、0.44.2から0.45.0とする。今回の更新成功通知単体はZ相当。前回の修正をYにした誤りの訂正（DEC-040）とは判定が異なる。
- Spec Reference: DESIGN_SPEC_v0.3 §6.1・7・16、AGENTS.md §9、DEC-040、ORDER_CONDITIONS_OPERATOR_STAFF_RUNBOOK.md。Google公式資料: https://developers.google.com/maps/documentation/places/web-service/policies 、 https://developers.google.com/maps/documentation/routes/transit-route

### DEC-043: Google Maps共有URLで会場を登録し、起床自動化と権限制御は次段階とする（2026-10-13）
- Status: Confirmed（ユーザーが今回の範囲を住所・LINE連携の準備まで、ロールは現在付与だけでよいと回答。所在地は検索してGoogleのアドレスを登録する案とAPI料金への懸念を提示）
- Decision: Googleのアドレスを共有URLと解釈し、その前提をユーザーへ明示してMaps URL方式を採用する。検索リンクでGoogle Mapsを開き、ユーザーが会場の共有リンクを登録する。APIキーや有料のAPI呼び出しは不要。URLをrequest_conditions.maps_urlと本文/PDFの確定版へ保存する。登録住所は主催者提供の住所を別途保存できる。共有リンクから住所や所要時間を自動取得する処理は追加しない。
- Guard: Google MapsのHTTPS URLをホストとパスで検証し、認証情報付き・非HTTPS・非Google/Mapsホスト・異常ポート・空白/逆スラッシュを拒否する。短縮URLはサーバーで開かない。会場変更で古い共有URL/地点IDを解除する。Maps URLの文字列を表示用チルダ変換で改変しない。
- Scope: 5ロールを付与・保存し、後々の表示項目・操作制御に使用する。今回は実権限の付与・ログインユーザー生成を行わない。起床報告・公共交通の移動時間・リマインド/運営エスカレーションは今回対象外と確定する。DEC-042のこれらの回答待ち状態を解消する。API検索は未設定時に表示せず、将来の所有者による設定時だけ使用できる準備を保持する。
- Minimal model/DDL: 依頼書の既存JSONのみ利用し、追加DDLなし。住所/共有URLの確定・改訂は既存版管理と監査を使う。新しい個人情報送信や通知の送付はなし。
- Verification: Googleの共有URLの保存・再読込・本文出力、改変しないURL、非Google・非HTTPS・偽ホストなどの拒否を試験する。URL登録はAPI未設定でも操作できること、単価/備考・運営登録の既存操作を画面試験する。
- Version: 0.45.0で追加した所在地登録方式をユーザー回答に合わせて変更するため、Zを上げて0.45.1とする。
- Sources: https://developers.google.com/maps/documentation/urls/get-started （Maps URLはAPIキー不要）、 https://developers.google.com/maps/billing-and-pricing/pricing （APIは月間無料枠と従量課金、2026-10-13確認）

### DEC-044: 発注依頼書の入力境界・二択操作・送付先選択の修正（2026-10-13）
- Status: Confirmed（ユーザー指定: ボタン/境界を明確に、勤務条件を稼働日の詳細へ、集合時間不要、二択をボタンへ、費用欄2列、送付先40人・商業Dなどで絞り込み）
- Decision: 日付別行を「稼働日の詳細 N」とし、既存の全体自由文は「稼働日の補足（全体）」として区別する。単日/期間および日給/時給は選択状態付きのボタンへ変更する。期間入力の表示切替で編集中の終了日を失わない。集合時間の新しい入力欄は撤去するが、旧gathering_timeと確定版は上書き/削除しない。旧項目が存在する場合のみ参考として展開できる。
- Overnight: 翌日指定は22時開始・翌朝6時終了など、日をまたぐ時間を区別するために必要。常時表示せず、終了が開始以下、または保存済み翌日指定の場合だけ説明付き確認を表示する。時刻の入力間違いを自動的に翌日扱いにせず、本人の明示指定を保存する。
- Layout: 日付別行/単価行を枠と背景で区別し、追加は緑の有色ボタン、削除は赤い枠と背景のボタンにする。昼食代/交通費は単価入力の次の行に2列で並べ、各備考も同じ2列の下に配置する。スマートフォンでもこの2列を保つ。
- Recipients: 上限40人をUI・保存・確定で統一する。商業Dなどは既存workers.tags/worker_tags定義（DEC-029）を正本とし、運営スタッフの5ロールと混同しない。登録済みタグの絞り込みと氏名/タグ表示名の検索を併用し、選択済みIDを保持する。候補は200件ずつ全ページ取得し、41人目の選択を止める。LINE送信は従来通り1送付行ごとで、勝手な追加送付や再送は行わない。
- Minimal model/DDL: 既存schedule JSON、workers.tags、MAX_RECIPIENTSのみ利用し、DB/DDL変更なし。既存の確定・改訂・送付監査を継続し、表示の変更だけで新たな業務監査イベントを作らない。
- Verification: 単日/期間切替と期間保持、翌日確認、集合入力の不存在、費用備考の横並び、氏名/タグ絞り込みと選択保持、200件以降の候補、40人保存/確定・41人拒否を検証する。既存依頼書とLINE経路、画面をテストし、両アプリをビルドする。
- Memory/Version: 二択はボタン、境界と操作を明確にする方針をAGENTS.md §12へ記録する。既存登録画面と選択操作の修正・変更としてZを上げ、0.45.1から0.45.2とする。
- Spec Reference: DESIGN_SPEC_v0.3 §3・6.1・16、DEC-029/040/042/043、AGENTS.md §9/12。

### DEC-045: 発注依頼書の半幅入力・日給統一・ロール複数選択（2026-10-13）
- Status: Confirmed（ユーザー指定: 稼働場所と稼働日の補足を案件名と同じ半幅、時給削除、すべての付与ロールから複数選択）
- Decision: 稼働場所/稼働日の補足を12列中6列へ変更する。新規単価の単位は日給のみで選択操作をなくす。保存済みの旧時給は表示・保存時に保持し、金額を読み取り専用とする。本人が確認して日給へ変更した場合のみunit=day、amount空欄にし、新しい日給額の入力を求める。時給から日給の推測換算や確定版/給与マスタの書換えは行わない。
- Recipients: workers.tagsの定義済み全ロールを複数のチェックボックスで表示する。複数選択時はOR（いずれかのロールを持つ人）とする前提を作業開始時にユーザーへ明示した。無選択は全員、氏名/ロール名検索はAND。候補のフィルタ変更で選択済み送付先は解除しない。送付上限40人は継続する。
- Minimal model/DDL: 既存schedule JSON・workers.tagsとフロントの選択状態だけで実装し、追加DB/DDLなし。旧hour値の読込と版管理の互換性を保持する。監査は既存下書き保存/確定/改訂を使用し、表示操作だけで業務監査を増やさない。
- Verification: 半幅と案件名の同幅、日給のみの新規入力・保存、旧時給保持/変更キャンセル/日給変更後の再入力、複数ロールのOR・氏名併用・送付先保持・全解除、200人以降の候補、40人制限を画面試験する。両アプリをビルドする。
- Version: 既存入力画面と絞り込み操作の修正としてZを上げ、0.45.2から0.45.3とする。
- Spec Reference: DESIGN_SPEC_v0.3 §3・6.1・16、DEC-029/044、AGENTS.md §9/12。

### DEC-046: イベントDの規模包含・全体稼働期間・共同管理（2026-10-14）
- Status: Confirmed（ユーザー指定とMapsの手入力維持の回答）
- Decision: イベントDは担当可能な最大規模。小型のフィルタは小型/中型/大型、中型は中型/大型、大型は大型を許容する。複数選択のORと他のロールの完全一致は維持。登録済みタグを増やす移行や書換えは不要。フィルタ注釈と定義の説明へ包含関係を記録する。
- Period: 初日/最終日の「稼働日」を全体補足の隣に復活し、詳細は「稼働時間の詳細」とする。既存request_conditions JSONへoptional work_period={from,to}を追加する。詳細編集で全体期間を変えない。下書きは片方未入力を許容し、確定時は両方必須。逆転/不正日付/全体期間外の稼働詳細をAPIで拒否する。休業日や予備日を含む期間を許容し、毎日の勤務を推測して生成しない。旧work_periodなしは従来の処理と確定版を保持し、入力時だけ明示期間を採用する。
- Ownership: 個別の追跡担当チェックと一覧欄を撤去。作成者と管理ロールが送付/回答を確認する運用とする。UI保存でassign_tracker_self/tracker_user_idを送信しないため、過去の担当者を編集者へ自動付替えしない。旧DBの担当情報は履歴として保持し、現行のadmin/opsアクセス権と運営5ロールの将来制御（DEC-043）は変更しない。
- Maps: 今回は住所/施設名を手入力のまま維持する（ユーザー回答）。API課金やキー設定は行わない。料金・設定・保存条件はGOOGLE_MAPS_API_SETUP_AND_COSTS.mdへGoogle公式資料を根拠に記録する。
- Minimal model/DDL: 既存のJSON/worker tags/UIで対応し、新規DB/DDLなし。確定時はwork_periodと本文を既存スナップショットに保存し、改訂版へ引き継ぐ。旧確定スナップショットを上書きしない。監査は既存下書き保存/確定/改訂の出力点を継続する。
- Verification: 階層の小型/中型/大型と複数ロールOR、注釈、全体期間と補足の横並び、詳細編集時の期間保持、追跡フィールド送信停止、期間の保存/確定/改訂と元版固定、逆転/期間外/未完成の確定拒否、旧JSON/LINE経路をテストする。
- Version: 既存の検索意味・入力画面・保存処理の修正としてZを上げ、0.45.3から0.45.4へ。
- Spec Reference: DESIGN_SPEC_v0.3 §3・5・6.1・16、DEC-029/043/044/045、AGENTS.md §9/12。

### DEC-047: マスタ追加ポップアップとクライアント連絡先・内部発注元（2026-10-14）
- Status: Confirmed（ユーザー指定: 一覧優先/新規追加ポップアップ、会社電話・複数担当者電話、切替の縁色、クライアント/担当者の連動選択、内部情報をPDFに含めない）
- Masters: 全7種の一覧から常設の追加フォームを撤去し、共通ProfileDialogで新規追加と既存編集を行う。入力項目/権限は従来を保持する。切替の縁を7色にし、選択状態を下線・強調・aria-pressedでも示す。
- Clients: 会社のphoneを追加し、担当者は既存client_staffを正本にする。クライアント新規追加では複数担当者を同じDBトランザクションで作成する。既存会社電話の編集はphone専用PATCHとする。旧contact_name/contact_emailは削除せず、同名担当者がいなければ追加移行する。既存担当者の電話などは上書きしない。担当者一覧のpage/offset不整合をoffset/limitへ修正する。
- Internal source: OrderRequestVersionにinternal_client_id/client_staff_id（FK）とinternal_source_snapshot（JSON）を追加する。選択の所属関係・有効/未削除をAPIで検証する。会社変更で担当者選択を解除する。選択済みの同じ参照は確認済みスナップショットを保持し、改訂/変更へコピーする。別の参照へ変えた場合は現行マスタから取得し直す。内部項目の確定後変更は拒否する。
- Privacy: 内部情報をrequest_conditions/body/公開snapshot_jsonに入れない。PDF/LINEの生成引数と稼働者向け経路に渡さない。管理画面のadmin/ops APIだけが返す。既存のcontact_nameは運営側の連絡担当者（公開帳票用）であり、内部のクライアント担当者を自動転記しない。UIで名称を明確にする。電話は業務監査の値へ複製しない。
- Minimal model/DDL: clients.phone、依頼版の2FK/内部JSON、担当者選択には会社選択が必要というCHECKを20261014a001で追加する。既存client_staffテーブルを再利用する。旧本文・確定スナップショット・金額は移行で変えない。
- Audit: client_created/client_staff_created、client_updated（電話フィールド名のみ）、client_staff_updated（フィールド名と所属ID）、order_request_internal_source_updated（参照IDと実行者）を出力する。既存確定/改訂の監査も継続する。
- Verification: 全7一覧の入力非表示/ポップアップ/縁色、複数担当者電話の一括保存、既存電話の編集、発注元/担当者の連動と解除、内部情報の公開本文/PDF生成/LINE非表示、所属検証・権限・確定後固定・改訂引継ぎ、旧データを保持する移行を検証する。
- Version: 当初、会社電話と内部発注元連携を新機能と誤分類し0.46.0で公開した。この判断はユーザー指摘により撤回。既存機能の項目追加・変更として0.45.5が正しい（DEC-049が優先）。
- Spec Reference: DESIGN_SPEC_v0.3 §3・5・6.1・16、AGENTS.md §9/11/12。

### DEC-048: マスタポップアップの入力スタイルを適用（2026-10-14）
- Status: Confirmed（同じユーザー依頼の本番見た目確認で、移動した入力にページ内スタイルが届かないことを検出）
- Decision: 追加・編集・クライアント管理の各ポップアップにmaster-formを付け、入力欄の枠/余白/幅/高さと暗色テーマを適用する。担当者追加ボタンの配色・操作サイズを明確にする。値・API・DBは変えない。
- Verification: 全7マスタのポップアップで名称入力の高さ44px以上・ラベル枠内の幅を確認し、既存の画面19件と両アプリのビルドを行う。
- Version: 当時は誤った基準番号を引き継いで0.46.1で公開した。訂正後は0.45.5から0.45.6とする（DEC-049が優先）。
- Spec Reference: AGENTS.md §9/12、DEC-047。

### DEC-049: 項目追加を新機能と誤分類した版番号の訂正・再発防止（2026-10-14）
- Status: Confirmed（ユーザーが今回の変更は既存機能の修正と項目追加でありYの増加は誤りと指摘し、作業ルール・CHANGELOGを含む訂正を指示）
- Decision: 会社電話番号、既存の複数担当者管理の入力方法、発注元/担当者の連動選択はZ。新しいAPI・DB列や実装量を理由にYへ分類しない。Yは利用者が新しく独立して行える業務・機能を具体的に説明できる場合に限る。AGENTS.md §9とリリースルールへ今回の具体例を記録する。
- Correction: 0.45.4に続くマスタ/項目変更は0.45.5、続くポップアップ表示修正は0.45.6。旧公開番号0.46.0/0.46.1の誤りと対応をCHANGELOGへ残し、見出し・両package.json・運用資料を訂正する。DEC-047/048の版判断を置き換える。今回の訂正は新しい業務変更ではなく版の是正なので0.45.7は発行しない。
- Guard: アプリの機能・データ・DB移行・確定版は変更しない。Git履歴を改変せず、訂正コミットを追加して通常のデプロイスクリプトで反映する。共有作業ディレクトリのAGENTS.mdとリリースルールにもこの判断だけを追記し、既存の未コミット変更を保持する。
- Verification: 両アプリをビルドし、埋込/公開バージョンが0.45.6で一致すること、CHANGELOGの訂正対応とルール、APIの稼働を確認する。業務ロジック未変更のため業務テストを再実行/新設しない。
- Spec Reference: AGENTS.md §9/11、DEC-047/048、.cursor/rules/release-workflow.mdc。


### DEC-050: 稼働者の最寄り駅を任意で複数登録する（2026-10-15）
- Status: Confirmed（ユーザーが2駅以上の任意登録を指示。駅ごとの徒歩時間は既存項目との整合を優先する実装方針）
- Purpose: 複数の駅を利用できる稼働者のアクセス情報を、別項目や備考へ分散せず登録・参照できるようにする。
- Decision: 管理画面の稼働者登録・編集とLINE登録で「最寄り駅を追加」を用意する。1駅目は既存列、2駅目以降は `workers.additional_stations` のJSON配列とする。駅名は100文字以内、徒歩分数は0〜300の整数または未入力。追加した完全空欄の行は送らず、徒歩だけ入力した追加行はエラーにする。駅数を2に固定しない。
- Compatibility: 既存の1駅目と徒歩分数は移行で書き換えない。追加列はnullable。旧クライアントの未送信・nullは既存の追加駅を保持し、空配列を明示した場合のみ追加駅を消す。1駅目の必須条件は既存ルールを維持する。
- LINE: `worker_registration_request_details.additional_stations` に申請値を保存する。既存の文字列フォーム・差分送信と再認証時の入力保持に合わせ、LINEのAPI入力/画面比較値はJSON文字列、正規化・DBは配列とする。未送信では従来の内容ハッシュを維持し、追加・削除は再送内容の同一性判定に含める。承認前に稼働者へ反映しない。
- Guard/Audit: 追加駅を通常編集・LINE承認・本人用フォームの比較票に含める。`worker_created` / `worker_updated` のprofile、LINE承認のbefore/afterへ保存する。通常更新ではprofileの変更前も記録する。
- Migration: `20261015a001_worker_additional_stations.py`。workersと申請詳細へJSON列を1つずつ追加するだけとし、既存レコード・列を変更しない。
- Verification: 複数駅の保存/再表示、旧データ読取、未送信保持、明示削除、入力制約、申請・承認・再送、追加駅のみの同時変更拒否、移行の旧行保持、モバイルでの追加/削除/確認/送信、締め・再計算の既存テスト、両アプリのビルド。
- Version: 既存の稼働者登録項目の拡張なのでZ。0.45.6 → 0.45.7。
- Spec Reference: DESIGN_SPEC_v0.3 §6.1、AGENTS.md §9/11/12、DEC-049。


### DEC-051: クライアント登録の役職・郵便番号・社内メモ（2026-10-20）
- Status: Confirmed（ユーザー指定）
- Purpose: クライアントの担当者情報・社内情報を揃え、住所入力と追加操作の負担を減らす。
- Decision: 役職は既存の `client_staff.role` に担当者単位で保存し、会社の社内メモは既存の `clients.notes` を使う。いずれも任意。郵便番号はnullableな7桁の `clients.postal_code` を追加し、既存のZipCloud補完を使う。複数候補は選択し、手入力済み住所は自動上書きしない。番地・建物名は手入力。
- Migration: `20261020a001_client_postal_code.py`。既存住所・レコードを書き換えない。金額・時間・締めには影響しない。
- Audit: 既存 `client_created` に郵便番号・メモを含める。役職は既存 `client_staff_created` / `client_staff_updated` の経路で保存する。
- Version: 既存登録画面の項目・表示変更なのでZ。0.45.7 → 0.45.8。
- Spec Reference: DESIGN_SPEC_v0.3 §6.1、§16、AGENTS.md §9/11/12。


### DEC-052: クライアント一覧から企業情報を編集する（2026-10-20）
- Status: Confirmed（ユーザー指定）
- Purpose: 登録済みの企業情報を一覧から修正できるようにする。
- Decision: クライアント一覧の各行に管理者向けの「編集」を追加し、企業名・コード・会社電話番号・郵便番号・住所・社内メモを編集する。担当者は既存の「担当者管理」で氏名・役職・電話・メールを修正する。
- Model/Migration: 既存のclients列のみを使い、DB変更なし。変更項目のみPATCHで送る。未送信列・担当者・過去の帳票スナップショットを変更しない。
- Guard/Audit: MASTER_WRITEをAPIで検証し、削除済み企業の更新・空の企業名・不正郵便番号・コード重複を拒否する。client_updatedに変更項目のbefore/afterと実行者を保存する。
- UI: 保存後は編集画面に成功表示を出し、クライアント一覧・案件選択・発注元選択を再取得する。住所補完は初期表示では実行せず、郵便番号を変更した場合に取得する。既存住所は明示的な候補選択で置き換え、番地・建物名を確認する。
- Version: 既存マスタの修正導線なのでZ。0.45.8 → 0.45.9。
- Spec Reference: DESIGN_SPEC_v0.3 §3/5/6.1/11/16、DEC-051。

### DEC-053: 確定帳票の実績は強制指定でも再計算しない（2026-10-20）
- Status: Confirmed（DESIGN_SPEC_v0.3 §6.3/7.4の不変条件への復帰）
- Purpose: 発行済み請求・承認済み支払と、保存実績・再計算プレビューの不一致を防ぐ。
- Decision: force引数は呼び出し互換のため保持するが、発行済み・closed請求、approved/paid/closed支払に含まれる実績は再計算しない。変更は既存の訂正・再発行手順で扱う。プレビューも同じ実績を対象件数・差額から除外する。
- Reason: 従来のforce=True処理とテスト期待値は、正本仕様の確定実績除外に反していた。単なる呼び出しフラグを会計確定の解除権限として扱わない。
- Model/Migration: 既存モデルを使用。DDL変更なし。過去の実績・帳票は一括更新しない。
- Concurrency/Audit: 帳票・締めと共通の案件ロックを取得後に実績を読み直す。既存の再計算監査にforce_requestedと処理・除外件数、差額を記録する。
- Tests: 発行済み/closed請求、approved/paid/closed支払の5条件で、force指定時の実績・金額保持とプレビュー除外を検証。旧forceテストを仕様に整合させる。
- Version: 既存処理の修正としてZ（0.45.9 → 0.45.10）。
- Spec Reference: DESIGN_SPEC_v0.3 §3/6.3/7.4/11/12/16、docs/ops/CODE_REVIEW_2026-10-20.md。


### DEC-054: クライアントの企業情報と担当者を一画面・一保存に統合する（2026-10-20）
- Status: Confirmed（ユーザーが入口分割の撤回・統合を指定。DEC-052の担当者別入口を置き換える）
- Purpose: 企業情報と担当者の修正に必要な操作・判断を減らす。
- Decision: 一覧から管理者は「編集」、参照者は「詳細」の一つの入口で企業情報と担当者を開く。全担当者は氏名・役職・電話・メールの入力欄で直接修正でき、追加行も同じ画面に出す。最後の「保存する」で企業情報・担当者変更・担当者追加を同時に確定する。担当者ごとの編集・保存や会社電話だけの保存ボタンは表示しない。
- Model/Migration: 既存のclients/client_staff列を使用し、DB変更なし。企業PATCHに変更した担当者IDと項目・新規担当者を含め、所属・存在・重複IDを検証後に同一トランザクションで保存する。未送信担当者を削除せず、既存の有効状態・メモ・IDを保持する。削除できるのは未保存の追加行だけ。
- Compatibility: 旧APIは互換維持。旧代表担当者名と一意に一致する既存担当者の改名・メール変更はclients.contact_name/contact_emailにも同期する。担当者行のない旧データは既存の担当者名・メールを入力行として提示し、保存時に担当者行へ移す。旧代表名が複数行と一致する場合は推測して代表を切り替えない。
- Guard/Audit: MASTER_WRITEをAPIで検証。読み込み完了前や失敗中は保存不可。入力・所属検証の失敗時は企業情報も保存しない。client_updated/client_staff_updatedに変更前後、client_staff_createdに追加内容と実行者を記録する。
- Version: 既存マスタの編集画面の統合なのでZ。0.45.10 → 0.45.11。
- Spec Reference: DESIGN_SPEC_v0.3 §3/5/6.1/16、DEC-051/052。


### DEC-055: 複数担当者の一覧表示と郵便番号・住所入力の統一（2026-10-20）
- Status: Confirmed（ユーザー指摘への修正）
- Purpose: 編集画面を開かなくても登録した全担当者を確認でき、新規・編集のどちらでも郵便番号による住所補完を見つけられるようにする。
- Decision: クライアント一覧APIにページ内企業の全担当者をまとめて取得したcontacts配列を追加する。一覧の「担当者・連絡先」に氏名・役職・電話・メールを担当者単位で表示する。削除済みは除外し、無効な担当者は「無効」を表示する。担当者行のない旧データは既存contact_name/contact_emailを表示する。
- UI: 新規登録・編集で同じ住所入力コンポーネントを使い、見出し「住所情報」の中に郵便番号・補完案内・住所を続けて配置する。既存の補完、全角・ハイフン正規化、番地の手入力、入力済み住所の保護は維持する。
- Model/Migration: 既存clients/client_staffを読むだけでDB変更なし。企業件数・ページ分割を変えず、担当者はページ内企業IDで一括取得する。
- Audit: 読み取り・表示の変更なので新規の監査イベントなし。編集時の既存client_updated/client_staff_updated/client_staff_createdを維持する。
- Version: 既存一覧・住所入力の修正としてZ。0.45.11 → 0.45.12。
- Spec Reference: DESIGN_SPEC_v0.3 §5/6.1/16、DEC-051/054。


### DEC-056: 管理者によるログインID・役割別権限の管理（2026-10-20）
- Status: Confirmed（ユーザー指定）
- Purpose: IDごとに役割を割り当て、閲覧範囲を管理者自身で変更できるようにする。
- Decision: admin/ops/accounting/site_managerの4役割を使う。現場管理者は担当に関係なく全案件を閲覧でき、請求・支払・単価は初期設定で非表示。CSV提出は従来の担当案件制限を維持する。
- IDの作成・役割の付与/変更・無効化と役割別の閲覧/操作権限セットの変更はadminだけに許可する。同じ役割の全IDに適用し、個人別例外と役割の自由追加は対象外。
- Guard: adminは全権限固定、自分自身の降格/無効化を拒否。ID変更時に実行者と対象を固定順でロックし、変更後の実行者権限を再確認する。画面/直接URL/APIを制御し、現行トークンでも次回リクエストから新権限を適用する。画面は30秒ごと/再フォーカスで同期する。
- Model/Migration: usersを保持し、role_access_policies（role主キー、permissions JSON、タイムスタンプ）だけ追加。既存ID・パスワードを書き換えない。
- APIの金額漏えい対策: 売上/外注費集計に認証を追加。権限のないダッシュボード集計項目、実績/配置一覧の単価は返さず、銀行口座APIを支払閲覧権限で保護する。
- Audit: USER_CREATED、USER_ACCESS_CHANGED、ROLE_PERMISSIONS_CHANGED。理由と変更前後を残し、パスワードを記録しない。
- Validation: tests/test_access_management.py、認証/案件/配置/実績/シフト/ダッシュボード等の回帰、管理者と現場管理者のブラウザテスト。
- Version: IDの作成・役割付与・役割別権限設定という独立した管理業務を追加するためY（0.45.12 → 0.46.0）。既存画面の項目追加を理由としたY判定ではない。
- Spec Reference: DESIGN_SPEC_v0.3 §5/16、RUNBOOK: docs/ops/ACCESS_MANAGEMENT_RUNBOOK.md。

### DEC-057: 独自役割の作成と作成・編集フォームのポップアップ統一（2026-10-20）
- Status: Confirmed（ユーザー指定。DEC-056の「役割の自由追加は対象外」を変更）
- Purpose: 管理者が業務に合う役割を設定でき、作成欄が一覧を占有しない操作方法へ統一する。
- Decision: 全体管理者だけが独自役割の名前・権限・理由を指定して作成する。役割識別子はシステム発行、初期権限はなし。新しい役割はID作成・付与時の選択肢に追加し、表示名を画面に表示する。
- Guard: 標準役割名・予約名・重複名は拒否する。独自役割に全業務権限を付けてもID・役割管理はadminだけに限定し、adminの固定権限と自己降格/無効化の禁止を維持する。workerの本人範囲とCSV提出の担当範囲を変更しない。
- Model/Migration: role_access_policiesにdisplay_name（100文字・一意・既存標準役割はNULL）を追加する。users.roleは既存の文字列列を使用し、既存ID・パスワード・役割を書き換えない。標準役割と独自役割を権限解決で扱い、未定義の役割は権限なしとする。
- UI: ID作成/変更・役割作成/権限変更、案件/シフト枠/配置の作成/編集、請求/支払生成、単価、通知、登録リンクと配置の選択/一括変更はボタンからポップアップで開く。既存の稼働者・運営スタッフ・マスタ・発注依頼書のポップアップを維持する。検索フィルタは一覧上に残す。Esc/閉じるとフォーカス復帰、送信中の閉じる防止を共通化する。
- Audit: ROLE_CREATEDに役割名・識別子・権限・理由・実行者を保存し、USER_CREATED/USER_ACCESS_CHANGED/ROLE_PERMISSIONS_CHANGEDも維持する。
- Validation: 独自役割の作成・重複/予約名拒否・IDへの付与・ログイン・画面/API拒否、既存ロールの回帰、一覧上にフォームが常設されないことと各ポップアップのブラウザ操作を検証する。
- Version: 既存のID・権限管理と入力方法の拡張・変更なのでZ（0.46.0 → 0.46.1）。API/DB追加を理由にYとはしない。
- Spec Reference: DESIGN_SPEC_v0.3 §5.1/5.2/16、AGENTS.md §12、docs/ops/ACCESS_MANAGEMENT_RUNBOOK.md。

### DEC-058: 作成ボタンのブルー統一（2026-10-20）
- Status: Confirmed（ユーザー指定）
- Purpose: 表示切替と新規作成の操作を色で判別できるようにする。
- Decision: 作成・新規登録・生成の入口とポップアップ内の作成確定に共通のcreate-buttonを適用し、背景をブルー（#2563eb、ホバー#1d4ed8）、文字を白に統一する。表示切替と既存データの更新は既存の色を維持する。今回の変更は配置を変えない。
- Model/Migration/Audit: 表示スタイルだけの変更のためDB変更・新規監査イベントなし。既存の作成処理と監査を維持する。
- Validation: 管理画面ビルド、作成ポップアップの既存ブラウザ回帰、表示切替と作成ボタンの実際の色・フォーカス・ダークモードを確認する。
- Version: 既存画面の表示改善なのでZ（0.46.1 → 0.46.2）。
- Spec Reference: DESIGN_SPEC_v0.3 §5.1/5.2、AGENTS.md §12。

### DEC-059: 管理者による役割の名称変更（2026-10-21）
- Status: Confirmed（役割の名称変更というユーザー指定を反映）
- Purpose: 役割を作り直したりIDを付け替えたりせず、業務に合った名称へ変更できるようにする。
- Decision: 管理者が役割一覧の「名称を変更」から専用ポップアップで名称・理由を保存する。対象は管理画面の標準役割（adminを含む）と独自役割。workerは従来どおり対象外。表示名だけを変え、役割識別子・ID割り当て・権限は維持する。全体管理者の固定権限も維持する。
- Guard: 空白名・100文字超・重複名・内部の予約識別子・他の標準役割の既定名称は拒否する。重複時は入力を保持する。同一名称での再保存は監査を増やさない。
- Model/Migration: 既存role_access_policies.display_nameと一意制約を再利用するためDDL変更なし。標準役割の行を初めて保存するときは現在の既定権限を保持する。既存行は表示名だけを更新する。
- Audit: ROLE_NAME_CHANGEDに変更前後の名称・理由・実行者・役割識別子を記録する。
- Validation: 標準4役割と独自役割の名称変更、既存トークンとID一覧への反映、権限不変・管理者固定権限、重複/予約名/未認可の拒否、ポップアップ操作と重複エラー時の入力保持を検証する。
- Version: 既存の役割管理の変更なのでZ（0.46.2 → 0.46.3）。
- Spec Reference: DESIGN_SPEC_v0.3 §5.1/5.2/16、docs/ops/ACCESS_MANAGEMENT_RUNBOOK.md。

### DEC-060: 役割名変更の理由入力廃止とフォーム余白の縮小（2026-10-21）
- Status: Confirmed（ユーザー指定。DEC-059の名称変更時の理由必須を変更）
- Purpose: 少数項目の変更で不要な入力や大きな空白を発生させず、名称だけですぐ保存できるようにする。
- Decision: 名称変更画面から理由欄を削除し、APIの理由も任意にする。変更前後の名称・実行者・日時は既存のROLE_NAME_CHANGEDへ自動記録し、未入力の理由はNULLとする。権限変更など他の操作の理由入力は維持する。
- UI: 共通FormDialogは内容に合わせた高さへ変更し、画面高さに合わせたグリッドの引き伸ばしを解消する。長いフォームの高さ上限・内部スクロールは維持する。名称変更のみ幅560px以下のコンパクト表示とし、スマートフォンでも枠内に収める。
- Model/Migration: 既存モデル・NULL可の監査理由を使用するためDB変更なし。
- Validation: 理由を省略した標準・独自役割の名称保存と監査、権限保持、PC/スマートフォンのポップアップサイズと保存、重複エラー時の入力保持、既存フォームの回帰。
- Version: 既存入力画面の改善なのでZ（0.46.3 → 0.46.4）。
- Spec Reference: DESIGN_SPEC_v0.3 §5.1/5.2/16、AGENTS.md §12。

### DEC-061: 監査履歴の日本語表示（2026-10-21）
- Status: Confirmed（ユーザー指定）
- Purpose: 操作コードを知らなくても監査内容を把握できるようにする。
- Decision: 操作名・対象種別・詳細要約の項目名を日本語辞書で表示し、既存履歴にも適用する。大文字の権限操作コードも対応する。検索には元のコードを使用し、未知のコードは情報を隠さず原文を表示する。
- Model/Migration/Audit: 既存audit_logを利用し、DDL・新規監査イベント・既存記録の書換えなし。実行者IDや自由記述は翻訳しない。監査検索・関連業務の識別子互換性を保つ。
- Validation: 画像で指摘された操作・対象種別、全AuditActionと静的な監査記録箇所の日本語対応、未知コード維持、管理・スタッフ画面ビルドを確認する。
- Version: 既存監査画面の改善なのでZ（0.46.5 → 0.46.6）。
- Spec Reference: DESIGN_SPEC_v0.3 §3/16。

### DEC-062: 発注依頼書の任意の集合場所（2026-10-21）
- Status: Confirmed（ユーザー指定）
- Purpose: 稼働場所と集合場所が異なる場合にも、依頼書の専用欄で案内できるようにする。
- Decision: 既存の作成・編集ポップアップの稼働場所の下に「集合場所（任意）」を複数行の自由入力欄として追加する。入力時は本文・PDFの稼働場所の次に独立した「集合場所」を表示し、空欄の場合は帳票の項目を省略する。
- Model/Migration: 既存order_request_versions.request_conditionsのJSONにmeeting_placeを保存し、bodyと確定時snapshot_jsonへ反映する。旧データの項目欠落は空欄として読み込み、DDL・マイグレーション・既存データの書換えは不要。
- Guard/Audit: 確定済み本文・PDFの編集拒否と変更版作成を維持する。既存ORDER_REQUEST_CONFIRMED / ORDER_REQUEST_REVISED監査を利用し、新規イベントは追加しない。
- Validation: 旧データからの追加、複数行保存・再取得・空欄への変更、任意のままの確定、PDF用項目解析、スナップショット保存、確定後編集拒否とPDF不変を検証する。
- Version: 既存依頼書への項目追加なのでZ（0.46.6 → 0.46.7）。
- Spec Reference: DESIGN_SPEC_v0.3 §3/5.2/6/16、AGENTS.md §12。

### DEC-063: 稼働者向け予定の正本を発注依頼書由来の稼働予定に統一する（2026-10-22）
- Status: Confirmed（ユーザー回答 2026-10-21〜22）／A1実装済み（0.47.0）。計画書 `docs/ops/LINE_WORKER_DAILY_OPERATIONS_PLAN_2026-10-21.md`（v0.9）§5・§7.1〜7.5、レビュー `LINE_WORKER_DAILY_OPERATIONS_REVIEW*_2026-10-21.md`
- Purpose: 運用開始前に、予定の入力起点を発注依頼書へ一本化し、案件登録と依頼書の二重入力・予定の二重管理をなくす。
- Decision: 発注依頼書をすべての予定の起点とする。依頼書を作らない限り、予定・起床監視に載らない。正式区分（formal）で確定した版を本人が受諾したときに、新設の稼働予定（worker_schedule_entries）を作る。test区分は対象外（2026-10-22補記：test区分でも、動作確認のために is_test の印を付けた稼働予定を作る。本人のLINEには「【テスト】」付きで表示し、運営の起床状況一覧・起床の監視・案件と請求の生成からは除外する。ユーザー回答）。稼働予定は依頼書からの派生データで直接編集を禁止し、訂正は修正版の依頼書（確定と受諾）で行う。勤務日はschedule.work_groupsだけから展開し、work_periodからは作らない（DEC-046と整合）。運用開始前のため、遡及生成・移行はしない。
- Versions/Cancel: 確定・送付した依頼書の「取消」は発注そのものの中止とし、修正は修正版の発行で行う（ユーザー確定）。依頼書ごとに回答受付版を1つ持ち、取消で旧版へ自動で戻さない。新版確定時、旧版で受諾済みの人の予定は「変更確認中」として旧い内容を表示し続け、新版の受諾で切り替える（ユーザー確定）。受諾後の辞退は本人から運営へ連絡し、運営が理由付きで記録する（ユーザー確定）。旧版のボタンによる返答は拒否する。操作ごとの影響と具体例E1〜E7は計画書§7.4。
- Accounting boundary: 稼働予定は金額を持たない。現行の支払・請求は単価×時間（payout_service.py / invoice_service.py）で日給の計上単位がないため、依頼書からの案件・シフト枠・アサイン生成（B2）と出勤・退勤からの実績作成（B3）は、日給の計上モデル（B1）の決定後に着手する。DEC-042の「依頼書の単価を給与・請求単価の正本へ転記しない」はTrack Aでは変更しない。DESIGN_SPEC §4の予定（planned）＝アサインという会計用の集計は、B2まで変更しない。
- Supersedes: `LINE_INTEGRATION_IMPLEMENTATION_PLAN_2026-09-30.md` のうち、集合時刻をgathering_timeで持つ方針（DEC-044と本DECにより開始時刻＝集合時刻）、移動時間を自宅住所→現場住所で求める方針（最寄り駅↔最寄り駅へ変更）、起床対象を集合9時前に限る方針（DEC-066へ）、遅刻を責任者修正→承認で反映する方針（現場リーダーから運営へ直接報告。システム機能は作らない）、案件を先に登録してから依頼書を作る運用。打刻と実績の関係（9/30計画P01）とGPS判定はB3の前に別途決定する。
- Guard: 同じ依頼書の確定・受諾・辞退・取消は依頼書単位のロックで直列化し、ロック後に回答受付版と状態を読み直す。Webhookはイベントごとのトランザクションで、commit後に返信する。イベントIDの一意制約違反だけを処理済みとし、それ以外の制約違反は握り潰さない。個別トーク（source.type=user）以外は処理しない。staff-mobileの予定画面（アサインを読む）は、稼働者向けに公開しない（導線と直接URL）。
- Correction paths（2026-10-22補記）: 稼働予定の訂正経路は2つだけとする。依頼書の共通の条件（勤務日・時刻・場所・共通の除外日など）は修正版の確定と受諾で、特定の人の参加日はDEC-065の本人申請を運営が承認した記録で変更する。後者は修正版を要しない。どちらも稼働予定を直接書き換えない。
- Model/Migration（予定）: worker_schedule_entries、order_request_documents.answerable_version_id、送付行の提示日、追記型の参加日の状態 ほか。計画書§9。DDLは詳細設計で確定する。
- Audit: 稼働予定の生成・状態変更、受諾後の辞退の記録。LINEユーザーIDは複製しない。
- Implementation（2026-10-22、0.47.0）: 稼働予定（worker_schedule_entries）、追記型の参加日の状態、適用送付行、回答受付版を migration 20261022a002 で追加し、確定・受諾・辞退・取消・受諾後の辞退の記録のたびに（系列 × 稼働者）の稼働予定を元データだけから作り直す。**回答受付版とロックは「依頼書」ではなく「系列」単位**とした：「変更を作成」で作った依頼書は元の依頼書と同じ系列に入り、新しい依頼書の確定で元の依頼書の予定は「変更確認中」、新しい依頼書の受諾で切り替わる（2026-10-22 ユーザー指示「推奨のものを反映」。詳細設計 §4.4）。上の Versions/Cancel・Guard の「依頼書ごと／依頼書単位」は系列単位と読み替える。既存データは依頼書ごとに系列を作り、A1以前の「変更を作成」は別系列のまま。
- Version: 起床報告・予定確認とあわせ、独立した新しい業務の提供としてY（A1）。
- Spec Reference: AGENTS.md §2/§9、DESIGN_SPEC_v0.3 §4/§6、DEC-027/028/037/042/044/046/053/062/065。

### DEC-064: 公式LINEのリッチメニュー6パネルと、A1で公開する日次操作（2026-10-22）
- Status: Confirmed（ユーザー回答）／A1実装済み（0.47.0。リッチメニューの適用は画像の受領後）。計画書§7.6〜7.9
- Decision: リッチメニューは全員共通の6パネル：①起床報告 ②出勤報告 ③退勤報告 ④販売報告 ⑤受託済みの発注依頼書 ⑥スケジュール確認。運用前のパネルは押せない状態にする（ボタン領域を定義しない）。画像は運営が公開段階ごとに用意し、画像と領域の定義をまとめて差し替える。メニューを全員に適用するのはA1の公開時とし、A1では①⑤⑥を有効にする。古いメニューから有効でない機能のポストバックが届いた場合は「まだご利用いただけません」と返す。
- ①起床報告: 本人の当日の予定（案件名・時刻・稼働場所・集合場所）を添えた挨拶を返し、（稼働者, 報告日）で記録する。報告日はLINEイベント発生時刻の日本時間の日付。二重押しは「報告済みです（HH:MM）」。予定なしの日も報告は記録する。
- ⑥スケジュール確認: 本人の有効・変更確認中の予定を今日から7日分、トーク内で返す。超過分は短命トークンによる「続きを見る」。
- ⑤受託済みの発注依頼書: 受諾した適用版の依頼書を一覧で返し、本人確認後に新しい期限付きPDFトークンを発行して開かせる（既存の受諾・送信状態は変えない）。本人が送付先の現在の回答受付版は、未受諾でも開ける。
- 未連携・連携解除・無効・削除済みの稼働者には「連携が確認できません。運営までお問い合わせください」と返す。
- Ops: 運営向けに当日の起床状況一覧を設ける。閲覧は新しい権限として、DEC-056/057の権限セットに追加する。
- Spec Reference: DEC-063、DEC-027/028、DEC-056/057。
- Implementation（2026-10-22、0.47.0）: ①⑤⑥のポストバック（wk_wake / wk_orders / wk_schedule、子の wk_next・wk_open は親の機能で判定）、起床報告（wake_reports、イベント発生から30分以上遅れて届いたものは受信遅れの印）、短命トークン（line_action_tokens、30分）、PDFの再発行（7日）、当日の起床状況一覧（管理画面「起床状況」、権限 wake_status_read を運用担当に既定付与）を実装。有効な機能はリッチメニューの公開記録（line_rich_menu_releases）の最新の enabled_actions を正本とし、公開記録がない間はすべて「まだご利用いただけません」と返す。公開は `scripts/line/rich_menu.py apply`（RUNBOOK `docs/runbook/LINE_RICH_MENU_RUNBOOK.md`）。staff-mobile の「今日」「予定」はメニューから外し、旧URLは公式LINEへの案内を出す。

### DEC-065: 期間の除外日と、送付先ごとの参加日（日付指定の受諾・受諾後の変更依頼）（2026-10-22）
- Status: Confirmed（ユーザー回答）／一部実装（除外日・作成時の不参加日 0.46.8、受諾後の辞退の記録 0.47.0）。計画書§7.3
- Decision（除外日）: 依頼書の稼働日の「期間」に、除外日（休業日）の入力欄を追加する。予備日（実施未定の日）は運用しない（実施が決まるまで依頼書を発行しない）。
- Decision（送付先ごとの参加日）: 個人ごとの不参加日、日付を指定した受諾、受諾後の参加日の変更を、「送付先ごとの参加日」という1つのデータで扱う。経路は次の3つ。
  1. 運営が依頼書の作成時に、個人の不参加日を入力する。
  2. 日付を指定した受諾：依頼書の作成時にチェックボックスで許可・不許可を選ぶ（全日程に通しで参加が必要な案件があるため）。許可された依頼書では、本人が参加日を選んで受諾した時点で確定する。運営は日ごとの充足状況（必要人数に対する参加人数）で確認する。
  3. 受諾後の変更依頼：本人がLINE（⑤受託済みの発注依頼書）から日付を選んで、いつでも依頼できる。日を減らす依頼・増やす依頼の両方を受け付け、承認するかどうかは運営が判断する。結果は本人へLINEで通知する。
- Data（2026-10-22補記）: 提示した日（実勤務日−個人不参加日。確定時に送付行へ固定）、合意した日（受諾時に固定。追記型の参加日の状態）、変更申請（申請時の状態・増減・理由・受信日時・審査状態）を区別して保存する。実勤務日は勤務グループから共通の除外日を除いた日。許可のない依頼書の受諾は提示日の全部への同意とする。
- Decision（2026-10-22補記、ユーザー説明による）: 当日・翌日分の変更申請は運営の通知先へ即時に知らせ、至急扱いにする。承認されるまでは確定済みの勤務・充足人数・起床監視を維持し、本人には「依頼を受け付けました。運営が承認するまでは、予定どおりの勤務です」と返す（増加を含む場合は、追加希望日は承認まで確定でない旨を添える）。本人が申請した増加は、運営が承認すれば、その依頼書の実勤務日の範囲内に限り修正版なしで反映する。共通の条件の変更は修正版で行う（DEC-063）。
- Guard: 申請の承認は依頼書単位のロック下で、対象版が本人の適用版のままか、参加日の状態が申請時と同じかを確認し、異なれば自動で反映せず失効（stale）とする。承認・却下・取り下げは冪等にし、状態・稼働予定・監査・結果通知の送信予定を同一トランザクションで保存して、通知はcommit後に送る。通知の送信成功を運営の確認済みとみなさない（received / seen / approved / rejected / withdrawn / stale）。過去の勤務日は変更しない。
- Pending: 運営の側から個人の参加日の追加を提案する場合の本人同意の方式（決まるまでは修正版で対応）、必要人数の保存場所の詳細（勤務グループまたは日ごと）、日付選択のLIFF画面、直前の申請の確認担当・代行・電話確認の時間（RUNBOOK）。
- Display: 個人の参加日は依頼書のPDF（版ごとに全員共通）には載せず、本人へのLINEの文面とスケジュール確認・⑤で示す。
- Implementation（2026-10-22、0.46.8）: A0として、期間の除外日（schedule.work_groups[].excluded_dates）と、送付先ごとの個人不参加日（order_request_versions.draft_recipient_absences、migration 20261022a001）を実装。個人不参加日は本文の元データ（request_conditions）ではなく専用の列に持つ（詳細設計§3.2）。
- Implementation（2026-10-22、0.47.0）: 確定時に送付行の提示日（offered_dates）を固定し、受諾で提示日の全部を参加日とする。受諾後の辞退は、運営が送付状況の表の「受諾後の辞退を記録」から理由付きで記録する（参加日0日の状態を追記し、その人の稼働予定を取り消す。ほかの送付先は変えない）。日付指定の受諾と変更依頼は A1+。
- Version: 除外日と作成時の不参加日の入力は既存の依頼書への項目追加なのでZ（A0）。日付指定の受諾と変更依頼は、新しい業務フローとして、その公開時に判定する。
- Spec Reference: DEC-044/046/063。

### DEC-066: 起床の監視・催促・運営への通知の方針（2026-10-22）
- Status: Partial Confirmed（業務方針はユーザー回答）／Pending（乗換API・駅の選択方法・複数駅の扱い）／未実装（A2・A3）。計画書§7.10
- Decision: 期限＝基準の勤務の開始（＝集合時刻）− 移動時間 − 余裕時間（初期値60分、設定で変更可）。期限までに起床報告がなければ5分おきに3回本人へ催促し、それでもなければ運営へ通知する。運営への通知後に報告があれば追加で通知し、報告時点で催促を止める。起床の対象は初期値を全勤務とし、設定で「開始がHH:MMより前の勤務だけ」などに変更できる。運営への通知の受け取り可否は、ID・権限管理で人ごとに設定する（0人ならLINE紐付け済みのadmin全員へ送る案）。通数増は有料プランで許容する。
- Design: 変更確認中の予定も旧い条件で監視する。開始0:00〜4:59の勤務と、期限が稼働日の前日になる勤務は自動の対象外とし、運営の確認に回す（同じ日の通常勤務の監視は続ける）。移動時間はA2では運営の手動設定で始め、未設定なら自動で催促しない。乗換APIによる自動計算はA3で選定・費用判断する（DEC-043は当時の工程での判断で、恒久的な禁止ではない）。通知は論理通知として保存してから送り、再試行キーを使う。acceptedは到達を意味しない。
- Spec Reference: DEC-042/043/050/056/063。
- Decision（2026-10-22補記、ユーザー回答）: 締切＝勤務開始日時（＝集合時刻）− 両端の徒歩時間（自宅→最寄り駅、会場の最寄り駅→会場）− 駅間の概算時間 − 移動の余裕時間（15分）− 出発前の準備時間（起床報告から出発まで60分）。稼働者に最寄り駅が複数あるときは、徒歩を含む合計が最短の経路を使う。上の「余裕時間（初期値60分）」の式はこれで置き換える。
- Decision（2026-10-22補記、ユーザー回答）: 駅間の時間は駅すぱあと API で自動取得する方針（買い切りを検討中。先方サイトのメンテナンス明けに条件を確認するまで保留）。API導入までは乗車時間を手入力しないため、自動の催促はAPI導入後に開始する。結果は駅の組ごとに保存して使い回す。
- Decision（2026-10-22補記、ユーザー回答）: 運営への通知は、ID・権限管理の役割ごとに付与する権限「起床報告が無い場合の連絡受け取り」（wake_alert_receive）を持ち、公式LINEと連携済みの人へ送る。管理者は全権限を持つため既定で対象。公式LINEはライトプラン（月5,000通。上限到達後はその月は送信不可）へ移行予定のため、月の消費通数を監視して8割で運営へ知らせる。返信（応答メッセージ）は通数に含まれない。
- Implementation（2026-10-22、0.47.4）: 依頼書に「会場の最寄り駅（任意）」と「駅から徒歩（分、0〜120）」を追加し、本文・PDFに「■最寄り駅」として表示。権限 wake_alert_receive を追加（A2で使用）。

### DEC-067: 正式の発注依頼書も公式LINEで送付する（DEC-028の上書き）（2026-10-22）
- Status: Confirmed（ユーザー回答 2026-10-22「すべて公式LINEで送付します」）
- Context: DEC-028（2026-10-06）は、公式LINEで送れるのはテスト区分の依頼書だけとし、正式区分は弁護士確認済みの書式が適用されるまで送らないとしていた。一方、同日のコミット 3724948（send confirmed orders on LINE）以降、コードは正式区分も送付できる状態になっており、その判断がこのログに記録されていなかった。
- Decision: 発注依頼書は、正式・テストの区分にかかわらず、すべて公式LINEで送付する。DEC-028の「テスト区分だけ」を上書きする。正式区分の受諾は、DEC-063の稼働予定の起点になる。
- Follow-ups: `src/services/line_order.py` の冒頭コメント（「正式区分は送らない」）を実装時に直す。弁護士確認済み書式（TEMPLATE_LAYOUT_APPLIED）の適用は、この決定とは別の事項として扱う。
- Spec Reference: DEC-027/028/063。

### DEC-068: 送付先ごとの「閲覧を停止」ボタンを撤去する（2026-10-22）
- Status: Confirmed（ユーザー提案。作成者も同意）／実装済み（0.46.8・0.47.0）。詳細設計 `docs/ops/LINE_WORKER_DAILY_OPERATIONS_DESIGN_A0_A1_2026-10-22.md` §12-C1
- Context: 発注依頼書の画面の「送付状況」の表に、送付先ごとの「閲覧を停止」ボタン（view_revoked）がある。押すとその人のPDFリンク・送付・受諾/辞退が止まるが、役割が分かりにくく、認知負荷が大きい。依頼書の作成後に必要な操作は「送付先を選んで送付する」だけである。
- Decision: 「閲覧を停止」のボタンとAPI（/api/order-requests/deliveries/{id}/revoke-view）を撤去する。送付先から外す・依頼をやめる場合は、修正版の発行（DEC-063）または取消（発注の中止。L-34）で行う。修正版を確定したとき、送付先から外れた人に旧い版で発行した期限内のPDFリンクを自動で無効にする。既存の view_revoked の列とデータは残し、撤去前に停止された送付行は、送付先から外れた扱いとする。
- Implementation（2026-10-22、0.46.8）: 画面のボタンと revoke-view API を撤去。修正版で外れた人の旧いPDFリンクの自動無効化はA1で実装する。
- Implementation（2026-10-22、0.47.0）: 修正版の確定時、送付先から外れた人の系列内の期限内PDFリンクを無効にし、稼働予定を取り消す（removed_from_recipients）。
- Version: 既存画面の操作の削除・変更なのでZ。
- Spec Reference: DEC-027/063/065。

### DEC-069: 発注依頼書の送付操作の改善（0.47.1〜0.47.3）（2026-10-22）
- Status: Confirmed（ユーザー指摘・依頼）／実装済み
- Context: A1公開後の確認で、(1) 稼働時間を文章で入力した依頼書は受諾しても稼働予定ができないことが操作者から分からない、(2) 公式LINEでの受諾が画面を開き直すまで「未回答」と表示される、(3) 送付前の入力漏れのメッセージが画面上端にしか出ず「押しても何も起きない」ように見える、(4) 「担当者」が運営側の連絡担当者を指すことが分からず送付できない、が分かった。
- Decision: (1) 日付・期間ごとの入力がない依頼書の確定・送付時に「稼働予定が作られない」ことを確認する（確定は止めない。正式運用前に止めるかは別途判断）。(2) 送信した依頼の一覧を30秒ごと・画面復帰時に読み直す。(3) エラーをボタンの上にも表示し、全体の稼働日が空なら稼働時間の詳細の最初と最後の日で補う。日付・期間の追加時の時刻の初期値を 9:00〜17:00 にする。送信後に「画面を閉じますか？」を確認する。(4) 運営側の連絡担当者を任意にし、空欄は「なし」として本文・PDFに表示する。発注元の担当者の空の選択肢を「なし」と表示する。
- Decision（2026-10-22、ユーザー判断）: (1) を改め、日付・期間ごとの入力がない依頼書は確定できないようにする（サーバーでも拒否）。ただし旧形式の依頼書を基にした「変更を作成」「別日で新規作成」・下書きの保存は止めない（作成時に日付・期間ごとの入力へ自動で切り替え、元の文面は参考として残す）。確定済みの旧形式の依頼書はそのまま。実装 0.47.7。
- Decision（2026-10-22、ユーザー依頼）: 同じイベントを別日に行うときのため「別日で新規作成」を追加する。元の依頼書とは別の系列として作り、日付と期限は空にする。「変更を作成」（同じ系列で置き換える）と使い分ける。実装 0.47.6。
- Version: いずれも既存画面の修正なのでZ（0.47.1・0.47.2・0.47.3・0.47.6・0.47.7）。
- Spec Reference: DEC-063、CHANGELOG 0.47.1〜0.47.3。

### DEC-070: 稼働者向けLINE Web確認画面の構想とレビュー計画（2026-10-22）
- Status: Requirements Confirmed / Design Pending（計画書作成の依頼。実装・公開は未依頼）
- Purpose: 稼働者が「いつ働くか」「いくらになりそうか」「何を確認すべきか」をひと目で把握できるようにする。
- Confirmed requirements: 月間は予定のある日が分かる簡単な印でよい。月間と直近1週間の札表示を切り替える。受諾済みの仕事からインセンティブを除いた月間報酬見込みを目安で表示する。交通費・昼食代は多くが込みであり、概算画面で細分化する必要はない。上記3点を優先し、現行6分割リッチメニューを踏まえた他AIレビュー用の計画書を作る。
- Proposal / Pending: LIFFの共通Web画面、⑤⑥のURI化、確認事項の分類、日付詳細、費用別途の例外、概算算式・税・端数・日給計上単位・時給休憩・再現用履歴、認証と公開制御は提案または未決。計画書に記載した推奨を承認済み仕様にしない。
- Boundary: DEC-063の予定正本とDEC-042/063の会計境界を維持する。Web概算の追加を理由に支払・請求・締め済み結果を書き換えない。DEC-064のトーク方式からの拡張は実装決定時に仕様へ反映する。
- Artifacts: `docs/ops/LINE_WORKER_WEB_PORTAL_PLAN_2026-10-22.md` v0.1、`docs/ops/LINE_WORKER_WEB_PORTAL_REVIEW_REQUEST_2026-10-22.md`。
- Implementation: 今回は文書のみ。コード・DB・本番メニューの変更なし。アプリのバージョン変更とデプロイは対象外。
- Spec Reference: DESIGN_SPEC_v0.3 §3/5/6/7/8/11/12、DEC-042/063/064/065/068/069。

