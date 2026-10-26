# 他のAI向けレビュー資料: LINE運営画面・個人別メニュー

作成・更新: 2026-10-26。当初は設計レビュー資料。本人の実装指示により0.53.0のコード差分を追加した。以降のレビューでは、本書の設計経緯に加えてDEC-119、運用手順と下記の新規コード・テストを確認する。
現行コードの参照コミット: `2ac029c`（本番0.52.9）。文書差分はこのコミット以降の作業ツリーにある。新規ファイルも直接読むこと。

外部レビューへの対応: [指摘への回答と本人の訂正](LINE_OPERATOR_MENU_REVIEW_RESPONSE_2026-10-26.md)。DEC-066（後続補記を含む）・DEC-116/117と [起床未報告対応計画](LINE_WAKE_ESCALATION_PLAN_2026-10-26.md) を併せて読むこと。

## 1. 目的と確定要件

同じ公式LINEの中で、管理者が承認した運営スタッフが全案件・全稼働者のカレンダーと起床状況を閲覧できるようにする。兼務者は運営用と稼働者用のメニューを往復できるようにする。

- 運営登録・承認と稼働者登録は同じLINEで実機確認済み。再登録を要求しない。
- 運営メニューは「起床状況」「カレンダー」「自分の登録情報」「稼働者用への切替」。兼務者の稼働者側にも運営へ戻る入口を設ける。
- 全運営スタッフが全案件・全稼働者を担当制限なく閲覧できることは、本人が明示承認した仕様（DEC-115）。この範囲を未決事項へ戻さない。
- LINE内の専用画面と本人確認を使い、毎回の管理画面ID・パスワード入力を求めない。**運営全員が管理画面Userを持ち、LINEだけの運営は存在しない**（DEC-117）。対応するUser・スタッフ・LINE連携の有効性を各APIで確認する。稼働者を兼ねない運営専任者もUserを持つ。
- DEC-118の設計修正: 閲覧は対応Userの既存wake_status_read、availability_read、order_readで認可する。全運営へ必要権限を設定して全件閲覧を実現し、運営であることだけで権限を迂回しない。カレンダーはデータ種別ごとに認可し、入口のOR条件を全データの許可に流用しない。
- カレンダー/起床状況は閲覧専用。金額、銀行、住所等は取得対象にしない。電話番号の一律除外は初期案であり撤回。本人へのLINE催促後も未報告の場合に、運営へ氏名・登録電話番号を通知する方針は本人指定で確定した。自動通知は別工程で計画し、画面完成と通知完成を混同しない。代理報告・編集・連絡記録登録は初回画面の必須要件にしない。
- 各APIで現在の有効な運営連携・スタッフ状態・セッションを確認する。メニュー画像やクライアントから送られるLINE IDだけを認証根拠にしない。

## 2. 読む順序

1. `docs/decisions/DECISION_LOG.md` DEC-056、DEC-066（後続補記まで）、DEC-110〜118。DEC-115はLINE内閲覧、DEC-117は全運営がUserを持つ前提、DEC-118は既存の閲覧権限で認可する修正。先の暫定案より後の指定と修正を優先する。
2. `docs/spec/DESIGN_SPEC_v0.3.md` §5.1、§6、§14、§16。
3. `docs/ops/LINE_OPERATOR_MENU_IMPLEMENTATION_PLAN_2026-10-26.md` 全文。API・DB名は設計案であり実装済みではない。
4. `docs/ops/LINE_OPERATOR_ONBOARDING_2026-10-26.md`。登録済み/未実装の境界と利用者作業。
5. 下記の現行コード。文書の推測と実装済みの事実を区別してレビューする。

| 確認対象 | 現行ファイルと注意 |
|---|---|
| 運営連携と失効 | `src/models/operator_staff.py`、`src/services/operator_staff.py`。旧OPSコード方式と新しい申請承認方式が共存。unfollowで連携を失効するため、再友だち追加だけで運営権限を復活させない |
| 新規運営申請 | `src/services/operator_registration.py`、`src/api/operator_registration_routes.py`。承認前は運営権限なし |
| 稼働者の本人認証の参考 | `src/services/line_worker.py`、`src/models/line_daily.py` の `LineWorkerSession`。有効期限・ハッシュ保存を参考にし、セッション用途を分離する |
| 起床状況の既存判定 | `src/api/line_daily_routes.py` の `wake_status`、`src/services/worker_schedule.py`、`src/models/line_daily.py`。予定・試験/取消・JST・変更中の扱いを確認 |
| カレンダーの正本 | `src/api/main.py` の `/api/availability-calendar`、`src/api/order_request_routes.py` 等の既存予定/参加関連処理、`src/services/worker_schedule.py`。実装着手時に各表示データの正本と状態を確定し、可否と確定予定を混同しない |
| 全員のメニュー公開 | `scripts/line/rich_menu.py`、`src/models/line_daily.py` の `LineRichMenuRelease`。既存applyは全員の既定表示を変え、enabled_actionsは稼働者機能の公開状態。運営個別割当と混在させない |
| Webhook | `src/services/line_order.py` のイベント振分け。署名・イベント重複防止と新しいメニュー操作を整合させる |
| LINE画面 | `apps/admin-web/src/pages/PublicLineOperatorRegistrationPage.tsx`、`apps/admin-web/src/app/App.tsx`。招待用liff.state復元と閲覧モードを共存させる |
| 管理画面ID | `src/models/master.py` の `User`、`VanzaiStaff`。users.worker_idとvanzai_staff_idは排他。兼務の判定にUserの両FKを要求しない |
| 通知受信権限 | `src/models/enums.py` のWAKE_ALERT_RECEIVE、`src/services/auth.py` のget_user_permissions/has_permission。無効/削除Userは権限なし、adminは全権限。User→VanzaiStaff→LineStaffLinkで本人の受信先を解決し、送信直前に再確認 |
| 閲覧認可と範囲 | `src/services/auth.py`、`src/api/line_daily_routes.py`、`src/api/main.py`のavailability-calendar、`src/api/order_request_routes.py`の_ensure。site_managerはDEC-056とcan_access_projectでは全案件参照。古いROLE_PERMISSIONSコメントだけで担当範囲と断定しない |

## 3. 特に指摘してほしいこと

1. **本人確認と失効:** 他人のID指定、稼働者専任者の越権、申請待ち、期限切れ、スタッフ停止、解除後の再連携で古いセッションが通る穴がないか。未認証APIから業務情報が返らないか。
   対応Userの最新閲覧権限もAPIごとに再評価し、セッション継続中の役割変更・権限剥奪が反映されるか。カレンダーの片側だけの権限で両方を返さないか。
2. **全範囲の取得と項目制限:** 担当外も閲覧できる要件を満たしつつ、ORMや管理用レスポンスの流用で電話・金額等が漏れないか。全件と無制限一括取得を混同していないか。
3. **既存業務との一致:** 可否/確定/変更中/取消/試験データ、日付境界、夜跨ぎ、予定なしの扱いが既存と矛盾しないか。起床未報告と遅刻を混同していないか。
4. **個人別メニューの同期:** 通常の往復はrichmenuswitchを利用し、切替ごとのサーバー割当を省く。承認/停止の割当失敗と再試行、unfollowでの解除、followでの再判定を検証する。LINE側の切替は事前のサーバー権限判定を通らないため、古い画像が残っても業務APIは拒否し、適切な表示へ修正できるか。
5. **影響範囲:** 一般稼働者の6機能やenabled_actionsを壊さないか。専用閲覧のために管理APIの認証を緩めていないか。全員の既定メニューを変更する経路が混入していないか。
6. **実装可能性と不足:** DB案・API・LIFFの遷移・画像の押下領域・監査・テストに抜けがないか。過剰な追加は根拠と簡単な代案を示す。

## 4. まだ設計案である点

- メニュー画像、運営専任者に切替不可を示す具体的な見せ方、初期表示と最後の選択の保持方法。
- レビュー提案の運営専任者3項目化、兼務者の運営画面への起床報告追加、朝の自動切替は本人未決定。実装で勝手に4項目構成や本人の選択を変更しない。
- 運営セッションとメニュー同期のDDL、APIの最終名称・返却項目・取得上限。確定後にmigrationと契約テストを作る。
- 月表示/日付詳細・検索条件と、可否/参加予定をどこまで初回画面に並べるか。提案は月表示と日付別詳細。既存の予定定義を変更しない。
- 既存LIFFの表示モード拡張で招待登録と閲覧を両立することの実機検証。新LIFFが必要なら、理由と利用者作業を明記する。
- 自動通知の期限式、5分おき3回、wake_alert_receive受信者、報告後追加通知、対象外勤務、駅すぱあと導入条件、8割の通数警告はDEC-066で決定済み。未決定に戻さない。送信不能時の連絡運用と時刻境界の実装詳細だけを区別して確認する。

これらは推奨案を付けてレビューできる。確定済みの全案件・全稼働者閲覧やLINE内の専用画面を、実装簡略化のために管理画面ログイン必須へ戻さない。

## 5. 実装後の必須確認と現在の検証状態

- 運営専任・兼務・稼働者専任・未承認・無効・期限切れの認証行列と、他人のID/トークン差替え。
- 管理画面Userを持つ運営専任者が、LINE内で毎回パスワードを入力せず担当外も閲覧できること。User未対応/無効/削除なら拒否し、対応Userを変更したら旧セッションを無効にすること。
- 対象外項目の非返却と更新操作の拒否、既存管理APIの権限維持。
- 既存管理画面と専用閲覧画面の集計一致、JST境界・取消/変更中/試験/予定なしの表示。
- LINE割当失敗・再試行・競合・失効・戻し、他の一般稼働者のメニュー不変。
- 本人1名の実機で専用画面、兼務往復、読みやすさを確認してから段階公開。
- 全運営の全件閲覧と、wake_alert_receiveを持つ人だけの通知受信が分離されること。Userの有効性と最新の役割権限を送信時に確認し、二重User等があっても同じLINEへの重複を防ぐこと。
- 管理画面とLINEの権限一致、wake_status_read剥奪後の403、availability_read/order_readの片方のみ・両方・両方なし、site_managerの全件参照とCSV提出範囲の維持。

**0.53.0の実装と自動テストを追加済み。本人の実LINE端末での確認は未実施。** 実装: `src/models/line_operator.py`、`src/services/line_operator.py`、`src/services/line_operator_menu.py`、`src/services/operator_calendar.py`、`src/services/wake_status.py`、`src/api/line_operator_routes.py`、`src/api/operator_access_routes.py`、`scripts/line/operator_menu.py`、管理画面の`PublicLineOperatorEntry/PortalPage`と`OperatorAccessPanel`。追加DDLは`20261026b001`の3表。テスト: `tests/test_line_operator_portal.py`、`tests/test_line_operator_migration.py`、`apps/admin-web/e2e/line-operator-portal.spec.ts`。既存のLINE/運営登録/カレンダー回帰と両アプリのビルドも実行する。操作手順は `LINE_OPERATOR_PORTAL_RUNBOOK.md`。

## 6. 別のAIへ渡す依頼文

以下をリポジトリを読める別のAIへ渡してください。レビューでは `.env` / `.env20261006` 等の秘密設定を読まないでください。

> LINE運営専用画面と個人別メニューの0.53.0実装をレビューしてください。まず `docs/ops/LINE_OPERATOR_MENU_REVIEW_BRIEF_2026-10-26.md` とDEC-119を読み、仕様・計画・コード・追加テストを照合してください。新規ファイルが未追跡の場合も実ファイルを読んでください。全運営が管理画面Userを持ち、毎回のパスワード入力なしでLINE本人と対応Userの有効性・管理ロール・最新の既存閲覧権限を確認したうえで全案件・全稼働者を閲覧する実装です。通常のメニュー往復はLINE標準richmenuswitchで、承認/失効時は本人単位で再同期します。全員の既定メニューを変えず、LINEだけ権限を迂回しないこと、稼働者ロールを運営として拒否すること、登録とUserの対応を推測しないことを確認してください。自動催促/運営通知は別工程で今回有効化しません。site_managerは全案件参照・CSV提出は担当分です。重大度順に「問題、発生条件と影響、根拠ファイルと行、修正案、必要な検証」を提示してください。問題がなければその旨と未確認点を示してください。コード変更・本番操作はせず、秘密設定を読まないでください。
