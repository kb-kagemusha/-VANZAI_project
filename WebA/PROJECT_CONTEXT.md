# プロジェクト引き継ぎドキュメント

> このファイルは AI セッションをまたいで状況を引き継ぐための常設ドキュメントです。  
> 変更のたびに該当セクションを更新してください。

---

## 1. プロジェクト概要

「買い周りサポートアプリ」— 書店巡回スタッフが店頭オペレーションを報告するための Web アプリ。

| 役割 | 画面 |
|---|---|
| 一般スタッフ（スマホ） | `mobile-report-app.html` |
| リーダー（PC/スマホ） | `leader.html` |
| バックエンド | `app_server.py` |

---

## 2. インフラ・デプロイ

### VPS 情報
| 項目 | 値 |
|---|---|
| ホスト | `220.158.19.143` |
| ドメイン | `bookstore-hopping.com` |
| アプリURL（HTTPS化後） | `https://bookstore-hopping.com` |
| ポート（内部） | `8080`（Nginx → app_server.py） |
| ユーザー | `root` |
| アプリパス | `/opt/mykey/` |
| サービス名 | `mykey.service` |

### SSL / HTTPS 構成（2026-03-04 設定済み）

```
スマホ/PC  →  HTTPS:443  →  Nginx（リバースプロキシ）  →  HTTP:8080  →  app_server.py
```

| 項目 | 状態 |
|---|---|
| Nginx | インストール済み・稼働中 |
| certbot (Let's Encrypt) | インストール済み |
| UFW 80/443 開放 | 完了 |
| Nginx リバースプロキシ設定 | `/etc/nginx/sites-available/bookstore-hopping.com` |
| SSL 証明書取得 | **DNS 反映後に下記コマンドを実行** |

#### DNS 反映確認コマンド（PowerShell）
```powershell
ssh -i "$env:USERPROFILE\.ssh\vps_key" -o StrictHostKeyChecking=no root@220.158.19.143 'dig +short bookstore-hopping.com @8.8.8.8'
# → 220.158.19.143 が返ったら反映済み
```

#### SSL 証明書取得コマンド（DNS 反映後に 1 回だけ実行）
```powershell
ssh -i "$env:USERPROFILE\.ssh\vps_key" -o StrictHostKeyChecking=no root@220.158.19.143 'certbot --nginx -d bookstore-hopping.com -d www.bookstore-hopping.com --non-interactive --agree-tos -m admin@bookstore-hopping.com'
```
成功すると Nginx が自動で HTTPS 設定に書き換えられ、HTTP→HTTPS リダイレクトも有効になる。  
証明書は 90 日ごとに自動更新（systemd タイマーで設定済み）。

### SSH 鍵
```
$env:USERPROFILE\.ssh\vps_key
```

### デプロイ手順（Windows PowerShell）

```powershell
# 1. ファイル転送（変更したファイルのみ指定する）
scp -i "$env:USERPROFILE\.ssh\vps_key" -o StrictHostKeyChecking=no `
  "C:\MykeyC\app_server.py" `
  "C:\MykeyC\mobile-report-app.html" `
  "C:\MykeyC\leader.html" `
  root@220.158.19.143:/opt/mykey/

# 2. サービス再起動
ssh -i "$env:USERPROFILE\.ssh\vps_key" -o StrictHostKeyChecking=no root@220.158.19.143 `
  "systemctl restart mykey.service && sleep 2 && systemctl is-active mykey.service"
```

`active` が返れば成功。

### ローカル構文チェック（デプロイ前に実施）
```powershell
C:/MykeyC/.venv/Scripts/python.exe -m py_compile C:/MykeyC/app_server.py
```

---

## 3. ファイル構成

```
C:\MykeyC\
├── app_server.py          # Python バックエンド（SimpleHTTPRequestHandler + SQLite）
├── mobile-report-app.html # スタッフ用スマホアプリ（~2600行）
├── leader.html            # リーダー用管理画面（~800行）
├── CHANGELOG.md           # 変更ログ（必ず追記）
├── PROJECT_CONTEXT.md     # 本ファイル
├── shared_reports.db      # SQLite DB（VPS 側が正）
├── uploads/               # アップロードされた画像
└── .venv/                 # Python 仮想環境（ローカルテスト用）
```

---

## 4. DB スキーマ（shared_reports.db）

```sql
-- レポート本体
CREATE TABLE reports (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  team            TEXT,
  actor           TEXT,       -- 実行者名（表示ラベルは「実行者」）
  result_type     TEXT,
  report_no       TEXT,
  purchase_at     TEXT,
  store_name      TEXT,
  store_address   TEXT,
  receipt_file_name TEXT,
  comment         TEXT,
  created_at      TEXT,
  remaining_stock TEXT NOT NULL DEFAULT '',  -- 書店内残り冊数（任意）
  deleted_at      TEXT        -- ソフトデリート。NULL = 有効
);

-- チーム
CREATE TABLE teams (
  name            TEXT PRIMARY KEY,
  created_at      TEXT,
  event_start_date TEXT  -- N日目バッジ用
);

-- メンバー
CREATE TABLE members (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT,
  team       TEXT,
  created_at TEXT,
  sort_order INTEGER,  -- 登録順並び（NULL の場合は id で代替）
  is_leader  INTEGER NOT NULL DEFAULT 0
);

-- 予定
CREATE TABLE schedules (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  team            TEXT,
  member          TEXT,
  date            TEXT,
  availability    TEXT,  -- o / d / x
  location_detail TEXT,  -- JSON: {home, work, noteEnabled, note}
  updated_at      TEXT,
  UNIQUE(team, member, date)
);

-- 担当指名
CREATE TABLE leader_assignments (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  team           TEXT,
  member         TEXT,
  date           TEXT,
  assigned_at    TEXT,
  purchase_count INTEGER DEFAULT 1,  -- 購入担当冊数 1〜3
  UNIQUE(team, member, date)
);

-- 担当メモ
CREATE TABLE assignment_notes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  team        TEXT,
  member_name TEXT,
  note_date   TEXT,
  note_text   TEXT,
  updated_at  TEXT,
  UNIQUE(team, member_name, note_date)
);

-- プロフィール
CREATE TABLE profiles (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  team            TEXT,
  member          TEXT,
  home_area       TEXT,
  work_area       TEXT,
  transport_modes TEXT,  -- car,train,walk をカンマ区切り
  updated_at      TEXT,
  UNIQUE(team, member)
);

-- 監査ログ
CREATE TABLE audit_logs (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  action    TEXT,
  detail    TEXT,
  createdAt TEXT
);

-- 削除履歴（undo 用）
CREATE TABLE deletions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  report_ids TEXT,   -- JSON 配列
  deleted_at TEXT
);
```

---

## 5. 主要 API エンドポイント

| メソッド | パス | 認証 | 説明 |
|---|---|---|---|
| GET | `/api/reports` | なし | 報告一覧（論理削除除外） |
| POST | `/api/reports` | なし | 報告作成 |
| DELETE | `/api/reports/{id}` | **なし**（一般ユーザー可） | 単体ソフトデリート |
| DELETE | `/api/reports` | リーダー | 全件リセット |
| POST | `/api/reports/delete` | リーダー | 複数件一括削除 |
| POST | `/api/deletions/undo` | リーダー | 削除取り消し |
| GET | `/api/teams` | なし | チーム一覧 |
| POST | `/api/teams` | リーダー | チーム追加 |
| DELETE | `/api/teams/{name}` | リーダー | チーム削除 |
| PATCH | `/api/teams/{name}` | リーダー | チーム名変更 |
| GET | `/api/members` | なし | メンバー一覧（?team= フィルター可） |
| POST | `/api/members` | リーダー | メンバー追加 |
| DELETE | `/api/members/{id}` | リーダー | メンバー削除 |
| PATCH | `/api/members/{id}` | リーダー | メンバー名変更 |
| GET | `/api/summary/daily` | リーダー | 本日集計 |
| GET | `/api/summary/weekly` | リーダー | 今週集計 |
| GET | `/api/summary/monthly` | リーダー | 今月集計 |
| GET | `/api/summary/range?from=&to=` | リーダー | 期間指定集計 |
| POST | `/api/upload` | なし | 画像アップロード |
| GET | `/uploads/{filename}` | なし | 画像取得 |
| GET | `/api/logs/major?limit=50` | リーダー | 主要変更ログ |
| POST | `/api/login` | — | リーダーログイン（パスワード: `LEADER_PASS` 環境変数） |
| GET | `/api/health` | なし | ヘルスチェック |

---

## 6. 認証方式

- リーダー認証：`POST /api/login` でパスワードを送信 → `Set-Cookie: leader_session=...`
- `_needs_leader_auth(method, parts)` でガード対象を判定
- セッション有効期限：72時間

---

## 7. フロー番号対応表（報告番号 → resultType）

> `resultType` は DB・画面ともに日本語文字列で保存される（英語コードは使用していない）。  
> ①②④⑤ / ⑪〜⑭ は `resultType` が同じでも到達経路が異なる別番号。

| No. | フロー到達条件（簡易） | resultType（DB保存値） | フロータイプ |
|---|---|---|---|
| ① | 自分で本を発見 → 在庫十分（平積み4冊以上 or 他店2冊以上）→ 購入 | 陳列されていて購入できた | purchase_steps |
| ② | 自分で本を発見 → 棚刺し2冊以上（紀伊/丸善ジュンク堂）→ 購入 | 陳列されていて購入できた | purchase_steps |
| ③ | 自分では見つからず → 店員がバックヤードから取り出してくれた → 購入 | 陳列はなかったが在庫から購入した | purchase_steps |
| ④ | 自分では見つからず → 店員が棚を案内 → 4冊以上 → 購入 | 陳列されていて購入できた | purchase_steps |
| ⑤ | 自分では見つからず → 店員が棚を案内 → 棚刺し2冊以上 → 購入 | 陳列されていて購入できた | purchase_steps |
| ⑥ | 予約本を購入（購入後の陳列確認スキップ or 陳列なし） | 予約した本を購入できた | purchase_steps |
| ⑦ | 予約本を購入 → 購入後確認で陳列あり | 予約した本を購入できた | purchase_steps |
| ⑧ | 本が見つからず → 店に予約歴なし → 予約成功 | 予約できた | report |
| ⑨ | 本が見つからず → 予約歴あり（1ヶ月以上経過）→ 再予約成功 | 予約できた | report |
| ⑩ | 予約中の本が未入荷 | 予約していたが未入荷だった | report |
| ⑪ | 自分で発見(平積み) → 残り1冊のため購入せず | 残り1冊だったため購入せず | report |
| ⑫ | 自分で発見(棚刺し) → 残り1冊のため購入せず | 残り1冊だったため購入せず | report |
| ⑬ | 店員案内(在庫少) → 残り1冊のため購入せず | 残り1冊だったため購入せず | report |
| ⑭ | 店員案内(棚刺し) → 残り1冊のため購入せず | 残り1冊だったため購入せず | report |
| ⑮ | 本が見つからず → 初回予約を断られた | 予約断られた | report |
| ⑯ | 本が見つからず → 再予約を断られた | 予約断られた | report |
| ⑰ | 本が見つからず → 予約歴あり → 前回受取から1ヶ月未満（早すぎる）→ 撤退 | 短期間に行き過ぎているため撤退 | report |
| ⑱ | 今日この店に2回目以上来訪 → 退店 | 何も考えずに同じ店に来てしまったため退店 | report |
| ⑲ | 2200円以上の現金を用意できなかった | お金が足りなかった | report |

---

## 8. 変数・ラベル対応メモ

| コード内の識別子 | 画面表示 | 備考 |
|---|---|---|
| `actor` (DB カラム) | 実行者 | カラム名は変えない |
| `actorName` (JS 変数) | 実行者 | 変数名は変えない |
| `team` (DB カラム) | チーム | — |
| `reportNo` | 報告ナンバー | ①〜⑲ |
| `resultType` | 結果 | 上記フロー番号対応表参照 |

---

## 9. 作業ルール

### CHANGELOG.md の書き方
1. 本セッションで変更したら **必ず** `CHANGELOG.md` に追記する
2. セクション見出し：`## YYYY-MM-DD (N回目)` の形式
3. 変更内容はファイル名・関数名・API パスを具体的に記載する

### 修正時の注意事項
- `app_server.py` を変更したら必ずデプロイ前に構文チェック（`py_compile`）を実施
- DB カラム名・JS 変数名は変えず、**表示ラベルのみ**変更する（上表参照）
- `_needs_leader_auth` を変更するときは意図しない認証漏れが生じないよう注意。テーブル参照を維持すること
- HTMLファイルは大きいため（2600行超）、`grep_search` で対象行を特定してから `replace_string_in_file` で編集する

### デプロイ後の確認
```powershell
# サービス起動確認
ssh -i "$env:USERPROFILE\.ssh\vps_key" root@220.158.19.143 "systemctl is-active mykey.service"

# ヘルスチェック
curl http://220.158.19.143:8080/api/health
```

---

## 10. 現在の既知の課題・TODOメモ

（次のセッションで取り組む場合はここに追記してください）

- 特になし

---

## 11. 直近セッション（2026-03-06 3回目）の変更サマリー

### mobile-report-app.html
| 変更内容 | 詳細 |
|---|---|
| CSV出力列順・日本語ヘッダー | `exportCsv()` を columns配列方式に刷新。purchaseAt を購入日/購入時刻に分割。teamとidは除外 |
| リセットボタン表示制御 | デフォルト非表示、🔒タップ時のみ表示 |
| 自分のデータ保存後に自動で畳む | saveProfile()成功後にprofileEditAreaを閉じ「保存しました」トースト表示 |
| iOSチェックボックスズレ修正 | `-webkit-flex`等のプレフィックス追加、min-height/vertical-align設定 |
| 担当日のオレンジ枠表示 | `myWeekAssignedDates`（Set）を追加。loadMyWeekSchedule内でassignmentsを並行取得 |
| 自宅チェックの仕様変更 | 初回登録時のみデフォルトチェック。以後は外せる（描画での強制補正を削除） |
| メンバー並び順修正 | フロントの`localeCompare`ソートを削除。サーバーの登録順（sort_order）を尊重 |

### `reports` テーブル現在のカラム順（CSV出力順）
```
タイムスタンプ(createdAt) / 購入者(actor) / 結果(result_type) /
在庫冊数(remaining_stock) / 報告ナンバー(report_no) / 購入日 / 購入時刻(purchase_at分割) /
店舗名(store_name) / 住所(store_address) / レシート(receipt_file_name) / コメント(comment)
```

---

## 12. 報告ナンバー全一覧（フロー定義上）

| 報告ナンバー | resultType（内容） | バッジ | 備考 |
|---|---|---|---|
| ① | 陷列されていて購入できた | 購入 | 大型店：平積・2冊以上 |
| ② | 陷列されていて購入できた | 購入 | 大型店：棚刺し・2冊以上 |
| ③ | 陷列はなかったが在庫から購入した | 購入 | 店員バックヤード経由 |
| ④ | 陷列されていて購入できた | 購入 | 大型店：店員経・4冊以上 |
| ⑤ | 陷列されていて購入できた | 購入 | 大型店：店員経・棚・2冊以上 |
| ⑥ | 予約した本を購入できた | 購入 | 予約入荷・陷列あり |
| ⑦ | 予約した本を購入できた | 購入 | 予約入荷・陷列なし |
| ⑧ | 予約できた | 予約 | 初回予約 |
| ⑨ | 予約できた | 予約 | 再予約（1ヶ月以上経過） |
| ⑩ | 予約していたが未入荷だった | 不可 | 予約入荷待ち |
| ⑪ | 残り1冊だったため購入せず | 不可 | 大型店：陷列・平積 |
| ⑫ | 残り1冊だったため購入せず | 不可 | 大型店：陷列・棚 |
| ⑬ | 残り1冊だったため購入せず | 不可 | 大型店：店員経・4冊以下 |
| ⑭ | 残り1冊だったため購入せず | 不可 | 大型店：店員経・棚・1冊 |
| ⑮ | 予約断られた | 不可 | 初回予約拒否 |
| ⑯ | 予約断られた | 不可 | 再予約拒否 |
| ⑰ | 短期間に行き過ぎているため撤退 | 不可 | 1ヶ月未満の再訪問 |
| ⑱ | 何も考えずに同じ店に来てしまったため退店 | 不可 | 2回目以上の訪問 |
| ⑲ | お金が足りなかった | 不可 | 現金不足 |
| ㉛ | 電話確認：在庫あり・取り置き成功 | 予約 | 電話フロー |
| ㉜ | 電話確認：入荷待ち・予約成功 | 予約 | 電話フロー |
| ㉝ | 電話確認：予約不可 | 不可 | 電話フロー |

> **バッジ判定ロジック**（leader.html 内）
> - 購入：①〜⑦
> - 予約：⑧⑨㉛㉜
> - 不可：⑩〜⑲㉝
> - 上記廣数字以外の旧形式（アラビア数字等）は resultType テキストでフォールバック判定

---

*最終更新: 2026-03-10*
