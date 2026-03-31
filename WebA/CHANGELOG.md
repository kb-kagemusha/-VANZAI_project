# 変更ログ（買い周りサポートアプリ）

---

## 2026-03-10

### 電話確認フロー追加・報告ナンバー㉛〜㉝新設（flow-data.json / leader.html / mobile-report-app.html）

- **flow-data.json**: 最初の質問を `store_type` から `action_type`（「買い周りに出る」or「電話確認する」）に変更
  - 電話フローノード追加: `phone_stock` → `phone_had_stock_instr` または `phone_no_stock` → `phone_reserved_instr` or `R33`
  - 新報告ノード追加:
    - `R31`（㉛）: 電話確認：在庫あり・取り置き成功
    - `R32`（㉜）: 電話確認：入荷待ち・予約成功
    - `R33`（㉝）: 電話確認：予約不可
- **leader.html**:
  - `CATEGORY_MAP` に「電話確認（㉛〜㉝）」カテゴリ追加
  - `REPORT_NO_RESULT_MAP` に㉛㉜㉝を追加
  - メンバー別集計の `RESV_NOS`（予約）に㉛㉜を追加、`CANT_NOS`（不可）に㉝を追加
  - バッジ分類の `_RSV_NOS` に㉛㉜を追加
- **mobile-report-app.html**: `REPORT_CATEGORIES` に「電話確認（㉛〜㉝）」カテゴリ追加

### 全角スペース含む名前のプロフィール保存403バグ修正（app_server.py）

- `_actor()` の `c.isprintable()` が全角スペース（U+3000）を非印刷と誤判定して除去していた
- `unicodedata.category()` により制御文字（Cc/Cf/Cs/Co/Cn）のみを除去する方式に変更
- `import unicodedata` を追加

### 報告ナンバーDB不整合修正（SQLite直接実行）

- 旧形式reportNo（`31`、`A-001`）および reportNo と resultType が矛盾するレコードを修正:
  - `31` → `⑧`（resultType=予約できた）
  - `⑱` → `①`（resultType=陳列されていて購入できた）
  - `⑩` → `⑧`（resultType=予約できた）
  - `①` → `③`（resultType=陳列はなかったが在庫から購入した）
  - `①` → `⑥`（resultType=予約した本を購入できた）
  - `A-001` → `①`（resultType=陳列されていて購入できた）
- leader.html バッジ判定に旧形式フォールバック追加（resultTypeテキストで購入/予約/不可を判定）

### 自分の予定入力ボタン移動（mobile-report-app.html）

- 「自分の予定」カード内ヘッダー右端 → カードの外・「チームの今週の予定」カード直前に移動
- 横幅いっぱい・紫枠（`border:2px solid #7c3aed`）に変更

### リーダー画面「表示カテゴリ」表記変更（leader.html）

- 「表示するカテゴリを選択してください」→「表示カテゴリ」

---

## 2026-03-06（6回目）

### 指名解除が反映されないバグ修正（leader.html）

- **原因①**: `assignApplyChanges()` がチーム名を `scTeamSelect.value` から取得していたため、チーム変更後に古いチームのメンバーが誤ったチームで削除リクエストされ、WHERE句にマッチせず0件削除（成功扱い）になっていた
- **原因②**: APIレスポンスの成否チェックがなく、セッション切れ等で認証失敗しても成功扱いになっていた
- **修正①**: `assignApplyChanges()` でチーム名を `scTeamSelect.value` の代わりに `assignCachedTeam`（パネル読み込み時点のチーム）から取得するよう変更
- **修正②**: `apiFetch` の戻り値 `result.ok` をチェックし、不正レスポンス時はエラーを throw するよう変更
- **修正③**: チーム変更（`scTeamSelect.change`）・週ナビゲーション（前週/次週/今週）時に `assignPendingChanges` をクリアし、古い週・チームの変更が混入しないよう修正

---

## 2026-03-06（5回目）

### 「電話予約」ショートカットボタン追加（mobile-report-app.html）

- フロー判定カードヘッダー右端に「📞 電話予約」ボタンを追加
- タップで報告No=31・結果=「予約できた」を自動セットして報告タブへ遷移

### leader.html CSV列名修正（leader.html）

- `downloadCsv()` の headers 配列内「報告ノー・」→「報告No」に修正

---

## 2026-03-06（4回目）

### タブ表示名の変更（mobile-report-app.html）

- タブボタン（`#tabFlow`）の表示を「フロー判定」→「やること」に変更（一般ユーザー向け表示の改善）

---

## 2026-03-06（3回目）

### CSV出力の列順・ヘッダー変更（mobile-report-app.html）

- `exportCsv()` をキー参照方式 → 列定義（columns配列）方式に刷新
- 出力順: ①タイムスタンプ ②購入者 ③結果 ④在庫冊数 ⑤報告ナンバー ⑥購入日 ⑦購入時刻 ⑧店舗名 ⑨購入店舗の住所 ⑩レシート写真 ⑪連絡事項・コメント
- `team` / `id` を出力対象から除外
- `purchaseAt`（`YYYY-MM-DDTHH:MM`）を購入日・購入時刻に自動分割
- ヘッダー行を日本語表示に変更

---

### 「リセット」ボタンを南京錠タップ時のみ表示（mobile-report-app.html）

- `actorResetBtn` のデフォルトを `display:none` に変更
- `actorUnlockBtn` クリック時に `display:inline-block` で表示

---

### 自分のデータ保存後に自動で畳む（mobile-report-app.html）

- `saveProfile()` 保存成功後に `profileEditArea` を非表示・トグル矢印を `▶` に戻す
- `showToast('保存しました')` を表示（旧「自分データを保存しました」から変更）

---

### iOSチェックボックス縦ズレ修正（mobile-report-app.html）

- `.sched-detail-chk` の CSS に `-webkit-flex` / `-webkit-align-items` プレフィックスを追加
- `line-height:1.4` / `min-height:22px` / `vertical-align:middle` で車・徒歩ラベルのズレを修正

---

### 担当日セルのオレンジ枠表示（mobile-report-app.html）

- `myWeekAssignedDates`（Set）変数を追加
- `loadMyWeekSchedule()` 内でスケジュールと同週の assignments を並行取得し `myWeekAssignedDates` を構築
- `renderMyScheduleGrid()` で `myWeekAssignedDates.has(ymd)` が true のセルに `border-color:#f97316` + `box-shadow` を適用

---

### 自宅チェックを初回登録時のみデフォルト化（mobile-report-app.html）

- `renderMyScheduleGrid()` 内の「描画のたびに `home:true` を強制補正」コードを削除
- `setSchedAvail()` の自動チェックをその日の detail が未存在の初回選択時のみに限定
- → チェックを外したあと再描画してもそのまま維持される仕様に変更

---

### チームスケジュールのメンバー並び順を登録順に修正（mobile-report-app.html）

- `loadAndRenderTeamSchedule()` 内の `.sort((a, b) => a.localeCompare(b, 'ja'))` を削除
- サーバー側が `ORDER BY is_leader DESC, sort_order ASC, id ASC` で返す登録順をそのまま使用

---

## 2026-03-06（2回目）

### 担当購入冊数指定機能（app_server.py / leader.html / mobile-report-app.html）

- **app_server.py**
  - `leader_assignments` テーブルに `purchase_count INTEGER DEFAULT 1` カラムを追加（マイグレーション）
  - `GET /api/assignments`: `purchaseCount` フィールドを返却
  - `PUT /api/assignments/bulk`: `purchaseCount`（1〜3）を受け取り保存（`ON CONFLICT DO UPDATE`）

- **leader.html**
  - `assignPurchaseCountMap`（確定済み冊数）を追加
  - 指名済みボタン直下に ×1 / ×2 / ×3 のドロップダウンを表示
  - `setAssignPurchaseCount()` 関数を追加
  - 「反映」送信時に `purchaseCount` を含める
  - リセット時に `assignPurchaseCountMap` もクリア

- **mobile-report-app.html**
  - チーム予定テーブルの `assignSet`（Set）→ `assignCountMap`（Map: `member@@date` → purchaseCount）に変更
  - 担当数が **2以上のときのみ**「★担当」の横に赤バッジで数字を表示

---

### 予定チェック「その他」展開入力・ラベル変更（mobile-report-app.html）

- 「自由記述」→「**その他**」にラベル変更
- 「その他」テキスト入力欄をフォーカス時に `position:absolute; width:220px; z-index:50` で横展開
- フォーカスアウト後は元の幅に戻る（`transition` アニメーション付き）
- プレースホルダーを「内容を入力」に変更

---

### 予定未入力ユーザーへの誘導（mobile-report-app.html）

- 「✏️ 予定入力」ボタン押下時に `homeArea` 未設定を検出
- 画面下部にトースト通知（**「⚠️ 先に「自分のデータ」を入力してください」**）を3秒表示
- 「自分のデータ」カードを自動展開してスムーズスクロール
- 予定入力モードには入らない

---

### リーダー指名管理: その他メモ表示（leader.html）

- `scheduleDetailMap`（Map: `member@@date` → locationDetail JSONオブジェクト）を追加
- `loadAssignmentPanel` でプロフィール（住所）を並行取得し `memberProfileMap` を構築
- **担当日メモモーダル** 内にハイライトエリア（`#assignNoteOtherArea`）を追加
  - プロフィールに住所登録があれば常に表示（自宅・職場）
  - チェック済み → ✅、未チェック → ◻️ で区別
  - 「その他」記入があれば 📝 その他: ○○○ を追加表示
- セルに「📝 その他あり」ボタン（黄色枠）を表示（メモなし＋その他あり時）

---

### 氏名・所属リセットボタン追加（mobile-report-app.html）

- 「7）連絡事項・コメント」ラベル行の南京錠🔒の手前に **「リセット」** ボタンを追加
- クリック → 確認ダイアログ → OK で `mc_actor_v1` / `mc_active_team_v1` / `mc_flow_state_v1` をクリア → `location.reload()`
- キャンセルで何もしない

---

### 報告データ一覧：列構成変更・ハイライト・昨日フィルター（leader.html）

- **列構成を変更**（全9列）
  - 旧: チェック / 日時 / チーム / 実行者 / No. / 結果 / 添付 / 編集
  - 新: チェック / 実行者（チーム名） / 日付 / 購入/予約 / NOと結果 / 書店名 / 住所 / 写真 / 編集
  - 実行者セルに「名前＋改行＋(チーム名)」を表示
  - 日付は時間を省略（YYYY-MM-DD のみ）
  - 購入/予約バッジ: resultType に「購入」含む→緑、「予約」含む→青、その他→「—」
  - NOと結果: 報告No.＋改行＋resultType テキスト（グレー小文字）
  - 住所から 〒XXX-XXXX を正規表現で除去して表示

- **チェック行ハイライト**
  - CSS `.row-selected { background:#fef9c3 !important; outline:2px solid #f59e0b; }` 追加
  - チェックボックス `change` イベントで `tr` に `.row-selected` を付与/除去
  - 全選択・全解除・「選択解除」ボタンにも対応

- **「昨日」フィルターボタン追加**
  - 「今日」の右隣に「昨日」ボタンを追加
  - `_rtDateRange()` に `rtMode === 'yesterday'` 分岐を追加（前日の日付で start/end を設定）
  - `setRtMode()` のボタン強調表示に `rtYesterday` を追加

---

### 担当メモ機能（assignment_notes）の追加（app_server.py / leader.html / mobile-report-app.html）

- **app_server.py**
  - `init_db()` に `assignment_notes` テーブルを追加
    - `(id, team, member_name, note_date, note_text, updated_at)`
    - `UNIQUE(team, member_name, note_date)` 制約
  - `_needs_leader_auth()` の PUT セクションに `["api","assignment-notes"]` を追加
  - `GET /api/assignment-notes?team=&member=&from=&to=` を追加（member指定なし→リーダー認証必須）
  - `PUT /api/assignment-notes` を追加（リーダー認証、UPSERT、最大2000文字）

- **leader.html**
  - `assignNoteMap`（`Map`）と `_assignNoteEditKey` グローバル変数を追加
  - `loadAssignmentPanel()` の `Promise.all` に notes フェッチを追加→ `assignNoteMap` を初期化
  - `_renderAssignFromCache()`: ◎△☓バッジ下にメモボタンを追加
    - メモあり → 1行プレビュー（黄色ボタン）
    - メモなし → 「＋メモ追加」（点線ボタン）
  - 担当メモ編集モーダルを追加（固定オーバーレイ、オーバーレイクリックで閉じる）
  - `openAssignNoteModal()` / `saveAssignNote()` / `closeAssignNoteModal()` を追加

- **mobile-report-app.html**
  - `schedEditBtns` 下に `#assignNoteArea` div を追加
  - `loadAssignNotes()` 関数を追加（今日〜20日後の範囲でノートを取得、日付ごとに「📖 書店名」リスト表示）
  - `initScheduleTab()` で `loadAssignNotes()` を呼び出す

---

### N日目バッジ・担当指名管理 安定化（app_server.py / leader.html / mobile-report-app.html）

- **N日目バッジをサーバー保存化**
  - `teams` テーブルに `event_start_date` カラムを追加（マイグレーション）
  - `GET /api/team-settings?team=` を追加（公開）
  - `PUT /api/team-settings` を追加（リーダー認証）
  - `leader.html`: 「設定」「クリア」ボタン＋ロック機能、全チーム一括保存
  - `mobile-report-app.html`: サーバーから取得 → ローカルキャッシュ併用

- **土日色分け・自分の担当日改善**（mobile-report-app.html）
  - チームの今週の予定テーブル: 土曜ヘッダー青・日曜ヘッダー赤・セル背景色
  - 自分の担当日: 過去日除外・曜日表示・土日色付き

- **チームの今週の予定: 実績行（📦）追加**
  - `GET /api/reported-dates`（member指定なし）で日別報告件数を返すよう拡張
  - テーブル末尾に緑背景の実績行を追加

---

## 2026-03-05 (5回目)

### 報告編集機能の追加（app_server.py / leader.html）

- `app_server.py`
  - `_needs_leader_auth()` の PATCH セクションに `PATCH /api/reports/{id}` を追加
  - `do_PATCH()` に `/api/reports/{id}` ハンドラーを追加
    - 許可フィールド: `actor, result_type, report_no, purchase_at, store_name, store_address, comment, team, created_at`
    - `edit_report` として audit ログに記録

- `leader.html`
  - 報告テーブルに「編集」列（8列目）と ✏️ ボタンを追加（削除済み行はボタンなし）
  - `editReportModal` を追加（proxyModal と同構成）
    - チーム選択 → 実行者ドロップダウン + その他直接入力
    - 報告No → 結果自動入力
    - 報告日時・購入日時・店舗名・住所・コメント
  - JS 関数: `openEditModal(r)`, `closeEditReportModal()`, `submitEditReport()`, `_updateEditMembers()`, `_toDatetimeLocal()`
  - `bindEvents()` にモーダル用イベントリスナーを追加

---

## 2026-03-05 (4回目)

### 予定確認タブ: クリック即反映 →「反映する」バッチ適用方式に変更（leader.html）

**変更理由**: PC 環境でクリックするたびに全スケジュールを再読み込みするため動作が重い。

**変更内容**:
- 状態変数を追加: `scPendingChanges`（未反映 Map）、`scCachedChunks`・`scCachedDates`（データキャッシュ）
- `buildScTable()` の `onclick` を `scSetAvail`（即時 API）→ `scClickCell`（ローカル変更のみ）に変更
  - 未反映セルにオレンジ枠（`.sc-avail-pending`）と `●` マークを表示
- `scClickCell()` を追加: API を呼ばずに `scPendingChanges` を更新し再描画
- `_renderScFromCache()` を追加: キャッシュから即時再描画（API 呼び出しなし）
- `_updateScApplyBar()` を追加: 未反映バーの表示制御
- `scApplyChanges()` を追加:「反映する」押下時に全変更を `Promise.all` でバルク送信 → 完了後1回リロード
- HTML に「未反映バー」を追加: `N件の変更が未反映`・`✅ 反映する`・`↩ 変更をリセット`
- CSS: `.sc-avail-pending { box-shadow: 0 0 0 2px #f97316; }` を追加
- `window.scSetAvail` を `window.scClickCell` に変更

---

## 2026-03-05 (3回目)

### 担当日指名 UI 改善・祝日カラー対応（leader.html）

- **担当日指名**:「☓」のメンバーは指名ボタンを `disabled`（「指名不可」グレーアウト）に変更
- **曜日・祝日カラー**:
  - 土曜 → 青（`#2563eb`）
  - 日曜・祝日 → 赤（`#dc2626`）
  - 予定確認タブ・担当日指名管理タブの両方に適用
- **祝日リスト** `JP_HOLIDAYS`（Set）を追加: 2025〜2027 年の日本国民の祝日
- **`dayColor(d)`** ヘルパー関数を追加
- **担当日指名の指名人数バッジ強調**:
  - 1人以上: 橙色バッジ（`background:#f59e0b`）で「N人」表示
  - 0人: グレーの小文字「0人」
  - 日付ヘッダーに曜日（月火水…）も追加

---

## 2026-03-05 (2回目)

### 一般ページにスケジュール確認機能を追加（mobile-report-app.html / app_server.py / leader.html）

- `mobile-report-app.html`
  - タブに `📅 予定` を追加（既存 `フロー判定` / `報告する` に加えて3タブ化）
  - スケジュールタブを新設し、以下を実装
    - 自分データ（住まい/職場住所・移動手段[車/電車/両方]）の保存UI
    - 週単位（月曜始まり）の予定入力（`◎/△/☓`）
    - 前週/次週/今週移動、今日セルの強調表示
    - 来週未入力警告バナー表示
    - チーム今週予定テーブル（自分含む）
    - リーダー指名セルのハイライト、日別指名人数表示
    - 「自分の担当日を確認」ボタン（指名日の一覧表示）
    - 報告送信済み日を優先色で上書き表示
  - API連携を追加
    - `GET/PUT /api/profile`
    - `GET /api/schedules`
    - `PUT /api/schedules/bulk`
    - `GET /api/assignments`
    - `GET /api/reported-dates`

- `app_server.py`
  - DBテーブル追加
    - `member_profiles`（住まい/職場/移動手段）
    - `member_schedules`（日別予定 `o/d/x`）
    - `leader_assignments`（リーダー指名）
  - API追加
    - `GET /api/profile?team=&member=`
    - `PUT /api/profile`
    - `GET /api/schedules?team=&from=&to=`
    - `PUT /api/schedules/bulk`
    - `GET /api/assignments?team=&from=&to=`
    - `PUT /api/assignments/bulk`（リーダー認証）
    - `DELETE /api/assignments?team=&member=&date=`（リーダー認証）
    - `GET /api/reported-dates?team=&member=&from=&to=`
  - プロフィール閲覧/更新を「本人またはリーダーのみ」に制限
  - チーム削除・チーム名変更・メンバー削除/移動時に新テーブル側も同期するよう更新

- `leader.html`
  - リーダー設定タブに「担当日 指名管理」セクションを追加
    - 週移動（月曜始まり）
    - メンバー×7日の指名トグル
    - 日別指名人数表示
    - `PUT /api/assignments/bulk` 連携
  - 「メンバー住所情報（全文表示）」セクションを追加
    - チーム別に住まい/職場/移動手段を一覧表示
    - `GET /api/profile` 連携

### 構文チェック

- `C:/MykeyC/.venv/Scripts/python.exe -m py_compile C:/MykeyC/app_server.py` 実施済み

## 2026-03-05 ★期間限定フロー変更（発売2週間）

### 購入判断ルールの一時変更（flow-data.json / mobile-report-app.html）

**変更内容：**

| 店舗区分 | 旧ルール | 新ルール（期間限定） |
|---|---|---|
| 大型店（紀伊國屋書店・丸善ジュンク堂） | 平積み：4冊以上でOK / 棚刺し：2冊以上でOK | 平積み・棚刺し共に **2冊以上でOK** |
| 非大型店（上記以外） | 2冊以上でOK、1冊だけはNG | **1冊だけでもOK** |

**変更ノード（3箇所）：**

| ノードID | 変更前 | 変更後 |
|---|---|---|
| `count4_direct` | title「4冊以上ある？」YES→R1 / NO→R11 | title「2冊以上ある？」YES→R1 / NO→R11 |
| `count2a_direct_other` | YES→R1 / **NO→R11（購入NG）** | YES→R1 / **NO→R1（購入OK）** |
| `count2a_staff_other` | YES→R4 / **NO→R13（購入NG）** | YES→R4 / **NO→R4（購入OK）** |

---

### ⏪ 元に戻す手順（2週間後）

**方法1：VPS上でコピー（推奨）**
```bash
cp /opt/mykey/flow-data-original.json /opt/mykey/flow-data.json
systemctl restart mykey.service
```

**方法2：ローカルでファイル差し替え後デプロイ**
```powershell
# ローカル
Copy-Item c:\MykeyC\flow-data-original.json c:\MykeyC\flow-data.json -Force
# mobile-report-app.html の埋め込みデータを手動で3箇所戻す（下記参照）
```
> mobile-report-app.html 埋め込みデータの逆変更：
> - `count4_direct` → title「4冊以上ある？」choices「YES 4冊以上→R1 / NO 3冊以下→R11」
> - `count2a_direct_other` → 「NO 1冊だけ」の next を `R1` → **`R11`** に戻す
> - `count2a_staff_other` → 「NO 1冊だけ」の next を `R4` → **`R13`** に戻す

---



### 代理入力機能の追加（leader.html）

リーダーがメンバーに代わって過去の実績を手動入力できるモーダルフォームを追加。

**ボタン位置**：集計タブ > 報告データ一覧（添付確認）カード > 「＋ 代理入力」ボタン（CSV の隣）

**入力フォーム（モーダル）**：
| フィールド | 内容 |
|---|---|
| チーム | `teams` から選択 |
| 実行者 | 選択したチームのメンバー一覧、または「その他（直接入力）」 |
| 報告ナンバー | ①〜⑲ のドロップダウン（PROJECT_CONTEXT のラベル表示） |
| 結果 | 報告ナンバー選択時に `REPORT_NO_RESULT_MAP` で自動入力（読み取り専用） |
| 報告日時 | `datetime-local`（デフォルト現在時刻、過去日時入力可） |
| 購入日時 | `datetime-local` |
| 店舗名 | テキスト |
| 住所 | テキスト |
| コメント | テキストエリア（任意） |

**動作**：
- モーダルを開くと `/api/teams` / `/api/members` を再取得（設定タブ未訪問でも正常動作）
- 送信後 `POST /api/reports` に `createdAt: UTC ISO`、`receiptFileName: '未選択'` で送信
- 送信成功後: 「✅ 送信しました」メッセージ表示 → 1.2秒後モーダル自動クローズ → `loadData()` で一覧更新
- 背景クリック・×ボタン・キャンセルでモーダルを閉じる

---

## 2026-03-04 (5回目)

### 集計チームフィルター バグ修正（app_server.py）

**問題**: リーダー画面の集計タブでチームを選択すると件数が 0 になる。

**根本原因**: モバイルアプリが `created_at` を `new Date().toISOString()`（UTC）で保存する一方、
フロントエンドが日付パラメーターを JST（ブラウザローカル時刻）で送信していたため、
JST 午前 0〜8 時台に投稿されたレポートの UTC 日付が前日になり、日付フィルターが不一致になっていた。

**修正内容 (`app_server.py`)**: 全 4 サマリーエンドポイント（`daily` / `weekly` / `monthly` / `range`）の
WHERE 句で UTC日付の直接比較 `substr(created_at, 1, 10)` を
JST変換後の日付比較 `substr(datetime(replace(created_at,'Z',''),'+9 hours'),1,10)` に変更。

| エンドポイント | 変更箇所 |
|---|---|
| `GET /api/summary/daily` | `cur_where` / `prev_where` の date 比較式 |
| `GET /api/summary/weekly` | `base_where` の BETWEEN 式 |
| `GET /api/summary/monthly` | `base_where` の BETWEEN 式 |
| `GET /api/summary/range` | `base_where` / `prev_where` の BETWEEN 式 |

修正後の動作確認（VPS DB 直接クエリ）:
- チームB（早朝投稿 UTC 前日扱い）: 旧方式 0件 → 新方式 **2件** ✓
- 全体合計: 旧方式 3件 → 新方式 **5件**（全チーム正常計上）✓

---

## 2026-03-04 (4回目)

### チーム・メンバー管理機能の追加
- **DB スキーマ追加**：`members` テーブル (`id`, `team_name`, `name`, `created_at`) を `shared_reports.db` に追加
- **API 追加（app_server.py）**：
  - `GET /api/members` — メンバー一覧（クエリ: `?team=` でフィルター可）
  - `POST /api/members` — メンバー追加（リーダー認証必須）
  - `DELETE /api/members/{id}` — メンバー削除（リーダー認証必須）
  - `PATCH /api/members/{id}` — メンバー名変更（リーダー認証必須）
  - `PATCH /api/teams/{name}` — チーム名変更（リーダー認証必須）+ `rename_team` 監査ログ
  - `do_PATCH` メソッドを `app_server.py` に新規追加
- **leader.html — リーダー設定タブ改善**：
  - メンバー行を2段構成（名前全幅 ＋ コントロール行）に変更
  - テキストエリアによる一括メンバー追加（改行区切り）
  - チーム名変更：「✏️ 名称変更」ボタン + 折りたたみ入力行
- **mobile-report-app.html — ゲート画面改修**：
  - 氏名入力をチーム連動のドロップダウン（`actorSelect`）に変更
  - `updateTeamGateVisibility()` を「チームが有効 AND 氏名が選択済み」の両条件でゲート通過に変更
  - ゲートタイトル更新：「チームと氏名を選択してください」
  - `gateTeamSelect` にスタイル適用

### 写真任意化（mobile-report-app.html）
- `<input type="file">` から `capture="environment"` 属性を削除 → ギャラリー選択を可能に
- 写真なしで送信しようとした場合に `confirm()` ダイアログで確認を求める動作に変更
- ラベルに「任意」を明示

### フロー番号ラベル修正（mobile-report-app.html）
全19番号のラベル・`resultType` を実際のフローに合わせて修正：
- **③**：「陳列されていて購入できた」→「陳列はなかったが在庫から購入した」
- **⑩**：「購入後に陳列を確認しなかった」→「未入荷」
- **⑪〜⑭**：残り1冊のため購入せず（`purchase_steps` → `report` type に変更）
- **⑰**：ラベル修正「短期間撤退」
- **⑱**：ラベル修正「退店」
- **⑲**：ラベル修正「お金なし」

### 担当者→実行者 ラベル変更（全ファイル）
※ DB カラム名 `actor`・JS 変数名 `actorName` はそのまま維持

| ファイル | 変更箇所 |
|---|---|
| `mobile-report-app.html` | `buildReportText()`・メンバー別集計ヘッダー・`_renderReportList` ヘッダー・toast メッセージ |
| `leader.html` | 報告テーブルヘッダー・操作ログヘッダー・CSV ヘッダー・メンバー別集計ヘッダー |

### 報告削除機能（一般ユーザー向け）
- **app_server.py**：`_needs_leader_auth` の DELETE チェックから `"reports"` を除外 → `DELETE /api/reports/{id}` がリーダー認証不要に（チーム・メンバーの単体削除は引き続きリーダー認証必須）
- **mobile-report-app.html**：
  - `_renderReportList` に「削除」列を追加（赤系ボタン）
  - `deleteReport(id)` 関数を追加（confirm → `DELETE /api/reports/{id}` → ローカル `reports` 配列から除外 → `renderDashboard()` 再描画 → toast 通知）

---

## 2026-03-04 (3回目)

### leader.html UI機能追加・修正
- **CATEGORY_MAP ラベル修正**：カテゴリー3・4のラベルを正式表記に修正
  - `購入できなかったけどあった / 予約未入荷（⑩〜⑮）` → `買えなかった/予約未入荷（⑩〜⑮）`
  - `こちらでアクション出来ない状態（⑯〜⑰）` → `アクション不可（⑯〜⑰）`
- **報告テーブル：直近20件制限**：`_filteredReports()` で createdAt 降順ソート後 `.slice(0,20)` を適用。ヘッダーに「直近N件 / 全M件」を表示
- **CSV ダウンロード**：「⬇ CSV」ボタン追加。チームフィルター後の全件（ソート済み・件数制限なし）をBOM付きUTF-8 CSVとして出力（日時/チーム/担当者/報告No./結果/添付ファイル名/購入日時/店舗名/住所/コメント）
- **画像 download 属性**：画像サムネイルリンクに「保存」リンクを追加。`download` 属性でファイル名を指定しダウンロード可能に変更

---

## 2026-03-04 (2回目)

### leader.html UI修正
- **リーダー設定タブ**：パスワード表示カード（ユーザー名・パスワードのinput）を削除。LEADER_PASS変更案内テキストのみ残す
- **カテゴリー別比較テーブル**: サマリーのカテゴリー内訳をstat-boxグリッド表示から「今期 / 前期 / 差分」3列テーブル表示に変更。差分はプラス（緑）・マイナス（赤）・ゼロ（灰）で色分け

---

## 2026-03-04

### leader.html 反映漏れの修正
- `leader.html` が `mobile-report-app.html` と別ファイルで管理されていたため、旧UIが表示され続けていた問題を修正
- リーダー画面にも以下を正式反映：
  - 期間選択（今日 / 今週 / 今月 / 期間指定）
  - 前日比 / 先週比（直前同期間比）
  - 5カテゴリ内訳（①〜⑲の指定区分）
  - メンバー別集計
  - 添付ファイル確認（画像サムネイル + 表示リンク）
- 主要変更ログ表示（`/api/logs/major`）は継続

### 集計タブ（リーダー用）完全実装
- **期間選択UI**：今日 / 今週（7日）/ 今月（30日）/ 期間指定（カレンダーピッカー）の4モード
- **前期比較**：今日→前日比、今週/今月→直前同期間比（▲/▼ 差分を件数・カテゴリ別に表示）
- **内訳5カテゴリ**：
  - 購入（①〜⑦）
  - 予約（⑧〜⑨）
  - 買えなかった/予約未入荷（⑩〜⑮）
  - アクション不可（⑯〜⑰）
  - どういうこと？（⑱〜⑲）
- **メンバー別集計**：担当者ごとの件数テーブル（件数降順）
- **集計タブ内「🔄 更新」ボタン**：集計データ＋報告一覧を同時に最新化
- **報告一覧（添付確認）**：レシート画像はサムネイル表示、タップで拡大

### API改修（app_server.py）
- `/api/summary/daily|weekly|monthly|range` にて `byReportNo`・`byActor`・前期比（`prevTotal`・`prevByReportNo`）を返すよう拡張
- `_query_summary()` ヘルパーを追加し集計ロジックを共通化

### 主要変更ログ機能
- サーバーの `audit_logs` テーブルに以下の操作を記録：
  - `create_team` / `delete_team`
  - `create_report`
  - `delete_reports` / `reset_reports` / `undo_delete`
  - `upload_file`
  - `leader_login_success` / `leader_login_failed`
- `GET /api/logs/major?limit=50` エンドポイント追加（リーダー認証必須）
- `leader.html` の集計タブ「主要変更ログ」セクションで最新50件を表示

### leader.html 修正
- 旧バージョンが別ファイルとして存在し、mobile-report-app.html とは別管理と判明
- 「主要変更ログ」テーブルを追加
- `API.majorLogs = '/api/logs/major?limit=50'` を追加
- `loadData()` 呼び出し時に `loadMajorLogs()` も実行

---

## 2026-03-04（同日・前セッション）

### mobile-report-app.html 改修

#### 予約フロー変更
- 陳列確認を「購入後」に移動
- `reserved_buy_first` → 直接 R6 へ遷移（`display_check_reserved` をバイパス）
- `isSkipBuy` フロー4ステップ：しまう → 陳列探す（YES/NO分岐）→ 店を出る → レシート撮影

#### UI改善
- 指示ノードのボタン色：`choice`（amber）→ `btn-primary`（blue）
- 集計タブの「🚧 作成中」プレースホルダー → 実際の集計UIに置き換え
- `hasDashboard` 判定を `summaryBox` 要素の存在確認に変更

#### フォーム
- `mapsUrl` 入力欄・`mapsParseBtn` 削除
- `storeName` 入力 → `storeSearchName`（readonly・グレー）に自動同期
- 住所欄説明：「都道府県を選んで書店の住所を検索する」に変更
- 送信後：フォームを非表示にして `doneCard` のみ表示し最上部にスクロール

#### リーダー認証
- ログイン画面：ユーザー名欄を削除、パスワードのみ入力（1111）

### app_server.py 改修
- `.html` ファイルに `Cache-Control: no-store` ヘッダーを付与
- ログイン処理：`username` フィールドをリクエストボディから削除、`user` は `'leader'` 固定

### インフラ
- team-bar に「🔄 更新」ボタン追加（`?r=timestamp` でハードリロード）
- VPS: `220.158.19.143:8080` にデプロイ済み

---

## それ以前（セッション開始前の実装済み機能）
- フロー状態の永続化（localStorage・戻る機能）
- 完了カード（`doneCard`）表示
- 住所検索（都道府県セレクター + 書店名候補）
- シークレットロックボタン
- サーバー共有DB（SQLite）モード / ローカルモード自動切り替え
- レシート写真アップロード（Base64 → `/uploads/{uuid}.ext`）
- チーム管理・メンバー設定
